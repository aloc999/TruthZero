import asyncio
import uuid
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class SubagentTask:
    task_id: str
    description: str
    prompt: str
    status: str = "pending"
    result: str = ""
    error: str = ""


class SubagentManager:
    def __init__(self, agent_factory: Optional[Callable] = None):
        self._agent_factory = agent_factory
        self._tasks: dict[str, SubagentTask] = {}
        self._running: dict[str, asyncio.Task] = {}

    async def spawn(self, description: str, prompt: str, agent_factory: Optional[Callable] = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = SubagentTask(
            task_id=task_id,
            description=description,
            prompt=prompt,
            status="running",
        )
        self._tasks[task_id] = task

        factory = agent_factory or self._agent_factory
        if not factory:
            task.status = "failed"
            task.error = "No agent factory configured"
            return task_id

        async def _run():
            try:
                agent = factory()
                result = await agent.run(prompt)
                task.result = result
                task.status = "completed"
            except Exception as e:
                task.error = str(e)
                task.status = "failed"

        self._running[task_id] = asyncio.create_task(_run())
        return task_id

    async def spawn_parallel(self, tasks: list[dict]) -> list[str]:
        task_ids = []
        for t in tasks:
            tid = await self.spawn(t.get("description", ""), t.get("prompt", ""))
            task_ids.append(tid)
        return task_ids

    async def wait(self, task_id: str, timeout: float = 300.0) -> SubagentTask:
        if task_id in self._running:
            try:
                await asyncio.wait_for(self._running[task_id], timeout=timeout)
            except asyncio.TimeoutError:
                self._tasks[task_id].status = "timeout"
                self._running[task_id].cancel()
        return self._tasks.get(task_id, SubagentTask(task_id=task_id, description="", prompt="", status="not_found"))

    async def wait_all(self, task_ids: list[str], timeout: float = 300.0) -> list[SubagentTask]:
        results = []
        pending = [self._running[tid] for tid in task_ids if tid in self._running]
        if pending:
            done, not_done = await asyncio.wait(pending, timeout=timeout)
            for task in not_done:
                task.cancel()
        for tid in task_ids:
            results.append(self._tasks.get(tid, SubagentTask(task_id=tid, description="", prompt="", status="not_found")))
        return results

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[SubagentTask]:
        return list(self._tasks.values())

    def get_running_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == "running")
