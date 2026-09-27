import asyncio
import time
from dataclasses import dataclass


@dataclass
class ComparisonResult:
    provider: str
    model: str
    response: str
    tokens: int
    cost: float
    duration: float
    error: str = ""


class ModelComparator:
    def __init__(self, provider_factory=None):
        self._factory = provider_factory

    async def compare(self, prompt: str, models: list[dict], provider_factory=None) -> list[ComparisonResult]:
        factory = provider_factory or self._factory
        if not factory:
            return []

        tasks = []
        for m in models:
            tasks.append(self._run_single(factory, m.get("provider", "openai"), m.get("model", "gpt-4o"), prompt))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final.append(ComparisonResult(
                    provider=models[i].get("provider", "?"),
                    model=models[i].get("model", "?"),
                    response="", tokens=0, cost=0, duration=0,
                    error=str(result),
                ))
            else:
                final.append(result)

        return final

    async def _run_single(self, factory, provider_name: str, model: str, prompt: str) -> ComparisonResult:
        start = time.monotonic()
        try:
            provider = factory(provider_name, model=model)
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Be concise."},
                {"role": "user", "content": prompt},
            ]
            response = await provider.chat(messages=messages)
            duration = time.monotonic() - start

            input_t = response.usage.get("prompt_tokens", 0)
            output_t = response.usage.get("completion_tokens", 0)

            return ComparisonResult(
                provider=provider_name,
                model=model,
                response=response.content[:2000],
                tokens=input_t + output_t,
                cost=0,
                duration=round(duration, 2),
            )
        except Exception as e:
            return ComparisonResult(
                provider=provider_name, model=model,
                response="", tokens=0, cost=0,
                duration=round(time.monotonic() - start, 2),
                error=str(e),
            )

    @staticmethod
    def format_results(results: list[ComparisonResult]) -> str:
        lines = ["# Model Comparison\n"]
        for r in results:
            lines.append(f"## {r.provider}/{r.model}")
            if r.error:
                lines.append(f"**Error:** {r.error}")
            else:
                lines.append(f"**Tokens:** {r.tokens} | **Time:** {r.duration}s")
                lines.append(f"\n{r.response}\n")
            lines.append("---")
        return "\n".join(lines)
