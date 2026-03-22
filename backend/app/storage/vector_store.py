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
    """Get stats about the stored collection."""
    collection = _get_collection()
    return {
        "total_documents": collection.count(),
        "collection_name": settings.chroma_collection,
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
