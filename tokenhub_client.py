import os
import json
from typing import Optional, List, Dict

import httpx
from language_map import get_tokenhub_language_name

TOKENHUB_API_KEY = os.getenv("TOKENHUB_API_KEY", "")
TOKENHUB_BASE_URL = os.getenv("TOKENHUB_BASE_URL", "https://tokenhub-intl.tencentcloudmaas.com/v1")
TOKENHUB_MODEL = os.getenv("TOKENHUB_MODEL", "hy-mt2-pro")

SEGMENT_DELIMITER = "###"  # TokenHub-recommended delimiter for batch translation


def build_prompt(source_lang: str, target_lang: str, segments: List[str], glossary: Optional[List[Dict]]) -> str:
    """Construct the full translation prompt for TokenHub."""
    target_name = get_tokenhub_language_name(target_lang)

    parts = []

    # Glossary injected into prompt (MT2-Pro doesn't support dedicated glossary API)
    if glossary:
        parts.append("Refer to the translation below:")
        for entry in glossary:
            parts.append(f"{entry['term']} translated into {entry['translation']}")
        parts.append("")

    # Translation instruction + batched segments
    joined = SEGMENT_DELIMITER.join(segments)
    parts.append(
        f"Translate the following text into {target_name}. "
        f"The text contains multiple segments separated by the delimiter '{SEGMENT_DELIMITER}'. "
        f"Keep exactly the same number of '{SEGMENT_DELIMITER}' delimiters in the output. "
        "Do not omit, escape, or translate the delimiter. "
        "Note: Output only the translated result without any additional explanation:"
    )
    parts.append("")
    parts.append(joined)

    return "\n".join(parts)


def parse_response(raw_response: str, segment_count: int) -> List[str]:
    """Split TokenHub response back into individual translated segments."""
    parts = raw_response.split(SEGMENT_DELIMITER)

    # If delimiter count matches, return as-is
    if len(parts) == segment_count:
        return [p.strip() for p in parts]

    # Fallback: if we got a different number, return the whole response as one segment
    # (the model may have merged/dropped delimiters)
    if segment_count == 1:
        return [raw_response.strip()]

    # Last resort: try to align
    result = []
    for i in range(segment_count):
        if i < len(parts):
            result.append(parts[i].strip())
        else:
            result.append("")
    return result


def translate_sync(
    source_lang: str,
    target_lang: str,
    segments: List[Dict],
    glossary: Optional[List[Dict]] = None,
) -> dict:
    """Translate segments synchronously via TokenHub. Returns full Phrase response dict."""
    source_texts = [s["text"] for s in segments]
    prompt = build_prompt(source_lang, target_lang, source_texts, glossary)

    payload = {
        "model": TOKENHUB_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = httpx.post(
        f"{TOKENHUB_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {TOKENHUB_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    body = response.json()

    raw = body["choices"][0]["message"]["content"]
    translated_texts = parse_response(raw, len(source_texts))

    translated_segments = []
    for i, seg in enumerate(segments):
        translated_segments.append({
            "idx": seg.get("idx"),
            "text": seg["text"],
            "translatedText": translated_texts[i] if i < len(translated_texts) else "",
            "metadata": seg.get("metadata"),
        })

    return translated_segments