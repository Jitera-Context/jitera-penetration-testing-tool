"""The ``--reasoning-effort`` run parameter: send the model's effort, even when
LiteLLM's catalog doesn't know the model.

Upstream attaches a reasoning effort only for models LiteLLM lists as
reasoning-capable (``strix.config.models.model_supports_reasoning``). Our models
reach the engine under an opaque gateway alias the catalog has no entry for, so
the configured effort — even the default ``high`` — is silently dropped and
nothing is sent (confirmed against the staging GLM gateway, 2026-11-23: no
effort field left the engine). ``--reasoning-effort`` is the user asserting the
model's effort for one run: the chosen level is sent whether or not the catalog
knows the model.

``auto`` means the model's maximum. For an opaque gateway model we cannot read
the model's own ceiling, so the maximum we can ask for is ``max`` (the top of
upstream's effort scale, sent as a raw body field by ``_reasoning_settings``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from strix.config.settings import ReasoningEffort


logger = logging.getLogger(__name__)


# Upstream's effort scale (strix.config.settings.ReasoningEffort), lowest to
# highest, plus the ``auto`` alias that resolves to the highest.
LEVELS: tuple[str, ...] = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
AUTO = "auto"
CLI_CHOICES: tuple[str, ...] = (*LEVELS, AUTO)


def resolve(chosen: str | None, configured: ReasoningEffort) -> tuple[ReasoningEffort, bool]:
    """Return ``(effort, force)`` for a run.

    ``chosen`` is the ``--reasoning-effort`` value or ``None``/empty. When it is
    a known level it wins and is force-sent (the catalog gate is bypassed), with
    ``auto`` resolved to the maximum level. When it is unset, or any value that
    is not a known level, the configured setting is used and upstream's catalog
    gating is left unchanged — so a bad value never forces anything and never
    crashes a run (argparse already rejects bad CLI input; this guards other
    callers of the runner). Default behaviour and the behaviour of models
    LiteLLM does know are untouched.
    """
    level = (chosen or "").strip().lower()
    if not level:
        return configured, False
    if level == AUTO:
        level = LEVELS[-1]
    if level not in LEVELS:
        logger.warning(
            "ignoring unrecognized reasoning effort %r; using the configured %r",
            chosen,
            configured,
        )
        return configured, False
    return level, True  # type: ignore[return-value]
