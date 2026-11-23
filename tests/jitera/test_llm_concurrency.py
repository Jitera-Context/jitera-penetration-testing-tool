"""LLM_MAX_CONCURRENT_REQUESTS caps the model calls the engine has in flight.

The end-to-end tests drive the real ``StrixProvider.get_model`` chain against a
local stub server that counts how many requests it is serving at once.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

import pytest
from agents.model_settings import ModelSettings
from agents.models.interface import Model, ModelTracing

from strix.config import loader
from strix.config.models import StrixProvider
from strix.config.settings import LlmSettings
from strix.jitera import llm_concurrency


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from pathlib import Path


_REPLY_DELAY = 0.3


def _sse(payload: dict[str, Any]) -> bytes:
    return b"data: " + json.dumps(payload).encode() + b"\n\n"


def _chunk(delta: dict[str, Any], finish: str | None = None) -> bytes:
    return _sse(
        {
            "id": "chatcmpl-1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "gw-model",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
    )


class _CountingHandler(BaseHTTPRequestHandler):
    """Answers each chat completion after a delay, counting requests in flight."""

    lock = threading.Lock()
    in_flight = 0
    peak = 0
    delay = _REPLY_DELAY

    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        cls = type(self)
        with cls.lock:
            cls.in_flight += 1
            cls.peak = max(cls.peak, cls.in_flight)
        try:
            # Like a model that reads one long prompt at a time: no byte until done.
            time.sleep(cls.delay)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(_chunk({"role": "assistant", "content": "OK"}))
            self.wfile.write(_chunk({}, finish="stop"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        finally:
            with cls.lock:
                cls.in_flight -= 1


@pytest.fixture
def gateway() -> Iterator[str]:
    _CountingHandler.in_flight = 0
    _CountingHandler.peak = 0
    _CountingHandler.delay = _REPLY_DELAY
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CountingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    """Settings from this test's env only, never the developer's saved config."""
    for key in (
        "STRIX_LLM",
        "LLM_MAX_CONCURRENT_REQUESTS",
        "LLM_DISABLE_STREAMING",
        "LLM_STREAM_IDLE_TIMEOUT",
        "LLM_STREAM_FIRST_EVENT_TIMEOUT",
        "LLM_STREAM_TOTAL_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(loader, "_override", tmp_path / "no-config.json")
    monkeypatch.setattr(loader, "_cached", None)
    return monkeypatch


def _args() -> tuple[tuple[Any, ...], dict[str, Any]]:
    args = (None, "go", ModelSettings(), [], None, [], ModelTracing.DISABLED)
    return args, {"previous_response_id": None, "conversation_id": None, "prompt": None}


async def _drain(model: Model) -> list[Any]:
    args, kwargs = _args()
    return [event async for event in model.stream_response(*args, **kwargs)]


async def _parallel_streams(base_url: str, calls: int) -> None:
    # A model per call, like one per agent: the cap must hold across all of them.
    models = [
        StrixProvider(api_key="tok", base_url=base_url).get_model("openai/gw-model")
        for _ in range(calls)
    ]
    results = await asyncio.gather(*(_drain(model) for model in models))
    assert all(results)


@pytest.mark.usefixtures("settings_env")
async def test_without_a_cap_every_call_reaches_the_server_at_once(gateway: str) -> None:
    # Shows the stub sees parallel calls, so the capped test below means something.
    await _parallel_streams(gateway, 5)
    assert _CountingHandler.peak == 5


async def test_the_cap_bounds_calls_in_flight(
    gateway: str, settings_env: pytest.MonkeyPatch
) -> None:
    settings_env.setenv("LLM_MAX_CONCURRENT_REQUESTS", "2")
    await _parallel_streams(gateway, 5)
    assert _CountingHandler.peak == 2


async def test_waiting_for_a_slot_does_not_run_the_first_event_timeout(
    gateway: str, settings_env: pytest.MonkeyPatch
) -> None:
    # The third call waits ~1.2 s for its slot, past the 1 s first-event timeout,
    # then gets its first byte 0.6 s after it is sent: it must succeed.
    _CountingHandler.delay = 0.6
    settings_env.setenv("LLM_MAX_CONCURRENT_REQUESTS", "1")
    settings_env.setenv("LLM_STREAM_FIRST_EVENT_TIMEOUT", "1")
    await _parallel_streams(gateway, 3)
    assert _CountingHandler.peak == 1


def test_the_setting_reads_its_env_var_and_defaults_to_no_cap(
    settings_env: pytest.MonkeyPatch,
) -> None:
    assert LlmSettings().max_concurrent_requests == 0
    settings_env.setenv("LLM_MAX_CONCURRENT_REQUESTS", "4")
    assert LlmSettings().max_concurrent_requests == 4
    settings_env.setenv("LLM_MAX_CONCURRENT_REQUESTS", " 2 ")
    assert LlmSettings().max_concurrent_requests == 2


@pytest.mark.parametrize("value", ["-1", "abc", "2.5", ""])
def test_a_bad_value_means_no_cap_with_a_warning_never_an_error(
    settings_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, value: str
) -> None:
    settings_env.setenv("LLM_MAX_CONCURRENT_REQUESTS", value)
    assert LlmSettings().max_concurrent_requests == 0
    if value:
        assert "model calls are not capped" in caplog.text


class _FakeModel(Model):
    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0
        self.stream_closed = False
        self.fail = False

    async def get_response(self, *_args: Any, **_kwargs: Any) -> Any:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(0.05)
            if self.fail:
                raise RuntimeError("provider error")
            return "response"
        finally:
            self.in_flight -= 1

    async def stream_response(self, *_args: Any, **_kwargs: Any) -> AsyncIterator[Any]:
        try:
            for i in range(100):
                await asyncio.sleep(0.01)
                yield f"event-{i}"
        finally:
            self.stream_closed = True


def test_a_cap_of_zero_leaves_the_model_as_it_is() -> None:
    model = _FakeModel()
    assert llm_concurrency.limit(model, 0) is model


async def test_non_streamed_calls_share_the_cap_across_models() -> None:
    inner = _FakeModel()
    first, second = llm_concurrency.limit(inner, 2), llm_concurrency.limit(inner, 2)
    args, kwargs = _args()
    results = await asyncio.gather(
        *(model.get_response(*args, **kwargs) for model in [first, second] * 3)
    )
    assert results == ["response"] * 6
    assert inner.peak == 2


async def test_a_failed_call_gives_its_slot_back() -> None:
    inner = _FakeModel()
    inner.fail = True
    model = llm_concurrency.limit(inner, 1)
    args, kwargs = _args()
    with pytest.raises(RuntimeError):
        await model.get_response(*args, **kwargs)
    inner.fail = False
    assert await asyncio.wait_for(model.get_response(*args, **kwargs), timeout=1) == "response"


async def test_a_stream_closed_early_closes_its_request_and_gives_its_slot_back() -> None:
    inner = _FakeModel()
    model = llm_concurrency.limit(inner, 1)
    args, kwargs = _args()
    stream = model.stream_response(*args, **kwargs)
    assert await anext(stream) == "event-0"
    await stream.aclose()  # type: ignore[attr-defined]
    assert inner.stream_closed
    assert await asyncio.wait_for(model.get_response(*args, **kwargs), timeout=1) == "response"


def test_each_event_loop_gets_its_own_slots() -> None:
    model = llm_concurrency.limit(_FakeModel(), 1)
    args, kwargs = _args()
    for _ in range(2):
        assert asyncio.run(model.get_response(*args, **kwargs)) == "response"


async def test_a_differing_cap_on_the_same_loop_is_ignored_not_rebuilt() -> None:
    # Review #3: rebuilding the semaphore on a changed limit would drop the slots
    # already held and blow the cap. The first value for a loop must win.
    inner = _FakeModel()
    first = llm_concurrency.limit(inner, 2)
    second = llm_concurrency.limit(inner, 5)  # different limit, same event loop
    args, kwargs = _args()
    await asyncio.gather(
        *(model.get_response(*args, **kwargs) for model in [first, second] * 4)
    )
    assert inner.peak <= 2  # the cap held at the first value, not 5

