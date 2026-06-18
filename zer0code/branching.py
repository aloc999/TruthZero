import copy
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Branch:
    name: str
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    parent: str = "main"
    description: str = ""


class ConversationBrancher:
    def __init__(self):
        self._branches: dict[str, Branch] = {
            "main": Branch(name="main", description="Main conversation"),
        }
        self._current: str = "main"

    @property
    def current_branch(self) -> str:
        return self._current

    @property
    def current_messages(self) -> list[dict]:
        return self._branches[self._current].messages

    @current_messages.setter
    def current_messages(self, messages: list[dict]):
        self._branches[self._current].messages = messages

    def create_branch(self, name: str, description: str = "") -> str:
        if name in self._branches:
            name = f"{name}-{int(time.time()) % 10000}"
        messages_copy = copy.deepcopy(self._branches[self._current].messages)
        self._branches[name] = Branch(
            name=name,
            messages=messages_copy,
            parent=self._current,
            description=description or f"Branch from {self._current}",
        )
        return name

    def switch_branch(self, name: str) -> bool:
        if name not in self._branches:
            return False
        self._current = name
        return True

    def delete_branch(self, name: str) -> bool:
        if name == "main" or name == self._current:
            return False
        if name in self._branches:
            del self._branches[name]
            return True
        return False

    def list_branches(self) -> list[dict]:
        return [
            {
                "name": b.name,
                "messages": len(b.messages),
                "parent": b.parent,
                "description": b.description,
                "current": b.name == self._current,
                "created": b.created_at,
            }
            for b in self._branches.values()
        ]

    def merge_branch(self, source: str, target: str = "main") -> bool:
        if source not in self._branches or target not in self._branches:
            return False
        source_msgs = self._branches[source].messages
        target_msgs = self._branches[target].messages
        common_len = min(len(source_msgs), len(target_msgs))
        diverge_point = 0
        for i in range(common_len):
            if source_msgs[i] != target_msgs[i]:
                diverge_point = i
                break
            diverge_point = i + 1
        new_msgs = source_msgs[diverge_point:]
        if new_msgs:
            self._branches[target].messages.append({
                "role": "system",
                "content": f"[Merged from branch '{source}': {len(new_msgs)} messages]",
            })
            self._branches[target].messages.extend(new_msgs)
        return True

    def get_branch(self, name: str) -> Optional[Branch]:
        return self._branches.get(name)
