import re
from zer0code.memory.store import MemoryStore


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
