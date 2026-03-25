import os
import asyncio
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.models.schemas import (
    StoreURLRequest,
    StoreTextRequest,
    SearchRequest,
    ChatRequest,
    BookmarkSyncRequest,
    WatchdogConfigRequest,
    IngestResponse,
    SearchResponse,
    ChatResponse,
    StoredItem,
)
from app.extraction.web_scraper import extract_from_url
from app.extraction.ocr_pipeline import run_ocr
from app.extraction.document_parser import parse_document
from app.extraction.image_captioning import generate_caption
from app.processing.summarizer import summarize
from app.processing.embedder import embed_text
from app.processing.tagger import generate_tags
from app.storage.vector_store import (
    add_entry,
    hybrid_search,
    get_collection_stats,
    delete_entry,
)
from app.retrieval.rag_pipeline import answer_query
from app.ingestion.bookmark_sync import parse_chrome_bookmarks
from app.ingestion.watchdog_agent import (
    start_watchdog,
    stop_watchdog,
    is_image_file,
    is_document_file,
)
from app.utils.logger import get_logger

logger = get_logger("api_router")

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _process_and_store(text: str, source_type: str, source: str) -> IngestResponse:
    """Common pipeline: summarize -> tag -> embed -> store."""
    summary = summarize(text)
    tags = generate_tags(summary)
    embedding = embed_text(summary)
    add_entry(
        summary=summary,
        embedding=embedding,
        source_type=source_type,
        source=source,
        tags=tags,
        full_text=text,
    )
    return IngestResponse(
        message=f"Successfully stored {source_type} content",
        summary=summary,
        tags=tags,
        source_type=source_type,
    )


# ── Store Endpoints ──────────────────────────────────────────


@router.post("/store/url", response_model=IngestResponse)
async def store_url(request: StoreURLRequest):
    """Extract, summarize, and store content from a URL."""
    try:
        text = await extract_from_url(request.url)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _process_and_store, text, "url", request.url
        )
    except Exception as e:
        logger.error(f"Store URL error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store/text", response_model=IngestResponse)
async def store_text(request: StoreTextRequest):
    """Store a raw text note."""
    try:
        source = request.title or "text_note"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _process_and_store, request.text, "text", source
        )
    except Exception as e:
        logger.error(f"Store text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store/file", response_model=IngestResponse)
async def store_file(file: UploadFile = File(...)):
    """Upload and process a file (image, PDF, DOCX, TXT)."""
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        file_path_str = str(file_path)

        if is_image_file(file_path_str):
            return _process_image(file_path_str, file.filename)
        elif is_document_file(file_path_str):
            text = parse_document(file_path_str)
            return _process_and_store(text, source_type="document", source=file.filename)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {Path(file.filename).suffix}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store/path", response_model=IngestResponse)
