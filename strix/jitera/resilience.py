"""Ride out a model-endpoint outage instead of failing the scan.

Gateway eval run 45947209797 (2026-11-27): the staging model endpoint stalled.
Every hunter's call hung about 290 s and came back 504, and the endpoint then
answered the root agent's next call with ``401 Invalid API key``. The engine's
own replay loop allows a transient error 5 tries over about a minute and never
retries a 401, so the root agent failed on that one reply and took the whole
two-hour scan down 34 minutes in. Strix's arm had run earlier in the day and was
never exposed to the stall.

Under the Jitera profile an agent whose model call fails in an outage-shaped
way keeps replaying its turn, with capped backoff, for up to
``OUTAGE_PATIENCE_S`` of wall-clock time:

- timeouts, dropped connections, 408/425/429 and 5xx (Cloudflare's 52x too);
- 401, but only after this run's credentials have already been accepted. A key
  that worked a few minutes ago did not go bad on its own, so a mid-run 401 is
  the endpoint failing. A 401 before any call has succeeded is a real
  misconfiguration and still fails fast.

When an agent gets a successful reply, its outage clock restarts, so each
separate blip in a long scan gets the full patience. Request errors (400, 404,
422 ...) and deliberate refusals (402, 403) are left to upstream's handling.
The upstream profile is untouched.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from openai import APIConnectionError, APITimeoutError

from strix.jitera import brand
from strix.llm import request_log


if TYPE_CHECKING:
    from strix.llm.request_log import LlmRequestEvent


OUTAGE_PATIENCE_S = 15 * 60.0
_BASE_DELAY_S = 5.0
_MAX_DELAY_S = 60.0

_OUTAGE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 529})

_now = time.monotonic  # tests replace this to move the clock

_lock = threading.Lock()
_installed = False
_credentials_proven = False
_last_success: dict[str, float] = {}


def _on_request(event: LlmRequestEvent) -> None:
    if event.outcome != "success":
        return
    global _credentials_proven  # noqa: PLW0603 - one scan per process
    with _lock:
        _credentials_proven = True
        if event.agent_id:
            _last_success[event.agent_id] = _now()


def _ensure_installed() -> None:
    global _installed  # noqa: PLW0603
    with _lock:
        if _installed:
            return
        _installed = True
    request_log.register_sink(_on_request)


def reset() -> None:
    """Forget every success seen so far (tests; a new scan in the same process)."""
    global _installed, _credentials_proven  # noqa: PLW0603
    request_log.unregister_sink(_on_request)
    with _lock:
        _installed = False
        _credentials_proven = False
        _last_success.clear()


def credentials_proven() -> bool:
    with _lock:
        return _credentials_proven


def _last_success_at(agent_id: str) -> float | None:
    with _lock:
        return _last_success.get(agent_id)


def is_outage_error(exc: BaseException) -> bool:
    """Whether ``exc`` looks like the endpoint failing, not like this request being wrong."""
    if isinstance(exc, APITimeoutError | APIConnectionError | TimeoutError | ConnectionError):
        return True
    code = getattr(exc, "status_code", None)
    if not isinstance(code, int):
        return False
    if code in _OUTAGE_STATUS:
        return True
    return code == 401 and credentials_proven()


class OutageRider:
    """One agent's progress through the current outage, for one run cycle."""

    def __init__(self, agent_id: str, *, patience_s: float = OUTAGE_PATIENCE_S) -> None:
        self.agent_id = agent_id
        self.patience_s = patience_s
        self.attempts = 0
        self._active = brand.current() is brand.JITERA
        self._started: float | None = None
        self._last_failure: float | None = None
        if self._active:
            _ensure_installed()

    @property
    def elapsed_s(self) -> float:
        return 0.0 if self._started is None else _now() - self._started

    def next_delay(self, exc: BaseException) -> float | None:
        """Seconds to wait before replaying the turn, or None to let the failure stand."""
        if not self._active or not is_outage_error(exc):
            return None
        now = _now()
        last_ok = _last_success_at(self.agent_id)
        recovered = (
            self._last_failure is not None and last_ok is not None and last_ok > self._last_failure
        )
        if self._started is None or recovered:
            self._started = now
            self.attempts = 0
        self._last_failure = now
        if now - self._started >= self.patience_s:
            return None
        self.attempts += 1
        backoff: float = _BASE_DELAY_S * float(2 ** (self.attempts - 1))
        return min(_MAX_DELAY_S, backoff)
