import json
import re
import httpx
from app.config import settings
from app.processing.embedder import embed_text
from app.processing.reranker import rerank
from app.storage.vector_store import hybrid_search, get_sibling_chunks, _get_collection
from app.utils.logger import get_logger

logger = get_logger("rag_pipeline")

# Map user intent phrases to source_type values in ChromaDB
_SOURCE_TYPE_PATTERNS = {
    r"\b(text\s*notes?|my\s*notes?|notes?)\b": ["text"],
    r"\b(urls?|websites?|links?|bookmarks?|web\s*pages?)\b": ["url", "bookmark"],
    r"\b(images?|photos?|pictures?|screenshots?)\b": ["image_caption", "image_ocr"],
    r"\b(documents?|pdfs?|files?|docx?)\b": ["document"],
}

# Patterns that indicate the user wants an overview/inventory, not a specific search
_INVENTORY_PATTERNS = [
    r"what\s+(are|is)\s+in\s+my\b",
    r"what\s+do\s+i\s+have\b",
    r"show\s+(me\s+)?(all|my)\b",
    r"list\s+(all\s+)?(my|the)\b",
    r"how\s+many\b",
    r"give\s+me\s+(a\s+)?(summary|overview)\b",
    r"summarize\s+(all\s+)?my\b",
]


def _detect_source_filter(query: str) -> tuple[dict | None, list[str]]:
    """Detect if the user is asking about specific source type(s).

    Scans ALL patterns and collects every mentioned type, so queries like
    "how many Images/Documents/Bookmarks do I have?" match all three.

    Returns (chroma_where_filter, source_type_list).
    """
    lower = query.lower()
    all_types = []
    for pattern, source_types in _SOURCE_TYPE_PATTERNS.items():
        if re.search(pattern, lower):
            for st in source_types:
                if st not in all_types:
                    all_types.append(st)

    if not all_types:
        return None, []

    logger.info(f"Detected source_type filter: {all_types} from query")
    if len(all_types) == 1:
        return {"source_type": all_types[0]}, all_types
    return {"$or": [{"source_type": st} for st in all_types]}, all_types


def _is_inventory_query(query: str) -> bool:
    """Detect if the user is asking for an overview/inventory of their content."""
    lower = query.lower()
    return any(re.search(p, lower) for p in _INVENTORY_PATTERNS)


