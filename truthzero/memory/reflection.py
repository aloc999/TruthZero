import re
from truthzero.memory.store import MemoryStore


class ReflectionEngine:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store
        self.consecutive_failures: dict[str, int] = {}
        self.session_failure_count: int = 0
        self._message_count: int = 0
        self._current_project: str = ""
        self._error_patterns = {
            "permission denied": "security_error",
            "not found": "tool_error",
            "timeout": "tool_error",
            "syntax error": "code_error",
            "type error": "code_error",
            "connection refused": "tool_error",
            "access denied": "security_error",
            "invalid": "logic_error",
            "failed": "tool_error",
            "exception": "code_error",
        }

    def _classify_error(self, error: str) -> str:
        error_lower = error.lower()
        for pattern, category in self._error_patterns.items():
            if pattern in error_lower:
                return category
        return "logic_error"

    def should_trigger_reflection(self, tool_name: str, success: bool) -> bool:
        self._message_count += 1

        if success:
            self.consecutive_failures[tool_name] = 0
        else:
            self.consecutive_failures[tool_name] = self.consecutive_failures.get(tool_name, 0) + 1
            self.session_failure_count += 1

        if self.consecutive_failures.get(tool_name, 0) >= 3:
            return True

        if self.session_failure_count >= 5:
            return True

        if self._message_count % 15 == 0:
            return True

        return False

    async def analyze_tool_failure(
        self, tool_name: str, args: dict, error: str, context: str
    ) -> str:
        category = self._classify_error(error)
        lesson = f"Tool '{tool_name}' failed with args {args}: {error}"
        await self.memory.add_mistake(context, error, lesson, category)

        anti_pattern = f"args={args} -> {error}"
        await self.memory.add_tool_pattern(tool_name, "", anti_pattern)

        similar = await self.memory.get_relevant_mistakes(context, limit=3)
        repeated = [m for m in similar if tool_name in m.get("lesson", "")]

        advice_parts = [f"WARNING: {tool_name} just failed: {error}"]

        consec = self.consecutive_failures.get(tool_name, 0)
        if consec >= 3:
            advice_parts.append(
                f"CRITICAL: {tool_name} has failed {consec} consecutive times. "
                "STOP using this tool and try a completely different approach."
            )
            strategy = await self.suggest_strategy(context)
            if strategy:
                advice_parts.append(f"Suggested strategy: {strategy}")

        if len(repeated) > 1:
            advice_parts.append(
                f"This tool has failed {len(repeated)} times in similar contexts."
            )
            for m in repeated[:2]:
                advice_parts.append(f"  Previous lesson: {m['lesson']}")
            advice_parts.append("Consider a different approach entirely.")

        patterns = await self.memory.get_tool_patterns(tool_name)
        good_patterns = [p for p in patterns if p["pattern"]]
        if good_patterns:
            advice_parts.append(f"Known working pattern: {good_patterns[0]['pattern']}")

        if self.session_failure_count >= 5:
            advice_parts.append(
                f"SESSION ALERT: {self.session_failure_count} total failures this session. "
                "Consider re-evaluating the overall approach."
            )

        return "\n".join(advice_parts)

    async def analyze_tool_success(
        self, tool_name: str, args: dict, result: str, context: str
    ):
        approach = f"Tool '{tool_name}' with args {args}"
        outcome = result[:500] if len(result) > 500 else result
        await self.memory.add_success(context, approach, outcome, "tool_success")

        pattern = f"args={args} -> success"
        await self.memory.add_tool_pattern(tool_name, pattern, "")

        self.consecutive_failures[tool_name] = 0

    async def analyze_conversation(self, messages: list[dict]) -> list[str]:
        lessons = []
        error_counts: dict[str, int] = {}
        tool_failures: dict[str, int] = {}

        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            for pattern, category in self._error_patterns.items():
                if pattern in content.lower():
                    error_counts[category] = error_counts.get(category, 0) + 1

            tool_match = re.findall(
                r"(?:tool|command|function)\s+['\"]?(\w+)['\"]?\s+failed",
                content.lower(),
            )
            for tool in tool_match:
                tool_failures[tool] = tool_failures.get(tool, 0) + 1

        for category, count in error_counts.items():
            if count >= 2:
                lessons.append(
                    f"Repeated {category} errors ({count} times) detected in conversation"
                )

        for tool, count in tool_failures.items():
            if count >= 2:
                lessons.append(
                    f"Tool '{tool}' failed {count} times - consider alternative approaches"
                )

        if len(messages) > 20:
            lessons.append(
                "Long conversation detected - consider breaking the task into smaller steps"
            )

        if self.detect_stuck_pattern(messages):
            lessons.append(
                "STUCK PATTERN DETECTED: Recent messages show repetitive behavior. "
                "Change approach immediately."
            )

        return lessons

    async def get_context_memories(self, current_context: str) -> str:
        mistakes = await self.memory.get_relevant_mistakes(current_context, limit=5)
        successes = await self.memory.get_relevant_successes(current_context, limit=3)

        if not mistakes and not successes:
            return ""

        parts = []

        if mistakes:
            parts.append("LEARNED FROM PAST MISTAKES:")
            for m in mistakes:
                parts.append(f"- {m['lesson']}")

        if successes:
            parts.append("PROVEN APPROACHES:")
            for s in successes:
                parts.append(f"- {s['approach']} -> {s['outcome'][:200]}")

        strategy = await self.suggest_strategy(current_context)
        if strategy:
            parts.append(f"RECOMMENDED STRATEGY: {strategy}")

        return "\n".join(parts)

    async def periodic_reflection(self, messages: list[dict]):
        lessons = await self.analyze_conversation(messages)

        for lesson in lessons:
            category = "system"
            if "security" in lesson.lower():
                category = "security"
            elif "code" in lesson.lower() or "syntax" in lesson.lower():
                category = "code"

            await self.memory.add_knowledge(
                key="conversation_lesson",
                value=lesson,
                source="periodic_reflection",
                category=category,
            )

        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        user_messages = [m for m in messages if m.get("role") == "user"]

        if assistant_messages and user_messages:
            last_user = user_messages[-1].get("content", "")
            if isinstance(last_user, str) and any(
                w in last_user.lower()
                for w in ["wrong", "no", "incorrect", "fix", "that's not", "try again"]
            ):
                await self.memory.add_mistake(
                    context=last_user,
                    error="User indicated previous response was incorrect",
                    lesson=f"User correction after: {last_user[:300]}",
                    category="logic_error",
                )

    async def suggest_strategy(self, context: str) -> str:
        best = await self.memory.get_best_strategy(context)
        if best:
            return (
                f"{best['strategy']} "
                f"(success rate: {best['success_rate']:.0%}, used {best['usage_count']} times)"
            )
        return ""

    async def record_strategy_outcome(self, context: str, strategy: str, success: bool):
        await self.memory.add_strategy(context, strategy)
        async with self.memory._db.execute(
            "SELECT id FROM strategies WHERE context_pattern = ? AND strategy = ? ORDER BY id DESC LIMIT 1",
            (context, strategy),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            await self.memory.update_strategy_outcome(row["id"], success)

    def assess_confidence(self, messages: list[dict]) -> str:
        if not messages:
            return "UNKNOWN: no messages to analyze"

        recent = messages[-10:] if len(messages) > 10 else messages

        error_count = 0
        success_indicators = 0

        for msg in recent:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            lowered = content.lower()
            for pattern in self._error_patterns:
                if pattern in lowered:
                    error_count += 1
            if any(
                w in lowered
                for w in ["success", "completed", "done", "works", "fixed"]
            ):
                success_indicators += 1

        if self.detect_stuck_pattern(messages):
            return "LOW: repeating same approach, consider pivot"

        if error_count > len(recent) * 0.5:
            return "LOW: high error rate in recent messages"

        if success_indicators >= 2 and error_count <= 1:
            return "HIGH: making steady progress"

        if error_count > 0 and success_indicators > 0:
            return "MEDIUM: mixed results, some progress with errors"

        return "MEDIUM: insufficient signal to determine progress"

    def detect_stuck_pattern(self, messages: list[dict]) -> bool:
        if len(messages) < 6:
            return False

        recent = messages[-6:]
        contents = []
        for msg in recent:
            content = msg.get("content", "")
            if isinstance(content, str):
                contents.append(content.strip().lower()[:200])

        if len(contents) < 4:
            return False

        unique_ratio = len(set(contents)) / len(contents)
        if unique_ratio <= 0.5:
            return True

        bigrams = []
        for i in range(len(contents) - 1):
            bigrams.append(f"{contents[i][:50]}|{contents[i + 1][:50]}")
        if len(bigrams) >= 4:
            unique_bigrams = len(set(bigrams))
            if unique_bigrams <= len(bigrams) * 0.5:
                return True

        return False

    def tag_project(self, project_root: str):
        self._current_project = project_root

    async def proactive_warning(self, tool_name: str, args: dict) -> str:
        patterns = await self.memory.get_tool_patterns(tool_name)
        anti_patterns = [p for p in patterns if p.get("anti_pattern")]
        if not anti_patterns:
            return ""

        warnings = []
        args_str = str(args).lower()
        for ap in anti_patterns[:5]:
            anti = ap.get("anti_pattern", "")
            if any(word in args_str for word in anti.lower().split()[:3] if len(word) > 3):
                warnings.append(f"Warning: similar args previously failed — {anti[:100]}")

        return "\n".join(warnings) if warnings else ""

    async def root_cause_analysis(self, tool_name: str, error: str, args: dict, context: str) -> dict:
        error_lower = error.lower()
        root_causes = {
            "timeout": "target_unresponsive",
            "connection refused": "port_closed_or_filtered",
            "permission denied": "insufficient_privileges",
            "not found": "incorrect_path_or_target",
            "401": "authentication_required",
            "403": "access_forbidden",
            "rate limit": "too_many_requests",
            "dns": "dns_resolution_failed",
            "ssl": "certificate_issue",
            "syntax": "malformed_input",
        }
        root = "unknown"
        for pattern, cause in root_causes.items():
            if pattern in error_lower:
                root = cause
                break

        result = {
            "tool": tool_name,
            "error": error[:200],
            "root_cause": root,
            "suggestion": self._suggest_fix(root, tool_name),
        }

        await self.memory.add_mistake(
            context=context[:200],
            error=error[:200],
            lesson=f"Root cause: {root}. Fix: {result['suggestion']}",
            category=f"root_cause:{root}",
        )
        return result

    def _suggest_fix(self, root_cause: str, tool_name: str) -> str:
        fixes = {
            "target_unresponsive": "Increase timeout or verify target is up",
            "port_closed_or_filtered": "Try different ports or check firewall",
            "insufficient_privileges": "Run with elevated privileges or try different approach",
            "incorrect_path_or_target": "Verify the URL/path exists",
            "authentication_required": "Add auth headers or credentials",
            "access_forbidden": "Try different endpoint or bypass technique",
            "too_many_requests": "Add delay between requests or use different IP",
            "dns_resolution_failed": "Check domain spelling or DNS server",
            "certificate_issue": "Add --insecure flag or verify SSL cert",
            "malformed_input": "Check syntax of the input/payload",
        }
        return fixes.get(root_cause, "Review error and try different approach")

    async def learn_from_user_correction(self, user_message: str, previous_response: str, messages: list[dict]):
        correction_keywords = ["wrong", "no", "incorrect", "fix", "that's not", "try again", "not what", "don't"]
        if not any(kw in user_message.lower() for kw in correction_keywords):
            return

        what_was_wrong = user_message[:300]
        what_was_said = previous_response[:300] if previous_response else ""

        lesson = f"User corrected: '{what_was_wrong}' after response: '{what_was_said[:100]}'"
        await self.memory.add_mistake(
            context=what_was_said,
            error=what_was_wrong,
            lesson=lesson,
            category="user_correction",
        )

        tools_in_response = []
        for m in messages[-5:]:
            if m.get("role") == "tool":
                tools_in_response.append(m.get("name", ""))
        if tools_in_response:
            for tool in tools_in_response:
                await self.memory.add_tool_pattern(tool, "", f"user_correction: {what_was_wrong[:100]}")

    async def analyze_behavioral_patterns(self, messages: list[dict]):
        tool_counts = {}
        for m in messages:
            if m.get("role") == "tool":
                name = m.get("name", "")
                tool_counts[name] = tool_counts.get(name, 0) + 1

        for tool, count in tool_counts.items():
            if count > 5:
                await self.memory.add_behavioral_pattern(
                    "over_reliance",
                    f"Used {tool} {count} times in one session — consider diversifying approach"
                )

        error_count = sum(1 for m in messages if m.get("role") == "tool" and "error" in str(m.get("content", "")).lower())
        total_tools = sum(1 for m in messages if m.get("role") == "tool")
        if total_tools > 0 and error_count / total_tools > 0.5:
            await self.memory.add_behavioral_pattern(
                "high_error_rate",
                f"Error rate: {error_count}/{total_tools} — review approach before continuing"
            )

    async def replay_strategy(self, context: str) -> str:
        best = await self.memory.get_best_strategy(context)
        if best:
            return f"Previously successful strategy for similar task: {best.get('strategy', '')}"

        successes = await self.memory.get_relevant_successes(context, limit=3)
        if successes:
            approaches = [s.get("approach", "") for s in successes]
            return f"Approaches that worked before: {'; '.join(approaches)}"

        return ""

    async def evolve_skill(self, skill_name: str, new_technique: str):
        await self.memory.add_knowledge(
            key=f"skill_evolution:{skill_name}",
            value=new_technique,
            source="experience",
            category="skill_evolution",
        )

    def assess_confidence_detailed(self, messages: list[dict]) -> dict:
        total_tools = sum(1 for m in messages if m.get("role") == "tool")
        errors = sum(1 for m in messages if m.get("role") == "tool" and "error" in str(m.get("content", "")).lower())
        corrections = sum(1 for m in messages if m.get("role") == "user" and any(w in str(m.get("content", "")).lower() for w in ["wrong", "no", "fix", "incorrect"]))

        success_rate = ((total_tools - errors) / total_tools * 100) if total_tools > 0 else 100
        if success_rate > 80 and corrections == 0:
            level = "HIGH"
            detail = "Making steady progress, low error rate"
        elif success_rate > 50:
            level = "MEDIUM"
            detail = f"Some errors ({errors}/{total_tools}), may need to adjust approach"
        else:
            level = "LOW"
            detail = f"High error rate ({errors}/{total_tools}), consider changing strategy"

        if corrections > 0:
            level = "LOW" if corrections > 1 else "MEDIUM"
            detail += f", {corrections} user correction(s)"

        return {"level": level, "score": int(success_rate), "detail": detail}
