"""Cap how many model calls the engine has in flight at once.

A self-hosted model that reads long prompts one at a time makes every agent
wait for every other agent's prompt. On staging (2026-11-23) GLM-5.3-Flash took
about 7 s per 144k-token prompt, so 10-20 agents calling together queued each
other into multi-minute stalls, and calls that saw no first byte for 300 s were
dropped. ``LLM_MAX_CONCURRENT_REQUESTS=N`` lets N calls run; the rest wait for
a free slot inside the engine, before any request or stream timeout starts.
0, the default, is no cap.

The cap is shared by every call the process makes: agent turns, compaction
summaries and report dedupe all get their model from ``StrixProvider.get_model``.
A streamed call keeps its slot until its stream ends or is closed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import weakref
from typing import TYPE_CHECKING

from agents.models.interface import Model


if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from agents.agent_output import AgentOutputSchemaBase
    from agents.handoffs import Handoff
    from agents.items import ModelResponse, TResponseInputItem, TResponseStreamEvent
    from agents.model_settings import ModelSettings
    from agents.models.interface import ModelTracing
    from agents.retry import ModelRetryAdvice, ModelRetryAdviceRequest
    from agents.tool import Tool
    from openai.types.responses.response_prompt_param import ResponsePromptParam


logger = logging.getLogger(__name__)

# One semaphore per event loop: an asyncio.Semaphore binds to the loop that
# first waits on it, and tests run many loops in one process.
_SLOTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]] = (
    weakref.WeakKeyDictionary()
)


def _slots(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    entry = _SLOTS.get(loop)
    if entry is None:
        entry = (limit, asyncio.Semaphore(limit))
        _SLOTS[loop] = entry
    elif entry[0] != limit:
        # The cap is read once from settings, so it is constant for a loop.
        # Replacing the live semaphore would drop the slots already held on it
        # and blow the cap, so the first value wins; a differing value is a bug.
        logger.warning(
            "LLM concurrency cap is already %d for this event loop; ignoring new value %d",
            entry[0],
            limit,
        )
    return entry[1]


def limit(model: Model, max_concurrent: int) -> Model:
    """``model`` with its calls under the process-wide cap, or as is when the cap is 0."""
    if max_concurrent <= 0:
        return model
    return ConcurrencyLimitedModel(model, max_concurrent)


class ConcurrencyLimitedModel(Model):
    """Run each call of ``inner`` only once a slot of the shared cap is free."""

    def __init__(self, inner: Model, max_concurrent: int) -> None:
        self._inner = inner
        self._max_concurrent = max_concurrent

    async def close(self) -> None:
        await self._inner.close()

    def get_retry_advice(self, request: ModelRetryAdviceRequest) -> ModelRetryAdvice | None:
        return self._inner.get_retry_advice(request)

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],  # noqa: A002
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> ModelResponse:
        async with _slots(self._max_concurrent):
            return await self._inner.get_response(
                system_instructions,
                input,
                model_settings,
                tools,
                output_schema,
                handoffs,
                tracing,
                previous_response_id=previous_response_id,
                conversation_id=conversation_id,
                prompt=prompt,
            )

    async def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],  # noqa: A002
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        async with _slots(self._max_concurrent):
            stream = self._inner.stream_response(
                system_instructions,
                input,
                model_settings,
                tools,
                output_schema,
                handoffs,
                tracing,
                previous_response_id=previous_response_id,
                conversation_id=conversation_id,
                prompt=prompt,
            )
            try:
                async for event in stream:
                    yield event
            finally:
                # A consumer that stops early closes this generator; close the
                # inner stream too, so its request ends before the slot frees.
                aclose = getattr(stream, "aclose", None)
                if aclose is not None:
                    with contextlib.suppress(Exception):
                        await aclose()
