"""Tests for the insecure-deserialization surface detector."""

from __future__ import annotations

from strix.jitera.tools.deserialization_scan import scan_serialized


def test_java_base64() -> None:
    out = scan_serialized([{"location": "cookie:session", "value": "rO0ABXNyABdqYXZh"}])
    assert out["success"] is True
    fmts = {h["format"] for h in out["serialized_values"]}
    assert "java" in fmts
    hit = next(h for h in out["serialized_values"] if h["format"] == "java")
    assert hit["location"] == "cookie:session"
    assert hit.get("payload_hint")


def test_php_object() -> None:
    out = scan_serialized(
        [{"location": "body:data", "value": 'O:4:"User":1:{s:4:"name";s:3:"bob";}'}]
    )
    assert any(h["format"] == "php" for h in out["serialized_values"])


def test_node_serialize_marker() -> None:
    val = '{"user":"_$$ND_FUNC$$_function(){return 1}()"}'
    out = scan_serialized([{"location": "body:profile", "value": val}])
    assert any(h["format"] == "node_serialize" for h in out["serialized_values"])


def test_dotnet_blob() -> None:
    out = scan_serialized([{"location": "param:state", "value": "AAEAAAD/////AQAAAAAAAAAM"}])
    assert any(h["format"] == "dotnet" for h in out["serialized_values"])


def test_ruby_marshal_base64() -> None:
    out = scan_serialized([{"location": "cookie:_app", "value": "BAhbByIKaGVsbG8"}])
    assert any(h["format"] == "ruby_marshal" for h in out["serialized_values"])


def test_plain_value_no_hit() -> None:
    out = scan_serialized([{"location": "param:q", "value": "hello world 123"}])
    assert out["success"] is True
    assert out["serialized_values"] == []


def test_dedup_same_location_format() -> None:
    val = "rO0ABXNyABdqYXZhIHJO0ABXNyABdqYXZh"  # two java markers, one location
    out = scan_serialized([{"location": "cookie:s", "value": val}])
    java = [h for h in out["serialized_values"] if h["format"] == "java"]
    assert len(java) == 1


def test_empty_or_bad_input() -> None:
    assert scan_serialized([])["success"] is False
    assert scan_serialized("nope")["success"] is False  # type: ignore[arg-type]
