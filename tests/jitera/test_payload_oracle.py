"""Tests for the deterministic injection/XSS/XXE/SSTI payload oracle."""

from __future__ import annotations

from strix.jitera.tools.payload_oracle import evaluate


# --- XSS ----------------------------------------------------------------------


def test_xss_fires_on_unescaped_reflection() -> None:
    out = evaluate("xss", "<script>xssCanary123</script>", "<div><script>xssCanary123</script></div>")
    assert out["success"] and out["fired"] is True
    assert out["reflected"] is True
    assert out["encoded_only"] is False


def test_xss_not_fired_when_encoded() -> None:
    body = "<div>&lt;script&gt;xssCanary123&lt;/script&gt;</div>"
    out = evaluate("xss", "<script>xssCanary123</script>", body)
    assert out["fired"] is False
    assert out["reflected"] is True
    assert out["encoded_only"] is True


def test_xss_not_reflected() -> None:
    out = evaluate("xss", "<script>xssCanary123</script>", "nothing here")
    assert out["fired"] is False
    assert out["reflected"] is False


# --- SQLi (error-based) -------------------------------------------------------


def test_sqli_error_mysql() -> None:
    body = "Error: You have an error in your SQL syntax near '''"
    out = evaluate("sqli_error", "' OR 1=1--", body)
    assert out["fired"] is True
    assert out["signature"] == "mysql"


def test_sqli_error_none() -> None:
    out = evaluate("sqli_error", "' OR 1=1--", "normal page content")
    assert out["fired"] is False


# --- SSTI ---------------------------------------------------------------------


def test_ssti_evaluated() -> None:
    out = evaluate("ssti", "{{7*7}}", "Result is 49 today")
    assert out["fired"] is True
    assert out["evidence"] == "49"


def test_ssti_echoed_verbatim_not_fired() -> None:
    out = evaluate("ssti", "{{7*7}}", "You searched for {{7*7}} (49 matches)")
    # raw expr echoed -> template did NOT evaluate it
    assert out["fired"] is False


def test_ssti_no_marker() -> None:
    out = evaluate("ssti", "hello", "world")
    assert out["fired"] is False


# --- XXE / LFI / path traversal ----------------------------------------------


def test_xxe_reads_passwd() -> None:
    body = "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:"
    out = evaluate("xxe", "<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>", body)
    assert out["fired"] is True
    assert out["signature"] == "unix_passwd"


def test_lfi_windows_ini() -> None:
    out = evaluate("lfi", "../../../../windows/win.ini", "[fonts]\n[extensions]\n")
    assert out["fired"] is True
    assert out["signature"] == "windows_ini"


def test_file_read_none() -> None:
    out = evaluate("path_traversal", "../../etc/passwd", "404 not found")
    assert out["fired"] is False


# --- open redirect ------------------------------------------------------------


def test_open_redirect_via_location_header() -> None:
    out = evaluate(
        "open_redirect", "https://evil.example", "", {"Location": "https://evil.example/landing"}
    )
    assert out["fired"] is True
    assert "evil.example" in out["evidence"]


def test_open_redirect_via_meta_refresh() -> None:
    body = '<meta http-equiv="refresh" content="0;url=https://evil.example/x">'
    out = evaluate("open_redirect", "https://evil.example", body)
    assert out["fired"] is True


def test_open_redirect_same_site_not_fired() -> None:
    out = evaluate("open_redirect", "https://evil.example", "", {"Location": "/dashboard"})
    assert out["fired"] is False


# --- misc ---------------------------------------------------------------------


def test_unknown_class_errors() -> None:
    out = evaluate("telepathy", "x", "y")
    assert out["success"] is False