def _handle_inventory_query(query: str, source_types: list[str]) -> dict:
    """Handle inventory queries by aggregating all entries of the given source types.

    Instead of semantic search, this fetches ALL entries from ChromaDB,
    groups them by type, and uses the LLM to generate an overview.
    """
    collection = _get_collection()

    # Fetch ALL entries from the collection (no filter) so we get accurate counts
    try:
        all_entries = collection.get(include=["metadatas", "documents"])
    except Exception as e:
        logger.error(f"Inventory query error: {e}")
        return {
            "answer": "Error fetching entries from the knowledge base.",
            "sources": [],
            "query": query,
            "evaluation": None,
            "crag_triggered": False,
        }

    if not all_entries["ids"]:
        return {
            "answer": "Your knowledge base is empty. Try adding some URLs, notes, or files!",
            "sources": [],
            "query": query,
            "evaluation": None,
            "crag_triggered": False,
        }

    # Friendly display names for source types
    _type_labels = {
        "url": "URLs",
        "bookmark": "Bookmarks",
        "text": "Text Notes",
        "document": "Documents",
        "image_caption": "Images (captioned)",
        "image_ocr": "Images (with text/OCR)",
    }

    # Aggregate ALL entries by type, with unique item counts and tags
    type_data = {}  # source_type -> {chunk_count, unique_parents, tags, samples}

    for i, meta in enumerate(all_entries["metadatas"]):
        st = meta.get("source_type", "unknown")

        if st not in type_data:
            type_data[st] = {
                "chunk_count": 0,
                "parent_ids": set(),
                "standalone_sources": set(),
                "tags": {},
                "samples": [],
            }

        td = type_data[st]
        td["chunk_count"] += 1

        parent_id = meta.get("parent_id", "")
        src = meta.get("source", "unknown")
        if parent_id:
            td["parent_ids"].add(parent_id)
        else:
            td["standalone_sources"].add(src)

        # Collect tags
        tags_raw = meta.get("tags", "[]")
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        except (json.JSONDecodeError, TypeError):
            tags = []
        for tag in tags:
            if isinstance(tag, str) and len(tag) > 1:
                td["tags"][tag.lower()] = td["tags"].get(tag.lower(), 0) + 1

        # Collect sample summaries (deduplicated by parent)
        if len(td["samples"]) < 5:
            key = parent_id if parent_id else src
            existing_keys = {s["key"] for s in td["samples"]}
            if key not in existing_keys:
                summary = meta.get("summary", "")
                if not summary:
                    summary = (all_entries["documents"][i] or "")[:200]
                td["samples"].append({
                    "key": key,
                    "source": src,
                    "summary": summary[:200],
                    "tags": tags,
                    "source_type": st,
                })

    # Build per-type context for the LLM
    context_parts = []
    total_unique = 0
    total_chunks = 0

    # Only include types the user asked about (or all if general query)
    relevant_types = {st: td for st, td in type_data.items() if st in source_types}
    # Also track other types for context
    other_types = {st: td for st, td in type_data.items() if st not in source_types}

    for st, td in relevant_types.items():
        unique = len(td["parent_ids"]) + len(td["standalone_sources"])
        total_unique += unique
        total_chunks += td["chunk_count"]
        top_tags = sorted(td["tags"], key=td["tags"].get, reverse=True)[:10]
        label = _type_labels.get(st, st)

        part = f"\n{label}: {unique} unique items ({td['chunk_count']} chunks)"
        if top_tags:
            part += f"\n  Topics/Tags: {', '.join(top_tags)}"
        if td["samples"]:
            part += "\n  Examples:"
            for s in td["samples"][:3]:
                part += f"\n    - {s['source']}: {s['summary'][:100]}"
        context_parts.append(part)

    # Mention other types briefly
    if other_types:
        other_parts = []
        for st, td in other_types.items():
            unique = len(td["parent_ids"]) + len(td["standalone_sources"])
            total_unique += unique
            total_chunks += td["chunk_count"]
            label = _type_labels.get(st, st)
            other_parts.append(f"{label}: {unique}")
        context_parts.append(f"\nOther content in your KB: {', '.join(other_parts)}")

    context = (
        f"KNOWLEDGE BASE INVENTORY:\n"
        f"Total: {total_unique} unique items ({total_chunks} chunks) across "
        f"{len(type_data)} content types\n"
        + "\n".join(context_parts)
    )

    # Ask LLM to generate a nice overview
    prompt = (
        "You are a helpful knowledge base assistant. The user is asking about their "
        "stored content. Based on the inventory data below, give a clear and organized "
        "answer. State exact counts for each type. Describe the main topics/categories "
        "found. Be conversational but precise with numbers.\n\n"
        f"--- Inventory Data ---\n{context}\n--- End ---\n\n"
        f"User question: {query}\n\n"
        f"Answer:"
    )

    answer = _query_ollama(prompt, max_tokens=600)

    if not answer or len(answer) < 10:
        # Fallback: generate answer without LLM
        lines = [f"Your knowledge base contains **{total_unique}** unique items:\n"]
        for st, td in relevant_types.items():
            unique = len(td["parent_ids"]) + len(td["standalone_sources"])
            label = _type_labels.get(st, st)
            top_tags = sorted(td["tags"], key=td["tags"].get, reverse=True)[:8]
            lines.append(f"- **{label}:** {unique} items")
            if top_tags:
                lines.append(f"  Topics: {', '.join(top_tags)}")
        answer = "\n".join(lines)

    # Build source list for frontend (representative samples from each type)
    sources = []
    for td in relevant_types.values():
        for s in td["samples"][:2]:
            sources.append({
                "id": "",
                "summary": s["summary"],
                "chunk_text": s["summary"],
                "source_type": s["source_type"],
                "source": s["source"],
                "tags": s["tags"],
                "distance": 0.0,
                "created_at": "",
                "parent_id": "",
                "chunk_index": -1,
            })

    logger.info(
        f"Inventory query answered: {total_unique} unique items, "
        f"{total_chunks} chunks across {len(type_data)} types"
    )

    return {
        "answer": answer,
        "sources": sources[:5],
        "query": query,
        "evaluation": None,
        "crag_triggered": False,
    }


