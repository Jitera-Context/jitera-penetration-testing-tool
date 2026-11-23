"""Tests for the black-box vulnerable-component scanner.

All logic lives in the pure ``scan_components`` helper plus the version/
fingerprint helpers, so these run with no network and no sandbox.
"""

from __future__ import annotations

from strix.jitera.tools.component_scan import (
    _cmp,
    _fingerprint,
    _in_range,
    _parse_version,
    scan_components,
)


# --- version parsing / comparison ---------------------------------------------


def test_parse_version_strips_prefix_and_suffix() -> None:
    assert _parse_version("v3.5.0") == (3, 5, 0)
    assert _parse_version("3.5.0-rc1") == (3, 5, 0)
    assert _parse_version("4.17.21+build.7") == (4, 17, 21)
    assert _parse_version("not-a-version") is None


def test_cmp_pads_shorter_tuple() -> None:
    assert _cmp((3, 5), (3, 5, 0)) == 0
    assert _cmp((3, 4, 9), (3, 5, 0)) < 0
    assert _cmp((4, 0, 0), (3, 9, 9)) > 0


def test_in_range_half_open_bounds() -> None:
    # affected when ge <= v < lt
    assert _in_range("3.4.1", ge=None, lt="3.5.0") is True
    assert _in_range("3.5.0", ge=None, lt="3.5.0") is False  # fixed version is safe
    assert _in_range("4.2.0", ge="4.0.0", lt="4.3.1") is True
    assert _in_range("3.9.9", ge="4.0.0", lt="4.3.1") is False  # below the 4.x band
    assert _in_range("unparseable", ge=None, lt="3.5.0") is False


# --- fingerprinting -----------------------------------------------------------


def test_fingerprint_reads_version_from_filename() -> None:
    found = _fingerprint("https://app/js/jquery-3.4.1.min.js", "")
    assert ("jquery", "3.4.1", "filename") in found


def test_fingerprint_reads_version_from_banner() -> None:
    banner = "/*! jQuery v3.4.1 | (c) JS Foundation */ function(){}"
    found = _fingerprint("https://app/js/vendor.js", banner)
    assert ("jquery", "3.4.1", "content-banner") in found


def test_fingerprint_lodash_license_banner() -> None:
    content = "/** @license Lodash lodash.com/license | Underscore 4.17.4 */"
    found = _fingerprint("https://app/lodash.js", content)
    assert any(lib == "lodash" and ver == "4.17.4" for lib, ver, _ in found)


# --- end-to-end scan_components ----------------------------------------------


def test_flags_vulnerable_jquery() -> None:
    out = scan_components([{"url": "https://app/js/jquery-3.4.1.min.js", "content": ""}])
    assert out["success"] is True
    cves = {v["cve"] for v in out["vulnerable"] if v["package_name"] == "jquery"}
    # 3.4.1 is < 3.5.0 (CVE-2020-11023) but >= 3.4.0 (so NOT CVE-2019-11358)
    assert "CVE-2020-11023" in cves
    assert "CVE-2019-11358" not in cves
    hit = next(v for v in out["vulnerable"] if v["cve"] == "CVE-2020-11023")
    assert hit["fixed_version"] == "3.5.0"
    assert hit["package_ecosystem"] == "npm"
    assert hit["installed_version"] == "3.4.1"
    assert hit["report_with"] == "create_dependency_report"
    assert "nvd.nist.gov" in hit["advisory_url"]


def test_current_jquery_not_flagged() -> None:
    out = scan_components([{"url": "https://app/js/jquery-3.7.1.min.js", "content": ""}])
    assert out["detected"]  # still detected...
    assert out["vulnerable"] == []  # ...but not vulnerable


def test_flags_vulnerable_lodash_prototype_pollution() -> None:
    out = scan_components(
        [{"url": "https://app/lodash.js", "content": "/** @license lodash v4.17.4 */"}]
    )
    cves = {v["cve"] for v in out["vulnerable"] if v["package_name"] == "lodash"}
    assert {"CVE-2019-10744", "CVE-2021-23337"} <= cves


def test_bootstrap_4x_band_only() -> None:
    out = scan_components([{"url": "https://app/bootstrap-4.1.0.min.js", "content": ""}])
    cves = {v["cve"] for v in out["vulnerable"]}
    assert "CVE-2019-8331" in cves
    # a fixed 4.x release is clean
    out2 = scan_components([{"url": "https://app/bootstrap-4.3.1.min.js", "content": ""}])
    assert out2["vulnerable"] == []


def test_no_duplicate_cve_across_assets() -> None:
    assets = [
        {"url": "https://app/a/jquery-3.4.1.min.js", "content": ""},
        {"url": "https://app/b/jquery-3.4.1.min.js", "content": ""},
    ]
    out = scan_components(assets)
    keys = [(v["package_name"], v["installed_version"], v["cve"]) for v in out["vulnerable"]]
    assert len(keys) == len(set(keys))


def test_empty_or_bad_input() -> None:
    assert scan_components([])["success"] is False
    assert scan_components("nope")["success"] is False  # type: ignore[arg-type]


def test_unknown_library_is_silent() -> None:
    out = scan_components([{"url": "https://app/js/supercoollib-1.0.0.js", "content": "x"}])
    assert out["success"] is True
    assert out["detected"] == []
    assert out["vulnerable"] == []
