import httpx
from app.config import settings
from app.processing.embedder import embed_text
from app.processing.reranker import rerank
from app.storage.vector_store import hybrid_search, get_sibling_chunks
from app.utils.logger import get_logger

logger = get_logger("rag_pipeline")


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
        "enable javascript",
        "please verify you are a human",
        "access denied",
        "403 forbidden",
    ]
    if any(marker in lower for marker in garbage_markers):
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
    query: str, top_k: int, fetch_multiplier: int = 3
) -> list[dict]:
    """Retrieve candidates with hybrid search and rerank with cross-encoder."""
    query_embedding = embed_text(query)
    candidates = hybrid_search(
        query, query_embedding, top_k=max(top_k * fetch_multiplier, 15)
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
    # Step 1: Initial retrieval + reranking
    results = _retrieve_and_rerank(query, top_k)

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
            new_results = _retrieve_and_rerank(rewritten_query, top_k)
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
