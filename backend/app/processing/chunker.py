from app.utils.logger import get_logger

logger = get_logger("chunker")


def chunk_text(
    text: str, chunk_size: int = 512, overlap: int = 50
) -> list[str]:
    """
    Split text into overlapping chunks by word count.

    Uses word boundaries for splitting with configurable overlap
    to preserve context across chunk boundaries.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if len(words) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk.strip())
        if end >= len(words):
            break
        start = end - overlap

    logger.info(f"Chunked {len(words)} words into {len(chunks)} chunks")
    return chunks
