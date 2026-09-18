# Phrase BYO → TokenHub HY-MT2 Adapter Specification

## Architecture

```
Phrase (cloud) ──HTTPS──▶ Adapter (Tencent Cloud) ──HTTPS──▶ TokenHub HY-MT2 (Singapore)
                              │
                              ├── Redis (async job state, production only)
                              └── in-memory cache (POC/dev)
```

Two auth layers:
- **Phrase → Adapter**: `X-Api-Token` header (simple) or OAuth2 client credentials
- **Adapter → TokenHub**: `Authorization: Bearer <TOKENHUB_API_KEY>`

## Endpoints

### 1. POST /status
Returns adapter health. Optionally probe TokenHub health if you want.

**Request** (Phrase sends, body optional):
```json
{}
```

**Response**:
```json
{"status": "ok"}
```
→ `ok` = fully operational, `not_ok` = not ready

### 2. POST /languages
Returns all supported source→target pairs using Phrase locale codes (e.g. `en`, `zh`).

**Request**:
```json
{}
```

**Response**:
```json
{
  "languagePairs": [
    {"sourceLanguage": "en", "targetLanguage": "fr"},
    {"sourceLanguage": "en", "targetLanguage": "de"},
    ...
  ]
}
```

Supported: 33 languages × 32 targets = 1056 pairs. Use top-level codes (`en` not `en_us`) to keep response size manageable.

### 3. POST /translate (synchronous)
The main endpoint. Phrase sends 1-500 segments + optional glossary.

**Request**:
```json
{
  "sourceLanguage": "en",
  "targetLanguage": "fr",
  "segments": [
    {"idx": "1", "text": "Hello world"},
    {"idx": "2", "text": "Good morning"}
  ],
  "glossary": [
    {"term": "cloud", "translation": "cloud"}
  ],
  "metadata": {"formality": "formal"}
}
```

- `segments`: 1–500 items. `idx` must be preserved in response.
- `glossary`: 0–500 term/translation pairs. Inject into prompt for MT2-Pro.
- `metadata`: optional key/value passthrough. Phrase resolves `{project_uid}`, `{job_uid}`, `{idm_organization_uid}`.

**Response** (same structure, add `translatedText`):
```json
{
  "sourceLanguage": "en",
  "targetLanguage": "fr",
  "segments": [
    {"idx": "1", "text": "Hello world", "translatedText": "Bonjour le monde"},
    {"idx": "2", "text": "Good morning", "translatedText": "Bonjour"}
  ],
  "metadata": {"formality": "formal"}
}
```

### 4. POST /translateAsync
Same request body as `/translate`. Returns a job ID immediately (200ms or less).

**Response**:
```json
{"id": "550e8400-e29b-41d4-a716-446655440000"}
```

### 5. GET /translateAsyncStatus/{id}
Poll for job completion.

**Response**:
```json
{"status": "running"}
```
```json
{"status": "done", "detail": "completed successfully"}
```
```json
{"status": "failed", "detail": "TokenHub timeout after 30s"}
```

### 6. GET /translateAsyncResult/{id}
Retrieve completed translation. Same schema as POST /translate response.

---

## TokenHub Mapping

### TokenHub API call
```
POST https://tokenhub-intl.tencentcloudmaas.com/v1/chat/completions
Authorization: Bearer <TOKENHUB_API_KEY>
Content-Type: application/json
```

Models: `hy-mt2-pro` (30B MoE, highest quality), `hy-mt2-plus` (7B), `hy-mt2-lite` (1.8B)
Context: 8K window, max 4K input, max 4K output

### Translation prompt template (no glossary)
```
Translate the following text into {target_lang_name}.
Note: Output only the translated result without any additional explanation:
{source_text}
```

### Translation prompt template (with glossary)
```
Refer to the translation below:
{term1} translated into {translation1}
{term2} translated into {translation2}
...

Translate the following text into {target_lang_name}.
Note: Output only the translated result without any additional explanation:
{source_text}
```

### Batching multiple segments
Use a delimiter that won't appear in translations. TokenHub docs recommend ` ` or `###`.

Concatenate segments:
```
{segment1}<SEP>{segment2}<SEP>{segment3}
```

Parse TokenHub response by splitting on the delimiter. Use robust fallback if count mismatch.

### TokenHub response format
```json
{
  "id": "...",
  "model": "hy-mt2-pro",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Bonjour le monde"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 26,
    "completion_tokens": 28,
    "total_tokens": 54
  }
}
```

Extract: `response.choices[0].message.content`

---

## Language Code Mapping

Phrase uses ISO-like locale codes; TokenHub expects full language names in the prompt.

| Phrase code | TokenHub name | TokenHub code |
|---|---|---|
| en | English | en |
| zh | Chinese | zh |
| zh_tw | Traditional Chinese | zh-TR |
| fr | French | fr |
| de | German | de |
| es | Spanish | es |
| ja | Japanese | ja |
| ko | Korean | ko |
| pt | Portuguese | pt |
| it | Italian | it |
| ru | Russian | ru |
| ar | Arabic | ar |
| th | Thai | th |
| tr | Turkish | tr |
| vi | Vietnamese | vi |
| ms | Malay | ms |
| id | Indonesian | id |
| fil | Filipino | fil |
| hi | Hindi | hi |
| pl | Polish | pl |
| cs | Czech | cs |
| nl | Dutch | nl |
| km | Khmer | km |
| my | Burmese | my |
| fa | Persian | fa |
| gu | Gujarati | gu |
| ur | Urdu | ur |
| te | Telugu | te |
| mr | Marathi | mr |
| he | Hebrew | he |
| bn | Bengali | bn |
| ta | Tamil | ta |
| uk | Ukrainian | uk |
| bo | Tibetan | bo |
| kk | Kazakh | kk |
| mn | Mongolian | mn |
| ug | Uyghur | ug |
| yue | Cantonese | yue |

---

## Error Handling

Phrase expects:
- `200` on success with correct schema
- `429` with `Retry-After` header on rate limiting
- `4xx`/`5xx` with `{"error": "message"}` on failure

TokenHub errors (auth failure, model unavailable, content filtered) should be translated into appropriate Phrase error responses.

---

## Configuration (env vars)

```
TOKENHUB_API_KEY=sk-...
TOKENHUB_BASE_URL=https://tokenhub-intl.tencentcloudmaas.com/v1
TOKENHUB_MODEL=hy-mt2-pro
PHRASE_API_TOKEN=phrase-...       (optional, validate X-Api-Token header)
REDIS_URL=redis://...             (production only, for async job storage)
```

---

## Implementation Plan

1. **FastAPI app** with 6 route handlers
2. **Pydantic models** matching Phrase schemas
3. **Language mapper** — Phrase code → TokenHub name, and back for /languages
4. **TokenHub client** — construct prompt, call chat/completions, parse response
5. **Segment batcher** — concat with `<SEP>`, split results, match by idx
6. **Glossary injector** — when glossary present, prepend terminology section to prompt
7. **Async job store** — in-memory dict for POC, Redis for production
8. **Auth middleware** — validate X-Api-Token header
9. **Env config** — read from .env file

## Phrase Validation

After deploying to a public URL:
1. Phrase → TMS → Phrase Language AI → Create MT profile → Connect MT → Bring Your Own Engine
2. Enter adapter URL (e.g. `https://phrase-hymt2.example.com`)
3. Enter auth details (X-Api-Token)
4. Click **Validate** — Phrase tests all 6 endpoints
5. Fix any validation errors, repeat

Once validated: Phrase tests it internally, then publishes as a listed partner engine.