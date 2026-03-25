import json
import uuid
import chromadb
from datetime import datetime
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("vector_store")

_client = None
_collection = None


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    logger.info(f"Initializing ChromaDB at {settings.chroma_persist_dir}")
    _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    _collection = _client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        f"ChromaDB collection '{settings.chroma_collection}' ready "
        f"({_collection.count()} documents)"
    )
    return _collection


def add_entry(
    summary: str,
    embedding: list[float],
    source_type: str,
    source: str,
    tags: list[str],
    full_text: str = "",
) -> str:
    """Store a document in ChromaDB with metadata."""
    collection = _get_collection()
    doc_id = str(uuid.uuid4())

    metadata = {
        "source_type": source_type,
        "source": source,
        "tags": json.dumps(tags),
        "created_at": datetime.now().isoformat(),
        "full_text_length": len(full_text),
    }

    # ChromaDB stores the document text for keyword search
    # and the embedding for dense vector search
    collection.add(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[summary],
        metadatas=[metadata],
    )

    logger.info(f"Stored entry {doc_id}: {source_type} from {source}")
    return doc_id


def search(
    query_embedding: list[float],
    top_k: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Search by vector similarity."""
    collection = _get_collection()

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    items = []
    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i]
        items.append({
            "id": results["ids"][0][i],
            "summary": results["documents"][0][i],
            "source_type": metadata.get("source_type", ""),
            "source": metadata.get("source", ""),
            "tags": json.loads(metadata.get("tags", "[]")),
            "distance": results["distances"][0][i],
            "created_at": metadata.get("created_at", ""),
        })

    logger.info(f"Search returned {len(items)} results")
    return items


def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Hybrid search: combines dense vector search with ChromaDB's
    built-in keyword filtering.
    """
    collection = _get_collection()

    # Dense vector search
    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k * 2,
        include=["documents", "metadatas", "distances"],
    )

    # Keyword search using ChromaDB's where_document filter
    keyword_results = None
    keywords = [w for w in query_text.split() if len(w) > 3]
    if keywords:
        try:
            keyword_filter = {
                "$or": [
                    {"$contains": kw} for kw in keywords[:3]
                ]
            }
            keyword_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where_document=keyword_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            pass

    # Merge and deduplicate results
    seen_ids = set()
    merged = []

    def add_results(results, boost=0.0):
        if not results or not results["ids"][0]:
            return
        for i in range(len(results["ids"][0])):
            doc_id = results["ids"][0][i]
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            metadata = results["metadatas"][0][i]
            merged.append({
                "id": doc_id,
                "summary": results["documents"][0][i],
                "source_type": metadata.get("source_type", ""),
                "source": metadata.get("source", ""),
                "tags": json.loads(metadata.get("tags", "[]")),
                "distance": results["distances"][0][i] - boost,
                "created_at": metadata.get("created_at", ""),
            })

    # Keyword matches get a slight boost (lower distance = better)
    if keyword_results:
        add_results(keyword_results, boost=0.05)
    add_results(vector_results)

    merged.sort(key=lambda x: x["distance"])
    return merged[:top_k]


def get_collection_stats() -> dict:
    """Get stats about the stored collection with type breakdown and file counts."""
    import os
    from pathlib import Path

    collection = _get_collection()
    total = collection.count()

    # Get type breakdown from ChromaDB
    type_counts = {}
    if total > 0:
        try:
            all_meta = collection.get(include=["metadatas"])
            for meta in all_meta["metadatas"]:
                st = meta.get("source_type", "unknown")
                type_counts[st] = type_counts.get(st, 0) + 1
        except Exception:
            pass

    # Count actual files on disk in watch directories
    file_counts = {"images_on_disk": 0, "documents_on_disk": 0, "bookmarks": 0}
    watch_dirs = settings.watch_dirs
    if watch_dirs:
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        doc_exts = {".pdf", ".docx", ".doc", ".txt", ".md"}
        for dir_path in watch_dirs.split(","):
            path = Path(dir_path.strip()).expanduser()
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        ext = f.suffix.lower()
                        if ext in image_exts:
                            file_counts["images_on_disk"] += 1
                        elif ext in doc_exts:
                            file_counts["documents_on_disk"] += 1

    # Count Chrome bookmarks from file
    try:
        bookmark_path = Path(settings.bookmark_path).expanduser()
        if bookmark_path.exists():
            import json as _json
            with open(bookmark_path, "r") as f:
                bm_data = _json.load(f)
            def _count_bookmarks(node):
                count = 0
                if node.get("type") == "url":
                    count += 1
                for child in node.get("children", []):
                    count += _count_bookmarks(child)
                return count
            for root in bm_data.get("roots", {}).values():
                if isinstance(root, dict):
                    file_counts["bookmarks"] += _count_bookmarks(root)
    except Exception:
        pass

    return {
        "total_documents": total,
        "collection_name": settings.chroma_collection,
        "by_type": type_counts,
        "file_counts": file_counts,
    }


def delete_entry(doc_id: str) -> bool:
    """Delete a document by ID."""
    collection = _get_collection()
    try:
        collection.delete(ids=[doc_id])
        logger.info(f"Deleted entry {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return False
