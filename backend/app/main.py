import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ingestion.router import router
from app.ingestion.watchdog_agent import file_queue, is_image_file, is_document_file
from app.extraction.ocr_pipeline import run_ocr
from app.extraction.document_parser import parse_document
from app.extraction.image_captioning import generate_caption
from app.processing.summarizer import summarize
from app.processing.embedder import embed_text
from app.processing.tagger import generate_tags
from app.storage.vector_store import add_entry
from app.utils.logger import get_logger

logger = get_logger("main")


async def watchdog_consumer():
    """Background task: process files detected by the watchdog."""
    while True:
        try:
            file_path = await asyncio.wait_for(file_queue.get(), timeout=5.0)
            logger.info(f"Processing watchdog file: {file_path}")

            try:
                if is_image_file(file_path):
                    ocr_text, method = run_ocr(file_path)
                    if method != "none" and len(ocr_text) >= 20:
                        text = ocr_text
                        source_type = "image_ocr"
                    else:
                        caption = generate_caption(file_path)
                        tags = generate_tags(caption)
                        embedding = embed_text(caption)
                        add_entry(
                            summary=caption,
                            embedding=embedding,
                            source_type="image_caption",
                            source=file_path,
                            tags=tags,
                        )
                        logger.info(f"Auto-stored image caption: {file_path}")
                        continue
                    summary = summarize(text)
                elif is_document_file(file_path):
                    text = parse_document(file_path)
                    summary = summarize(text)
                    source_type = "document"
                else:
                    continue

                tags = generate_tags(summary)
                embedding = embed_text(summary)
                add_entry(
                    summary=summary,
                    embedding=embedding,
                    source_type=source_type,
                    source=file_path,
                    tags=tags,
                    full_text=text,
                )
                logger.info(f"Auto-stored {source_type}: {file_path}")

            except Exception as e:
                logger.error(f"Watchdog processing error for {file_path}: {e}")

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Watchdog consumer error: {e}")
            await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    logger.info("InfoStore v2 starting up...")

    # Start watchdog consumer as background task
    consumer_task = asyncio.create_task(watchdog_consumer())

    yield

    # Cleanup
    consumer_task.cancel()
    from app.ingestion.watchdog_agent import stop_watchdog
    stop_watchdog()
    logger.info("InfoStore v2 shut down.")


app = FastAPI(
    title="InfoStore v2 - Multimodal AI Knowledge Base",
    description=(
        "A multimodal AI system for unified content summarization and retrieval. "
        "Supports URLs, images, PDFs, DOCX, text notes with semantic search and RAG."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes
app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
