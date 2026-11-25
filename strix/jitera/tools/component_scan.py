"""``detect_vulnerable_components`` -- black-box SCA for a running web app.

Upstream's ``custom/dependency_cve_scanning`` skill matches known CVEs against
*lockfiles* (``trivy fs`` on a repo). That is white-box only; against a running
target with no source we see just the JavaScript the app serves. This tool fills
that gap: give it the HTML/JS the agent already fetched, and it extracts each
client-side library and version it can fingerprint, then matches them against a
curated table of well-known, high-confidence client-side CVEs.

The LLM is unreliable at version->CVE matching (it misremembers affected ranges
and fixed versions); this does it deterministically. It never guesses -- a
component is only reported when a concrete version was extracted and that version
falls inside a known-vulnerable range. The agent then files each hit with
``create_dependency_report`` (the SCA exception to the dynamic-PoC rule).
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents import function_tool


# --- version comparison (pure stdlib, no new dependency) ----------------------


def _parse_version(v: str) -> tuple[int, ...] | None:
    """Return the numeric release tuple of a dotted version, or None.

    Pre-release/build suffixes (``-beta``, ``+build``) are dropped before the
    numeric parts are read, so ``3.5.0-rc1`` compares as ``(3, 5, 0)``.
    """
    v = v.strip().lstrip("vV")
    v = re.split(r"[-+]", v, maxsplit=1)[0]
    parts = v.split(".")
    out: list[int] = []
    for p in parts:
        if not p.isdigit():
            break
        out.append(int(p))
    return tuple(out) if out else None


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    """Compare two release tuples, padding the shorter with zeros."""
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def _in_range(version: str, *, ge: str | None, lt: str | None) -> bool:
    """True when ``ge <= version < lt`` for the bounds that are given."""
    ver = _parse_version(version)
    if ver is None:
        return False
    if ge is not None:
        lo = _parse_version(ge)
        if lo is not None and _cmp(ver, lo) < 0:
            return False
    if lt is not None:
        hi = _parse_version(lt)
        if hi is not None and _cmp(ver, hi) >= 0:
            return False
    return True


# --- fingerprints: how to read a library + version out of served JS -----------

# Each entry: library key -> list of regex patterns whose first group is the
# version. Patterns match the banners/markers these libraries ship in their
# distributed files, plus versioned filenames like ``jquery-3.4.1.min.js``.
_FINGERPRINTS: dict[str, list[re.Pattern[str]]] = {
    "jquery": [
        re.compile(r"/\*!\s*jQuery\s+v(\d+\.\d+\.\d+)", re.I),
        re.compile(r"jquery[.-](\d+\.\d+\.\d+)(?:\.min)?\.js", re.I),
        re.compile(r'jquery\.fn\.jquery\s*=\s*["\'](\d+\.\d+\.\d+)', re.I),
    ],
    "lodash": [
        re.compile(r"@license\s+[Ll]odash[^\n]*?v?(\d+\.\d+\.\d+)", re.I),
        re.compile(r"lodash[.-](\d+\.\d+\.\d+)(?:\.min)?\.js", re.I),
        re.compile(r'VERSION\s*=\s*["\'](\d+\.\d+\.\d+)["\'][^\n]*lodash', re.I),
    ],
    "angularjs": [
        re.compile(r"@license\s+AngularJS\s+v(\d+\.\d+\.\d+)", re.I),
        re.compile(r"angular[.-](\d+\.\d+\.\d+)(?:\.min)?\.js", re.I),
    ],
    "bootstrap": [
        re.compile(r"/\*!\s*Bootstrap\s+v(\d+\.\d+\.\d+)", re.I),
        re.compile(r"bootstrap[.-](\d+\.\d+\.\d+)(?:\.min)?\.(?:js|css)", re.I),
    ],
    "moment": [
        re.compile(r"//!\s*moment\.js\s+version\s*:\s*(\d+\.\d+\.\d+)", re.I),
        re.compile(r"moment[.-](\d+\.\d+\.\d+)(?:\.min)?\.js", re.I),
    ],
    "handlebars": [
        re.compile(r"Handlebars\.VERSION\s*=\s*[\"'](\d+\.\d+\.\d+)", re.I),
        re.compile(r"handlebars[.-](\d+\.\d+\.\d+)(?:\.min)?\.js", re.I),
    ],
}

# --- curated vulnerable-version table (high-confidence, well-documented) -------

# Each: library -> list of advisories. ``ge``/``lt`` bound the affected range
# (half-open: ge <= v < lt). Kept conservative on purpose -- a false SCA finding
# is worse than a missed one.
_ADVISORIES: dict[str, list[dict[str, Any]]] = {
    "jquery": [
        {
            "ge": None,
            "lt": "3.5.0",
            "cve": "CVE-2020-11023",
            "cvss": 6.1,
            "cwe": "CWE-79",
            "fixed": "3.5.0",
            "summary": "XSS via <option> passed to DOM-manipulation methods (htmlPrefilter).",
        },
        {
            "ge": None,
            "lt": "3.4.0",
            "cve": "CVE-2019-11358",
            "cvss": 6.1,
            "cwe": "CWE-1321",
            "fixed": "3.4.0",
            "summary": "Prototype pollution in jQuery.extend(true, ...).",
        },
        {
            "ge": None,
            "lt": "1.9.0",
            "cve": "CVE-2012-6708",
            "cvss": 6.1,
            "cwe": "CWE-79",
            "fixed": "1.9.0",
            "summary": "Selector-interpreted-as-HTML XSS in $() location.hash sinks.",
        },
    ],
    "lodash": [
        {
            "ge": None,
            "lt": "4.17.21",
            "cve": "CVE-2021-23337",
            "cvss": 7.2,
            "cwe": "CWE-94",
            "fixed": "4.17.21",
            "summary": "Command injection via lodash template().",
        },
        {
            "ge": None,
            "lt": "4.17.12",
            "cve": "CVE-2019-10744",
            "cvss": 9.1,
            "cwe": "CWE-1321",
            "fixed": "4.17.12",
            "summary": "Prototype pollution in defaultsDeep/merge.",
        },
    ],
    "angularjs": [
        {
            "ge": None,
            "lt": "1.8.0",
            "cve": "CVE-2020-7676",
            "cvss": 6.1,
            "cwe": "CWE-79",
            "fixed": "1.8.0",
            "summary": "angular.element XSS via <option> / srcset sanitizer bypass.",
        },
    ],
    "bootstrap": [
        {
            "ge": "4.0.0",
            "lt": "4.3.1",
            "cve": "CVE-2019-8331",
            "cvss": 6.1,
            "cwe": "CWE-79",
            "fixed": "4.3.1",
            "summary": "XSS in tooltip/popover data-template (4.x).",
        },
        {
            "ge": None,
            "lt": "3.4.1",
            "cve": "CVE-2019-8331",
            "cvss": 6.1,
            "cwe": "CWE-79",
            "fixed": "3.4.1",
            "summary": "XSS in tooltip/popover data-template (3.x).",
        },
    ],
    "moment": [
        {
            "ge": None,
            "lt": "2.29.4",
            "cve": "CVE-2022-31129",
            "cvss": 7.5,
            "cwe": "CWE-1333",
            "fixed": "2.29.4",
            "summary": "ReDoS in moment parsing of long strings.",
        },
    ],
    "handlebars": [
        {
            "ge": None,
            "lt": "4.7.7",
            "cve": "CVE-2021-23369",
            "cvss": 9.8,
            "cwe": "CWE-1321",
            "fixed": "4.7.7",
            "summary": "RCE via prototype pollution when compiling untrusted templates.",
        },
    ],
}

# Common distribution page / registry for each ecosystem member.
_ADVISORY_URL = "https://nvd.nist.gov/vuln/detail/{cve}"


def _fingerprint(url: str, content: str) -> list[tuple[str, str, str]]:
    """Return ``(library, version, how)`` for every lib/version read from one asset."""
    found: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    haystacks = ((url or "", "filename"), (content or "", "content-banner"))
    for lib, patterns in _FINGERPRINTS.items():
        for text, how in haystacks:
            if not text:
                continue
            for pat in patterns:
                m = pat.search(text)
                if m:
                    version = m.group(1)
                    key = (lib, version)
                    if key not in seen:
                        seen.add(key)
                        found.append((lib, version, how))
                    break
    return found


def _advisories_for(lib: str, version: str) -> list[dict[str, Any]]:
    return [
        adv
        for adv in _ADVISORIES.get(lib, [])
        if _in_range(version, ge=adv.get("ge"), lt=adv.get("lt"))
    ]


def scan_components(assets: list[dict[str, str]]) -> dict[str, Any]:
    """Pure logic of :func:`detect_vulnerable_components` (no I/O, easy to test).

    Returns ``{"success": bool, ...}`` -- the tool wrapper just JSON-encodes it.
    """
    if not isinstance(assets, list) or not assets:
        return {"success": False, "error": "assets must be a non-empty list of {url, content}"}

    detected: list[dict[str, Any]] = []
    vulnerable: list[dict[str, Any]] = []
    seen_vuln: set[tuple[str, str, str]] = set()

    for item in assets:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "") or "")
        content = str(item.get("content", "") or "")
        for lib, version, how in _fingerprint(url, content):
            detected.append(
                {"library": lib, "version": version, "source_url": url, "detected_via": how}
            )
            for adv in _advisories_for(lib, version):
                key = (lib, version, adv["cve"])
                if key in seen_vuln:
                    continue
                seen_vuln.add(key)
                vulnerable.append(
                    {
                        "package_name": lib,
                        "package_ecosystem": "npm",
                        "installed_version": version,
                        "cve": adv["cve"],
                        "advisory_cvss": adv["cvss"],
                        "cwe": adv["cwe"],
                        "fixed_version": adv["fixed"],
                        "summary": adv["summary"],
                        "advisory_url": _ADVISORY_URL.format(cve=adv["cve"]),
                        "source_url": url,
                        "detected_via": how,
                        "report_with": "create_dependency_report",
                    }
                )

    return {
        "success": True,
        "detected": detected,
        "vulnerable": vulnerable,
        "note": (
            "File each 'vulnerable' entry with create_dependency_report "
            "(the SCA exception to the dynamic-PoC rule). An empty list is "
            "not proof the app is free of vulnerable components."
        ),
    }


@function_tool(timeout=30, strict_mode=False)
async def detect_vulnerable_components(assets: list[dict[str, str]]) -> str:
    """Fingerprint client-side libraries in served HTML/JS and flag known CVEs.

    This is black-box SCA: it works from the responses a running target serves,
    so use it when you have no repository/lockfile. Collect the target's HTML and
    its linked JavaScript (via the browser or ``repeat_request``), then pass them
    here. Every component whose extracted version falls in a known-vulnerable
    range comes back with its CVE, CVSS, CWE and fixed version -- file each one
    with ``create_dependency_report`` (package_ecosystem="npm"), citing the asset
    URL and the detected version as the proof.

    It never guesses: a library is only reported when a concrete version was read
    from a banner or a versioned filename and that version matches an advisory.
    An empty ``vulnerable`` list means nothing matched, not that the app is clean
    -- it only knows the handful of common libraries it fingerprints.

    Args:
        assets: The fetched responses to analyse. Each item is
            ``{"url": "<asset url>", "content": "<response body>"}``. Pass the
            main HTML document and every linked script you retrieved.
    """
    return json.dumps(scan_components(assets))
