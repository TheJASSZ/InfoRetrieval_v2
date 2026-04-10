# Changes Summary — RAG Pipeline Improvements (2026-04-04)

## Files Changed

1. `backend/app/extraction/web_scraper.py`
2. `backend/app/ingestion/router.py`
3. `backend/app/processing/tagger.py`
4. `backend/app/retrieval/rag_pipeline.py`
5. `backend/app/storage/vector_store.py`

---

## 1. Garbage Content Filtering at Ingestion (`web_scraper.py`)

**Problem:** Cloudflare block pages, raw JSON blobs, access denied messages, and other junk were being scraped and stored in ChromaDB.

**Fix:** Added `_is_garbage_content()` function that detects:
- Cloudflare/bot protection pages (security verification, banned, access denied, etc.)
- Raw JSON data blobs (high brace count)
- Low alphabetic ratio text (encoded data, URL strings, gibberish)

**Behavior change:**
- If Trafilatura returns garbage, it falls back to Playwright
- If both return garbage, the URL is rejected entirely instead of storing junk

---

## 2. Chunker Parameter Bug Fix (`router.py`)

**Problem:** `_process_and_store()` called `chunk_text(text, chunk_size=..., chunk_overlap=...)` but the actual function signature uses `overlap`, not `chunk_overlap`. This caused ALL document chunking to silently fail.

**Fix:** Changed `chunk_overlap=settings.chunk_overlap` → `overlap=settings.chunk_overlap`

---

## 3. Tagger Fix with Keyword Fallback (`tagger.py`)

**Problem:** The T5 tagger was echoing its own prompt as tags. Tags like `"generate 5 short topic tags for this text"` and `"separated by commas: a screenshot of a blue"` were being stored.

**Fix:**
- Changed prompt from `"Generate 5 short topic tags..."` → `"Extract the main topics as comma-separated keywords:"`
- Added prompt-leak detection: if the T5 output contains fragments of the prompt, it falls back to keyword extraction
- Added `_extract_keywords()` function as fallback — simple word-frequency-based keyword extraction with stopword filtering
- If T5 returns empty output or fails entirely, keyword extraction is used

---

## 4. RAG Pipeline — Inventory Queries & Source-Type Filtering (`rag_pipeline.py`)

### 4a. Source-Type Aware Routing

**Problem:** Queries like "What are in my text notes?" searched all content types and returned random image captions instead of filtering to `source_type="text"`.

**Fix:** Added `_detect_source_filter()` that maps user intent to ChromaDB metadata filters:
- "notes" → `source_type="text"`
- "URLs/websites/bookmarks" → `source_type in ["url", "bookmark"]`
- "images/photos" → `source_type in ["image_caption", "image_ocr"]`
- "documents/PDFs" → `source_type="document"`

Scans ALL patterns so multi-type queries like "Images/Documents/URLs" match all three.

### 4b. Inventory Query Handler

**Problem:** Questions like "What are in my URLs?" or "How many images do I have?" are **inventory questions** — they need an aggregate overview of all entries, not a similarity search.

**Fix:** Added `_is_inventory_query()` and `_handle_inventory_query()`:
- Detects overview phrases: "what are in my", "how many", "show me all my", etc.
- Instead of semantic search, fetches ALL entries from ChromaDB
- Aggregates per type: unique item counts, chunk counts, top tags, sample entries
- Builds structured context and sends to Granite 8B to generate a conversational summary
- Falls back to a formatted text answer if LLM fails
- Returns representative sample sources for the frontend

### 4c. Improved Quality Filtering

**Problem:** `_is_quality_result()` missed JSON blobs and other garbage in retrieved results.

**Fix:** Added detection for:
- Raw JSON blobs (starts with `{` or `[` with high brace count)
- Low alphabetic ratio text
- Additional security page markers (banned, attention required, ray id, etc.)

---

## 5. Hybrid Search with Metadata Filtering (`vector_store.py`)

**Problem:** `hybrid_search()` had no way to filter by metadata (e.g., `source_type`), so source-type filtering couldn't work.

**Fix:** Added optional `where` parameter to `hybrid_search()`. When provided, the filter is applied to both dense vector search and keyword search branches. This enables the source-type-aware routing from the RAG pipeline.

---

## What Was Tried and Reverted

The following features were implemented but reverted due to quality issues:

1. **Streaming Chat (SSE):** Token-by-token streaming from Ollama via `/api/chat/stream` endpoint. Reverted because Granite 8B hallucinated extensively without proper stop-token enforcement in streaming mode.

2. **Bulk Ingest:** Background processing of all existing files in watched directories. Reverted by user preference — was working but very slow on CPU (~2-5 sec/file for 5,555 files).

---

## How to Commit

```bash
git add backend/app/extraction/web_scraper.py \
        backend/app/ingestion/router.py \
        backend/app/processing/tagger.py \
        backend/app/retrieval/rag_pipeline.py \
        backend/app/storage/vector_store.py

git commit -m "fix: improve RAG quality — inventory queries, garbage filtering, tagger fix, source-type routing"
```
