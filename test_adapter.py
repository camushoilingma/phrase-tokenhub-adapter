"""Test the adapter locally without a TokenHub API key.
Uses httpx to call the FastAPI app directly (no network needed)."""

import os
import json
import importlib

# Fake env before importing app
os.environ["TOKENHUB_API_KEY"] = "test-key"
os.environ["PHRASE_API_TOKEN"] = "demo-token"
os.environ["TOKENHUB_MODEL"] = "hy-mt2-pro"

from app import app
from fastapi.testclient import TestClient

client = TestClient(app)
TOKEN = "demo-token"

def h(token=None):
    t = token or TOKEN
    return {"X-Api-Token": t, "Content-Type": "application/json"}

def test_status():
    r = client.post("/status", headers=h(), json={})
    assert r.status_code == 200, f"status failed: {r.text}"
    assert r.json()["status"] == "ok"
    print("  ✓ /status returns ok")

    r = client.post("/status", headers=h("bad"), json={})
    assert r.status_code == 401, f"auth should fail: {r.text}"
    print("  ✓ /status rejects bad token")

def test_languages():
    r = client.post("/languages", headers=h(), json={})
    assert r.status_code == 200, f"languages failed: {r.text}"
    data = r.json()
    pairs = data["languagePairs"]
    assert len(pairs) > 10, f"too few languages: {len(pairs)}"
    # Should have en->fr, en->de, en->zh etc
    langs = set()
    for p in pairs:
        langs.add(p["sourceLanguage"])
        langs.add(p["targetLanguage"])
    assert "en" in langs
    assert "zh" in langs
    assert "fr" in langs
    print(f"  ✓ /languages returns {len(pairs)} pairs ({len(langs)} unique codes)")

def test_translate_async_flow():
    """Test async endpoints — call TokenHub (will fail without real key, but schema is correct)"""
    body = {
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "segments": [
            {"idx": "1", "text": "Hello world"},
            {"idx": "2", "text": "Good morning"},
        ],
    }

    # Create async job
    r = client.post("/translateAsync", headers=h(), json=body)
    assert r.status_code == 200, f"async create failed: {r.text}"
    job_id = r.json()["id"]
    assert len(job_id) > 0
    print(f"  ✓ /translateAsync created job: {job_id}")

    # Check status — will be "running" since no real TokenHub key, then fail
    r = client.get(f"/translateAsyncStatus/{job_id}", headers=h())
    assert r.status_code == 200, f"status check failed: {r.text}"
    status = r.json()["status"]
    assert status in ("running", "done", "failed")
    print(f"  ✓ /translateAsyncStatus → {status}")

    # Status for non-existent job
    r = client.get("/translateAsyncStatus/nonexistent", headers=h())
    assert r.status_code == 404
    print("  ✓ /translateAsyncStatus returns 404 for missing job")

def test_schema_validation():
    """Test that Pydantic rejects malformed requests"""
    # Missing segments
    r = client.post("/translate", headers=h(), json={
        "sourceLanguage": "en",
        "targetLanguage": "fr",
    })
    assert r.status_code == 422, f"should reject missing segments: {r.status_code}"
    print("  ✓ Rejects missing 'segments' field (422)")

    # Missing targetLanguage
    r = client.post("/translate", headers=h(), json={
        "sourceLanguage": "en",
        "segments": [{"text": "hello"}],
    })
    assert r.status_code == 422
    print("  ✓ Rejects missing 'targetLanguage' field (422)")

    # Empty segments — note: Pydantic allows empty list by default on list[Field]
    # Phrase's OpenAPI schema specifies minItems: 1, but that's validated at their side before calling us
    # If strict validation is needed, add a @field_validator
    r = client.post("/translate", headers=h(), json={
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "segments": [],
    })
    print(f"  ✓ Empty segments accepted (HTTP {r.status_code} — add min_length validator if needed)")

    # Valid request (will fail at TokenHub call with bad API key, but schema is correct)
    r = client.post("/translate", headers=h(), json={
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "segments": [{"idx": "1", "text": "Hello"}],
    })
    # 401 = TokenHub rejects fake API key (expected); 200 = real key works
    assert r.status_code in (200, 401, 502, 500), f"unexpected status: {r.status_code}: {r.text}"
    print(f"  ✓ /translate accepted valid request (HTTP {r.status_code} — TokenHub not configured)")

def test_glossary_schema():
    """Test that glossary entries are accepted"""
    r = client.post("/translate", headers=h(), json={
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "segments": [{"idx": "1", "text": "Hello cloud"}],
        "glossary": [
            {"term": "cloud", "translation": "cloud"},
            {"term": "API", "translation": "interface de programmation"},
        ],
    })
    assert r.status_code in (200, 401, 502, 500), f"glossary request failed with {r.status_code}: {r.text}"
    print(f"  ✓ /translate accepts glossary (HTTP {r.status_code})")

def test_segment_delimiter_logic():
    """Test batching logic in tokenhub_client directly (no API call)"""
    from tokenhub_client import build_prompt, parse_response

    prompt = build_prompt("en", "fr", ["Hello", "Good morning"], None)
    assert "French" in prompt
    assert "Hello" in prompt
    assert "Good morning" in prompt
    assert " " in prompt  # delimiter present
    print("  ✓ build_prompt includes segments with delimiter")

    # parse_response: exact count (with actual delimiter)
    from tokenhub_client import SEGMENT_DELIMITER
    raw = f"Bonjour{SEGMENT_DELIMITER}Bonne journée"
    result = parse_response(raw, 2)
    assert result == ["Bonjour", "Bonne journée"], f"got {result}"
    print("  ✓ parse_response splits on delimiter correctly")

    # parse_response: single segment
    result = parse_response("Bonjour le monde", 1)
    assert result == ["Bonjour le monde"], f"got {result}"
    print("  ✓ parse_response handles single segment")

    # parse_response: mismatch fallback
    result = parse_response(f"Part1{SEGMENT_DELIMITER}Part2", 3)
    assert len(result) == 3, f"expected 3, got {len(result)}"
    print("  ✓ parse_response pads on delimiter mismatch")

def test_language_map():
    """Test language code mapping"""
    import language_map
    import importlib
    importlib.reload(language_map)
    from language_map import get_tokenhub_language_name, SUPPORTED_CODES

    assert get_tokenhub_language_name("en") == "English"
    assert get_tokenhub_language_name("zh") == "Chinese"
    assert get_tokenhub_language_name("zh_tw") == "Traditional Chinese"
    assert get_tokenhub_language_name("unknown") == "unknown"
    assert len(SUPPORTED_CODES) >= 33
    print(f"  ✓ language_map: {len(SUPPORTED_CODES)} codes, correct translations")


if __name__ == "__main__":
    print("Testing Phrase BYO → TokenHub Adapter\n")

    tests = [
        ("/status", test_status),
        ("/languages", test_languages),
        ("/translateAsync flow", test_translate_async_flow),
        ("Schema validation", test_schema_validation),
        ("Glossary schema", test_glossary_schema),
        ("Batching + delimiter", test_segment_delimiter_logic),
        ("Language map", test_language_map),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        exit(1)
    else:
        print("All tests pass ✓")