def _is_quality_result(item: dict) -> bool:
    """Check if a search result is high-quality and relevant."""
    if item.get("distance", 1.0) > settings.relevance_threshold:
        return False

    text = item.get("chunk_text", item.get("summary", "")).strip()
    if len(text) < 30:
        return False

    lower = text.lower()
    garbage_markers = [
        "performing security verification",
        "this website uses a security service",
        "this website is using a security service",
        "enable javascript",
        "please verify you are a human",
        "access denied",
        "403 forbidden",
        "you have been banned",
        "checking your browser before accessing",
        "attention required",
        "ray id:",
        "just a moment...",
        "you don't have permission to access",
    ]
    if any(marker in lower for marker in garbage_markers):
        return False

    # Detect raw JSON / structured data blobs
    stripped = text.strip()
    if (stripped.startswith("{") or stripped.startswith("[")) and stripped.count("{") > 3:
        return False

    # Low alphabetic ratio = encoded data, URLs, gibberish
    alpha_chars = sum(1 for c in text if c.isalpha())
    if len(text) > 100 and alpha_chars / len(text) < 0.4:
        return False

    words = text.split()
    if len(words) > 5:
        short_words = sum(1 for w in words if len(w) <= 2)
        if short_words / len(words) > 0.4:
            return False

    return True


