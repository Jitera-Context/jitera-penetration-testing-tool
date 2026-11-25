"""``scan_static_exposure`` -- mine served JS/HTML for secrets and hidden endpoints.

Two of the vulnerability classes the agent rarely lands come down to reading the
front-end carefully: **sensitive-data exposure** (a credential or key hardcoded
into a bundle) and **security through obscurity** (an endpoint that is never
linked but still works, discoverable only by reading the JavaScript). The model
tends to skim bundles rather than grep them exhaustively.

This tool does the exhaustive pass deterministically: give it the HTML/JS the
agent already fetched and it returns every high-signal secret and every
app-internal endpoint path it can extract, each tied to the asset it came from.
Secrets are returned redacted (type, length, first/last few chars, location) --
enough to file and re-locate a finding without dumping the raw secret into logs.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents import function_tool


# --- secret patterns: high-signal, low-false-positive -------------------------

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("slack_webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_+-]+")),
    ("github_token", re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b")),
    ("stripe_secret_key", re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("basic_auth_url", re.compile(r"https?://[^/\s:@\"']+:[^/\s:@\"']+@[^/\s\"']+")),
    # generic assignment -- lower confidence, flagged as such
    (
        "generic_credential_assignment",
        re.compile(
            r"(?i)(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token|passwd|password)"
            r"""\s*[:=]\s*["']([^"']{8,})["']"""
        ),
    ),
]

# a secret pattern name is "low confidence" when its hit needs human eyes
_LOW_CONFIDENCE = {"generic_credential_assignment"}

# --- endpoint patterns: app-internal paths referenced from JS/HTML ------------

# Only app-internal looking paths (/api, /rest, ...) so the signal stays high and
# we surface routes that exist but are never linked in the UI.
_ENDPOINT_PATTERN = re.compile(
    r"""["'](/(?:api|rest|graphql|v\d+|internal|admin|debug|actuator|_next|backup|metrics)"""
    r"""/[A-Za-z0-9_\-./{}:]*)["']"""
)
# also raw fetch/axios/XHR targets that are absolute app paths
_CALL_TARGET_PATTERN = re.compile(
    r"""(?:fetch|axios(?:\.[a-z]+)?|\.open)\(\s*(?:["'][A-Z]+["']\s*,\s*)?["'](/[A-Za-z0-9_\-./{}:]+)["']"""
)

# comments that often leak intent/credentials
_SENSITIVE_COMMENT = re.compile(
    r"(?i)(?://|/\*|<!--)[^\n]{0,80}\b(todo|fixme|hack|backdoor|password|secret|do not ship|debug only)\b[^\n]{0,80}"  # noqa: E501
)


def _redact(value: str) -> str:
    """Return a safe preview of a secret: length + a few edge chars."""
    v = value.strip()
    if len(v) <= 8:
        return f"<{len(v)} chars>"
    return f"{v[:4]}...{v[-4:]} (<{len(v)} chars>)"


def scan_exposure(assets: list[dict[str, str]]) -> dict[str, Any]:
    """Pure logic of :func:`scan_static_exposure` (no I/O, easy to test)."""
    if not isinstance(assets, list) or not assets:
        return {"success": False, "error": "assets must be a non-empty list of {url, content}"}

    secrets: list[dict[str, Any]] = []
    endpoints: list[dict[str, str]] = []
    comments: list[dict[str, str]] = []
    seen_secret: set[tuple[str, str, str]] = set()
    seen_ep: set[str] = set()
    seen_comment: set[str] = set()

    for item in assets:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "") or "")
        content = str(item.get("content", "") or "")
        if not content:
            continue

        for name, pat in _SECRET_PATTERNS:
            for m in pat.finditer(content):
                raw = m.group(1) if m.groups() else m.group(0)
                key = (name, url, raw)
                if key in seen_secret:
                    continue
                seen_secret.add(key)
                secrets.append(
                    {
                        "type": name,
                        "preview": _redact(raw),
                        "source_url": url,
                        "confidence": "low" if name in _LOW_CONFIDENCE else "high",
                    }
                )

        for pat in (_ENDPOINT_PATTERN, _CALL_TARGET_PATTERN):
            for m in pat.finditer(content):
                path = m.group(1)
                if path not in seen_ep:
                    seen_ep.add(path)
                    endpoints.append({"path": path, "source_url": url})

        for m in _SENSITIVE_COMMENT.finditer(content):
            snippet = m.group(0).strip()[:160]
            if snippet not in seen_comment:
                seen_comment.add(snippet)
                comments.append({"snippet": snippet, "source_url": url})

    return {
        "success": True,
        "secrets": secrets,
        "endpoints": sorted(endpoints, key=lambda e: e["path"]),
        "sensitive_comments": comments,
        "note": (
            "Secrets are redacted previews -- re-fetch the source_url to read the "
            "full value before filing. Endpoints are app-internal paths found in "
            "served code; probe each one (it may work while being unlinked -- "
            "security through obscurity). Nothing here is confirmed on its own."
        ),
    }


@function_tool(timeout=30, strict_mode=False)
async def scan_static_exposure(assets: list[dict[str, str]]) -> str:
    """Grep served HTML/JS for leaked secrets and hidden app endpoints.

    Use this during/after recon on the responses you have already fetched
    (HTML documents, every linked script, any source map). It does the
    exhaustive read of the front-end that is easy to skip: it returns

    - ``secrets`` -- hardcoded keys/tokens/credentials (redacted previews +
      the ``source_url`` to re-read the full value). File confirmed ones as
      sensitive-data-exposure findings.
    - ``endpoints`` -- app-internal paths (``/api``, ``/rest``, ``/admin``,
      ...) referenced from code. Probe each: one that works but is never
      linked in the UI is *security through obscurity*.
    - ``sensitive_comments`` -- TODO/FIXME/backdoor/debug comments worth a look.

    Nothing here is a finding on its own -- confirm each (read the full
    secret, hit the endpoint) before reporting.

    Args:
        assets: ``[{"url": ..., "content": ...}, ...]`` -- the main HTML and
            every script you fetched.
    """
    return json.dumps(scan_exposure(assets))
