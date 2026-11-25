"""``check_payload_fired`` -- deterministic oracle for injection/XSS/XXE/SSTI.

The evidence from Juice Shop scans: the agent *attempts* XSS and XXE but files
almost nothing, because a weak model is unreliable at judging whether a response
actually proves the payload fired. It second-guesses a real reflection or accepts
a non-result. This tool makes that judgment deterministic: give it the class, the
payload you sent and the response you got back, and it returns a yes/no verdict
with the exact evidence span, so the agent can file (or drop) with confidence.

It is an *oracle*, not a scanner -- it does not send traffic. The agent sends the
request with its existing HTTP/browser tools, then passes the response here.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from agents import function_tool


# known database error signatures -> engine (SQL injection, error-based)
_SQL_ERRORS: list[tuple[str, re.Pattern[str]]] = [
    (
        "mysql",
        re.compile(
            r"You have an error in your SQL syntax|MySQL server version|valid MySQL result|mysqli?_",  # noqa: E501
            re.I,
        ),
    ),
    (
        "postgres",
        re.compile(r"PostgreSQL.*ERROR|PG::\w+Error|pg_query\(\)|unterminated quoted string", re.I),
    ),
    (
        "sqlite",
        re.compile(
            r"SQLITE_ERROR|sqlite3?\.OperationalError|SQL logic error|unrecognized token", re.I
        ),
    ),
    ("oracle", re.compile(r"ORA-\d{5}|Oracle error|quoted string not properly terminated", re.I)),
    (
        "mssql",
        re.compile(r"Unclosed quotation mark|Microsoft SQL Server|System\.Data\.SqlClient", re.I),
    ),
]

# file-content markers that prove a file read landed (XXE / LFI / path traversal)
_FILE_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    ("unix_passwd", re.compile(r"root:.*?:0:0:", re.M)),
    ("windows_ini", re.compile(r"\[(?:fonts|extensions|mci extensions)\]", re.I)),
    ("php_source", re.compile(r"<\?php\b")),
    ("ssh_private_key", re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")),
]


def _xss_verdict(payload: str, body: str) -> dict[str, Any]:
    """Reflected-XSS oracle: did the payload's markup survive unescaped?

    It fires only when the payload's dangerous construct (a tag, an event-handler
    attribute, or a ``javascript:`` URI) appears verbatim in the body. If the
    same payload appears only HTML-entity-encoded, it is reflected but not
    exploitable (``encoded_only``).
    """
    has_markup = bool(
        re.search(r"[<>]", payload)
        or re.search(r"on\w+\s*=", payload, re.I)
        or "javascript:" in payload.lower()
    )
    raw_full = payload in body
    enc_full = (not raw_full) and html.escape(payload, quote=True) in body

    # an alphanumeric canary, to still report "reflected" when neither form matches
    canaries = re.findall(r"[a-zA-Z0-9_]{6,}", payload)
    marker = next(
        (c for c in canaries if c.lower().startswith("xss") or "canary" in c.lower()), None
    )
    canary_hit = bool(marker) and marker in body

    fired = raw_full and has_markup
    encoded_only = enc_full or (canary_hit and not raw_full and has_markup)
    reflected = raw_full or enc_full or canary_hit
    reason = (
        "payload markup reflected unescaped in an executable context"
        if fired
        else "reflected but HTML-encoded (not exploitable)"
        if encoded_only
        else "payload reflected without its markup"
        if reflected
        else "payload not reflected"
    )
    return {
        "fired": bool(fired),
        "reflected": bool(reflected),
        "encoded_only": bool(encoded_only),
        "evidence": payload
        if raw_full
        else (html.escape(payload, quote=True) if enc_full else (marker if canary_hit else None)),
        "reason": reason,
    }


def _ssti_verdict(payload: str, body: str) -> dict[str, Any]:
    """SSTI oracle: an arithmetic marker evaluated server-side.

    Expects a payload containing a product like ``7*7`` (``{{7*7}}``,
    ``${7*7}``, ``#{7*7}`` ...). Fires if the product appears in the body while
    the raw expression does not (i.e. it was evaluated, not echoed).
    """
    m = re.search(r"(\d{1,4})\s*\*\s*(\d{1,4})", payload)
    if not m:
        return {"fired": False, "reason": "payload has no N*N marker to evaluate"}
    product = str(int(m.group(1)) * int(m.group(2)))
    raw_expr = m.group(0).replace(" ", "")
    body_nospace = body.replace(" ", "")
    evaluated = product in body and raw_expr not in body_nospace
    return {
        "fired": bool(evaluated),
        "evidence": product if evaluated else None,
        "reason": (
            f"template evaluated {raw_expr} to {product}"
            if evaluated
            else "expression echoed verbatim or absent (not evaluated)"
        ),
    }


def _redirect_verdict(payload: str, body: str, headers: dict[str, str]) -> dict[str, Any]:
    """Open-redirect oracle: does Location / meta-refresh point at the payload host?"""
    host = re.sub(r"^https?://", "", payload).split("/")[0].strip()
    loc = ""
    for k, v in (headers or {}).items():
        if k.lower() == "location":
            loc = v
            break
    meta = re.search(r'http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)', body, re.I)
    target = loc or (meta.group(1) if meta else "")
    fired = bool(host) and host in target and target.startswith(("http", "//"))
    return {
        "fired": bool(fired),
        "evidence": target or None,
        "reason": f"redirects off-site to {target}"
        if fired
        else "no off-site redirect to the payload host",
    }


def _marker_verdict(
    body: str, markers: list[tuple[str, re.Pattern[str]]], kind: str
) -> dict[str, Any]:
    for name, pat in markers:
        m = pat.search(body)
        if m:
            return {
                "fired": True,
                "signature": name,
                "evidence": m.group(0)[:120],
                "reason": f"{kind}: matched {name}",
            }
    return {"fired": False, "reason": f"no {kind} signature in response"}


# vuln_class -> oracle name used in docs/tests
_CLASSES = {"xss", "sqli_error", "ssti", "xxe", "lfi", "path_traversal", "open_redirect"}


def evaluate(
    vuln_class: str,
    payload: str,
    response_body: str,
    response_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Pure logic of :func:`check_payload_fired`."""
    cls = (vuln_class or "").strip().lower()
    body = response_body or ""
    if cls not in _CLASSES:
        return {
            "success": False,
            "error": f"unknown vuln_class '{vuln_class}'; expected one of {sorted(_CLASSES)}",
        }

    if cls == "xss":
        verdict = _xss_verdict(payload, body)
    elif cls == "sqli_error":
        verdict = _marker_verdict(body, _SQL_ERRORS, "sql-error")
    elif cls == "ssti":
        verdict = _ssti_verdict(payload, body)
    elif cls in ("xxe", "lfi", "path_traversal"):
        verdict = _marker_verdict(body, _FILE_MARKERS, "file-read")
    elif cls == "open_redirect":
        verdict = _redirect_verdict(payload, body, response_headers or {})
    else:  # pragma: no cover - guarded by _CLASSES
        verdict = {"fired": False, "reason": "unhandled"}

    return {"success": True, "vuln_class": cls, **verdict}


@function_tool(timeout=20, strict_mode=False)
async def check_payload_fired(
    vuln_class: str,
    payload: str,
    response_body: str,
    response_headers: dict[str, str] | None = None,
) -> str:
    """Decide, deterministically, whether an injection payload actually fired.

    Send the request yourself (HTTP/browser tools), then pass what came back
    here. The oracle returns ``fired`` (true/false) plus the exact evidence span
    and a reason -- so you file a finding only on a real hit and stop
    second-guessing genuine ones.

    Supported ``vuln_class`` values and what each looks for:
    - ``xss`` -- a canary from the payload reflected *unescaped* in an executable
      context (HTML-entity-encoded reflection returns fired=false, encoded_only=true).
    - ``sqli_error`` -- a database error signature (MySQL/Postgres/SQLite/Oracle/MSSQL).
    - ``ssti`` -- an arithmetic marker like ``{{7*7}}`` evaluated to ``49`` in the body.
    - ``xxe`` / ``lfi`` / ``path_traversal`` -- a file-content marker
      (``/etc/passwd``, ``win.ini``, PHP source, a private key) in the response.
    - ``open_redirect`` -- Location/meta-refresh pointing off-site to the payload host.

    Use a distinctive canary in XSS payloads (e.g. ``xss<token>``) so the oracle
    can key on it. A false verdict means the evidence does not prove impact, not
    that the class is absent -- try another payload or vector.

    Args:
        vuln_class: One of xss, sqli_error, ssti, xxe, lfi, path_traversal, open_redirect.
        payload: The exact payload you sent.
        response_body: The response body you got back.
        response_headers: Response headers (needed for open_redirect).
    """
    return json.dumps(evaluate(vuln_class, payload, response_body, response_headers))