def _query_ollama(prompt: str, max_tokens: int = 500) -> str:
    """Send a prompt to Ollama and get the response."""
    try:
        response = httpx.post(
            settings.ollama_url,
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return ""



def _rewrite_query(original_query: str) -> str:
    """Use the LLM to rewrite a query for better retrieval (CRAG step)."""
    prompt = (
        "Rewrite the following search query to be more specific and likely to "
        "match relevant documents. Output ONLY the rewritten query, nothing else.\n\n"
        f"Original query: {original_query}\n\n"
        "Rewritten query:"
    )
    rewritten = _query_ollama(prompt, max_tokens=100)
    if rewritten and len(rewritten) > 5:
        logger.info(f"Query rewritten: '{original_query}' -> '{rewritten}'")
        return rewritten
    return original_query


def _evaluate_retrieval_quality(results: list[dict]) -> str:
    """Evaluate retrieval quality: 'good', 'marginal', or 'poor'."""
    if not results:
        return "poor"

    quality_count = sum(1 for r in results[:5] if _is_quality_result(r))

    if quality_count >= 3:
        return "good"
    elif quality_count >= 1:
        return "marginal"
    return "poor"


def build_context(
    results: list[dict], max_context_chars: int = 4000
) -> str:
    """Build context from retrieved chunks with parent-child expansion.

    For chunked documents, retrieves sibling chunks for richer context.
    """
    context_parts = []
    total = 0
    seen_parents = set()

    for item in results:
        if not _is_quality_result(item):
            continue

        # Use chunk_text (the actual indexed content) for context
        chunk = item.get("chunk_text", item.get("summary", "")).strip()
        parent_id = item.get("parent_id", "")

        # Parent-child expansion: fetch siblings for richer context
        if parent_id and parent_id not in seen_parents:
            seen_parents.add(parent_id)
            siblings = get_sibling_chunks(item["id"], window=1)
            if siblings and len(siblings) > 1:
                chunk = "\n".join(siblings)

        if total + len(chunk) > max_context_chars:
            remaining = max_context_chars - total
            if remaining > 100:
                context_parts.append(chunk[:remaining])
            break

        context_parts.append(chunk)
        total += len(chunk)

    return "\n\n".join(context_parts)


def _retrieve_and_rerank(
    query: str, top_k: int, fetch_multiplier: int = 3, where: dict | None = None
) -> list[dict]:
    """Retrieve candidates with hybrid search and rerank with cross-encoder."""
    query_embedding = embed_text(query)
    candidates = hybrid_search(
        query, query_embedding, top_k=max(top_k * fetch_multiplier, 15), where=where
    )

    if not candidates:
        return []

    # Rerank with cross-encoder for precision
    reranked = rerank(query, candidates, top_k=top_k)
    return reranked


def answer_query(query: str, top_k: int = 5) -> dict:
    """Full RAG pipeline with Corrective RAG (CRAG):

    1. Embed query -> hybrid search (RRF) -> cross-encoder rerank
    2. Evaluate retrieval quality
    3. If poor: rewrite query (CRAG) -> re-retrieve -> re-rerank
    4. Build context with parent-child chunk expansion
    5. Generate answer with Ollama (Granite 8B)
    6. Optionally evaluate answer quality (RAGAS)
    """
    # Step 0: Detect if user is asking about a specific source type
    source_filter, source_types = _detect_source_filter(query)

    # Step 0b: Handle inventory/overview queries differently
    if _is_inventory_query(query):
        # If no specific types mentioned, show ALL types
        inventory_types = source_types if source_types else [
            "text", "url", "bookmark", "image_caption", "image_ocr", "document"
        ]
        logger.info(f"Routing to inventory handler for types: {inventory_types}")
        return _handle_inventory_query(query, inventory_types)

    # Step 1: Initial retrieval + reranking (with optional source_type filter)
    results = _retrieve_and_rerank(query, top_k, where=source_filter)

    if not results:
        return {
            "answer": "No relevant information found in the knowledge base.",
            "sources": [],
            "query": query,
            "evaluation": None,
            "crag_triggered": False,
        }

    # Step 2: Evaluate retrieval quality (CRAG)
    quality = _evaluate_retrieval_quality(results)
    crag_triggered = False

    # Step 3: If poor/marginal, rewrite query and re-retrieve
    if quality in ("poor", "marginal"):
        logger.info(f"CRAG triggered: retrieval quality is '{quality}', rewriting query")
        crag_triggered = True
        rewritten_query = _rewrite_query(query)

        if rewritten_query != query:
            new_results = _retrieve_and_rerank(rewritten_query, top_k, where=source_filter)
            if new_results:
                new_quality = _evaluate_retrieval_quality(new_results)
                if new_quality != "poor":
                    results = new_results
                    logger.info(
                        f"CRAG: rewritten query improved quality "
                        f"'{quality}' -> '{new_quality}'"
                    )

    # Step 4: Build context with parent-child expansion
    context = build_context(results)
    quality_results = [r for r in results if _is_quality_result(r)]

    if not context:
        return {
            "answer": (
                "I found some results but none were closely relevant to your "
                "question. Try being more specific, or check the sources below."
            ),
            "sources": results[:top_k],
            "query": query,
            "evaluation": None,
            "crag_triggered": crag_triggered,
        }

    # Step 5: Generate answer with Ollama
    prompt = (
        "You are a helpful knowledge base assistant. Answer the user's question "
        "using ONLY the information provided below. Be concise, clear, and "
        "conversational. If the information doesn't fully answer the question, "
        "say what you can and note what's missing. Do not make up information.\n\n"
        f"--- Information from knowledge base ---\n{context}\n"
        f"--- End of information ---\n\n"
        f"User question: {query}\n\n"
        f"Answer:"
    )

    answer = _query_ollama(prompt)

    if not answer or len(answer) < 10:
        parts = [
            r.get("chunk_text", r["summary"]).strip().replace(" . ", ". ")
            for r in quality_results[:3]
        ]
        answer = (
            "Here's what I found:\n\n" + "\n\n".join(parts)
            if parts
            else "I couldn't generate an answer. Check the sources below."
        )

    logger.info(f"RAG answer generated for query: {query[:50]}...")

    # Build source list for frontend
    sources = quality_results[:top_k]
    if len(sources) < top_k:
        seen = {r["id"] for r in sources}
        for r in results:
            if r["id"] not in seen:
                sources.append(r)
                if len(sources) >= top_k:
                    break

    # Step 6: Optional RAGAS evaluation
    evaluation = None
    if settings.enable_evaluation:
        try:
            from app.retrieval.evaluator import evaluate_rag

            evaluation = evaluate_rag(query, answer, context, results)
        except Exception as e:
            logger.error(f"Evaluation error: {e}")

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "evaluation": evaluation,
        "crag_triggered": crag_triggered,
    }