async def store_local_path(path: str):
    """Process a local file path (image or document)."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        if is_image_file(path):
            return _process_image(path, path)
        elif is_document_file(path):
            text = parse_document(path)
            return _process_and_store(text, source_type="document", source=path)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {Path(path).suffix}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store path error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _process_image(image_path: str, source: str) -> IngestResponse:
    """Process image: OCR routing -> summarize or caption -> store."""
    ocr_text, method = run_ocr(image_path)

    if method != "none" and len(ocr_text) >= 20:
        # Text-heavy image: summarize the OCR text
        logger.info(f"Image has text ({method}), summarizing OCR output")
        return _process_and_store(ocr_text, source_type="image_ocr", source=source)
    else:
        # Visual image: generate caption
        logger.info("Image has minimal text, generating caption")
        caption = generate_caption(image_path)
        if not caption:
            raise ValueError("Failed to generate caption for image")
        tags = generate_tags(caption)
        embedding = embed_text(caption)
        add_entry(
            summary=caption,
            embedding=embedding,
            source_type="image_caption",
            source=source,
            tags=tags,
        )
        return IngestResponse(
            message="Stored image caption",
            summary=caption,
            tags=tags,
            source_type="image_caption",
        )


# ── Search Endpoints ─────────────────────────────────────────


@router.post("/search", response_model=SearchResponse)
async def search_info(request: SearchRequest):
    """Semantic search across stored content."""
    try:
        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(None, embed_text, request.query)

        def _search():
            return hybrid_search(request.query, query_embedding, top_k=request.top_k)

        results = await loop.run_in_executor(None, _search)
        items = [StoredItem(**r) for r in results]
        return SearchResponse(results=items, query=request.query)
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """RAG-powered Q&A over stored content."""
    try:
        loop = asyncio.get_event_loop()

        def _answer():
            return answer_query(request.query, top_k=request.top_k)

        result = await loop.run_in_executor(None, _answer)
        sources = [StoredItem(**s) for s in result["sources"]]
        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            query=result["query"],
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Bookmark Sync ────────────────────────────────────────────


_bookmark_sync_status = {"running": False, "processed": 0, "errors": 0, "total": 0}


@router.post("/bookmarks/sync")
async def sync_bookmarks(request: BookmarkSyncRequest, background_tasks=None):
    """Parse Chrome bookmarks and queue them for background ingestion."""
    global _bookmark_sync_status

    if _bookmark_sync_status["running"]:
        return {
            "message": f"Sync already in progress ({_bookmark_sync_status['processed']}/{_bookmark_sync_status['total']})",
            **_bookmark_sync_status,
        }

    bookmarks = parse_chrome_bookmarks(request.bookmark_path)
    if not bookmarks:
        return {"message": "No bookmarks found", "count": 0}

    # Check which bookmarks are already stored
    from app.storage.vector_store import _get_collection
    collection = _get_collection()
    existing_sources = set()
    try:
        all_meta = collection.get(include=["metadatas"])
        for meta in all_meta["metadatas"]:
            if meta.get("source_type") == "bookmark":
                existing_sources.add(meta.get("source", ""))
    except Exception:
        pass

    new_bookmarks = [bm for bm in bookmarks if bm["url"] not in existing_sources]

    if not new_bookmarks:
        return {"message": "All bookmarks already synced", "processed": 0, "total": len(bookmarks)}

    # Run sync in background
    _bookmark_sync_status = {"running": True, "processed": 0, "errors": 0, "total": len(new_bookmarks)}

    async def _process_one_bookmark(bm, semaphore):
        async with semaphore:
            try:
                text = await extract_from_url(bm["url"])
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, _process_and_store, text, "bookmark", bm["url"]
                )
                _bookmark_sync_status["processed"] += 1
                logger.info(f"Synced bookmark: {bm['url']} ({_bookmark_sync_status['processed']}/{len(new_bookmarks)})")
            except Exception as e:
                logger.warning(f"Skipping bookmark {bm['url']}: {e}")
                _bookmark_sync_status["errors"] += 1

    async def _sync_in_background():
        # Process 5 bookmarks concurrently for speed
        semaphore = asyncio.Semaphore(5)
        tasks = [_process_one_bookmark(bm, semaphore) for bm in new_bookmarks]
        await asyncio.gather(*tasks)
        _bookmark_sync_status["running"] = False
        logger.info(f"Bookmark sync complete: {_bookmark_sync_status['processed']} processed, {_bookmark_sync_status['errors']} errors")

    asyncio.create_task(_sync_in_background())

    return {
        "message": f"Sync started for {len(new_bookmarks)} new bookmarks ({len(existing_sources)} already synced)",
        "new": len(new_bookmarks),
        "already_synced": len(existing_sources),
        "total": len(bookmarks),
    }


@router.get("/bookmarks/status")
async def bookmark_sync_status():
    """Check bookmark sync progress."""
    return _bookmark_sync_status


@router.get("/bookmarks/preview")
async def preview_bookmarks(bookmark_path: str | None = None):
    """Preview bookmarks without ingesting them."""
    bookmarks = parse_chrome_bookmarks(bookmark_path)
    return {"bookmarks": bookmarks[:50], "total": len(bookmarks)}


# ── Watchdog Control ─────────────────────────────────────────


@router.post("/watchdog/start")
async def start_watch(request: WatchdogConfigRequest):
    """Start file system watchdog on specified directories."""
    success = start_watchdog(request.directories)
    if success:
        return {"message": "Watchdog started", "directories": request.directories}
    raise HTTPException(status_code=400, detail="Failed to start watchdog")


@router.post("/watchdog/stop")
async def stop_watch():
    """Stop the file system watchdog."""
    stop_watchdog()
    return {"message": "Watchdog stopped"}


# ── Utility Endpoints ────────────────────────────────────────


@router.get("/stats")
async def stats():
    """Get knowledge base statistics."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_collection_stats)
    result["bookmark_sync"] = _bookmark_sync_status
    return result


@router.delete("/entry/{doc_id}")
async def delete(doc_id: str):
    """Delete an entry from the knowledge base."""
    success = delete_entry(doc_id)
    if success:
        return {"message": f"Deleted {doc_id}"}
    raise HTTPException(status_code=404, detail="Entry not found")
