---
name: payload-confirmation
description: Confirm injection/XSS/XXE/SSTI payloads deterministically with check_payload_fired before filing -- stop dropping real hits and stop filing non-hits
---

# Confirming injection payloads

Scans of this target repeatedly *attempt* XSS and XXE yet file nothing, because
judging "did that payload actually fire?" from a raw response is error-prone.
Do not eyeball it. For every injection probe, send the request with your HTTP or
browser tools, then pass the result to `check_payload_fired` and act on its
verdict.

## Procedure

1. **Send a probe with a distinctive marker.**
   - XSS: embed a canary, e.g. `"><script>xssCANARY1</script>` or
     `xssCANARY1` in an attribute/JS context.
   - SSTI: an arithmetic marker, `{{7*7}}` / `${7*7}` / `#{7*7}`.
   - XXE: an external-entity doc reading `file:///etc/passwd` (or `win.ini`).
   - SQLi: a quote-breaking payload; look for DB errors.
   - Open redirect: a `?redirect=https://<your-canary-host>` style value.
2. **Call `check_payload_fired`** with `vuln_class`, the exact `payload`, the
   `response_body` (and `response_headers` for open_redirect). It returns:
   - `fired: true` with an `evidence` span -> you have proof; file it.
   - `fired: false` with a `reason` -> not proven; for XSS note `encoded_only`
     (the sink escapes output -> try a different context/parameter, don't file).
3. **File on a real hit** with `create_vulnerability_report`, quoting the
   `evidence` span and the request/response as the PoC.

## Why trust the oracle

- **XSS**: fires only when the canary survives **unescaped** in an executable
  context; an HTML-entity-encoded reflection returns `fired=false,
  encoded_only=true` (correctly not exploitable).
- **SSTI**: fires only when `7*7` shows up as `49` **and** the raw expression is
  not merely echoed back.
- **XXE/LFI**: fires only on real file-content markers (`root:...:0:0:`,
  `[fonts]`, PHP source, a private-key header).

A `false` verdict means *this* evidence does not prove impact -- change the
vector and probe again; it is not proof the class is absent.
