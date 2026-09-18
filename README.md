# Phrase BYO Engine → Tencent TokenHub HY-MT2 Adapter

A lightweight proxy that translates [Phrase's BYO Engine API](https://developers.phrase.com/en/guides/byo-engine/introduction) into [Tencent TokenHub HY-MT2](https://www.tencentcloud.com/document/product/1300/80695) chat completions calls.

## Quick Start

```bash
# 1. Configure credentials
cp .env.example .env
# Edit .env with your TokenHub API key and a Phrase auth token

# 2. Start
docker compose up
```

The adapter runs on `http://localhost:8000`.

## Endpoints

Implements all 6 [BYO Engine API](https://developers.phrase.com/public/assets/openapi/phrase-byo-mt.yaml) endpoints:

| Endpoint | Description |
|---|---|
| `POST /status` | Engine health check |
| `POST /languages` | Supported language pairs (33 languages, 1056 pairs) |
| `POST /translate` | Synchronous translation (1-500 segments) |
| `POST /translateAsync` | Submit async translation job |
| `GET /translateAsyncStatus/{id}` | Poll job status |
| `GET /translateAsyncResult/{id}` | Get completed translation |

## Authentication

- **Phrase → Adapter**: `X-Api-Token` header (set via `PHRASE_API_TOKEN` env var)
- **Adapter → TokenHub**: `Authorization: Bearer` (set via `TOKENHUB_API_KEY` env var)

## Supported Languages

HY-MT2 supports 33 languages: `en, zh, zh_tw, fr, de, es, ja, ko, pt, it, ru, ar, th, tr, vi, ms, id, fil, hi, pl, cs, nl, km, my, fa, gu, ur, te, mr, he, bn, ta, uk`

## Features

- **Glossary support**: Ad-hoc glossaries injected into the translation prompt
- **Batch translation**: Multiple segments batched in one TokenHub request using `###` delimiter
- **Async jobs**: In-memory storage (production deployments should use Redis)

## Architecture

```
Phrase ──HTTPS──▶ Adapter (this service) ──HTTPS──▶ TokenHub HY-MT2
                       │
                       └── Schema transformation
                           ├── Phrase locale code → TokenHub language name
                           ├── Segments + glossary → LLM prompt
                           └── TokenHub response → Phrase response schema
```

## Phrase Validation

After deploying to a public HTTPS URL:

1. **Phrase TMS** → **Phrase Language AI** → **Create MT profile** → **Connect MT** → **Bring Your Own Engine**
2. Fill in: Base URL (your adapter URL), Auth (API Key → your `PHRASE_API_TOKEN`)
3. Click **Validate** — Phrase tests all 6 endpoints automatically

## Configuration

| Env var | Required | Default |
|---|---|---|
| `TOKENHUB_API_KEY` | Yes | — |
| `TOKENHUB_BASE_URL` | No | `https://tokenhub-intl.tencentcloudmaas.com/v1` |
| `TOKENHUB_MODEL` | No | `hy-mt2-pro` |
| `PHRASE_API_TOKEN` | Yes | — |
| `REDIS_URL` | No | (in-memory fallback) |

## Running Tests

```bash
pip install -r requirements.txt
python3 test_adapter.py
```

## License

MIT