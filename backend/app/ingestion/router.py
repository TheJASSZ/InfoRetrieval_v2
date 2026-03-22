import os
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
        return _process_and_store(text, source_type="url", source=request.url)
    except Exception as e:
        logger.error(f"Store URL error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store/text", response_model=IngestResponse)
async def store_text(request: StoreTextRequest):
    """Store a raw text note."""
    try:
        source = request.title or "text_note"
        return _process_and_store(request.text, source_type="text", source=source)
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
        query_embedding = embed_text(request.query)
        results = hybrid_search(request.query, query_embedding, top_k=request.top_k)
        items = [StoredItem(**r) for r in results]
        return SearchResponse(results=items, query=request.query)
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """RAG-powered Q&A over stored content."""
    try:
        result = answer_query(request.query, top_k=request.top_k)
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


@router.post("/bookmarks/sync")
async def sync_bookmarks(request: BookmarkSyncRequest):
    """Parse Chrome bookmarks and queue them for ingestion."""
    bookmarks = parse_chrome_bookmarks(request.bookmark_path)
    if not bookmarks:
        return {"message": "No bookmarks found", "count": 0}

    processed = 0
    errors = 0
    for bm in bookmarks:
        try:
            text = await extract_from_url(bm["url"])
            _process_and_store(text, source_type="bookmark", source=bm["url"])
            processed += 1
        except Exception as e:
            logger.warning(f"Skipping bookmark {bm['url']}: {e}")
            errors += 1

    return {
        "message": f"Synced {processed} bookmarks ({errors} failed)",
        "processed": processed,
        "errors": errors,
        "total": len(bookmarks),
    }


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
    return get_collection_stats()


@router.delete("/entry/{doc_id}")
async def delete(doc_id: str):
    """Delete an entry from the knowledge base."""
    success = delete_entry(doc_id)
    if success:
        return {"message": f"Deleted {doc_id}"}
    raise HTTPException(status_code=404, detail="Entry not found")
