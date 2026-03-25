import httpx
from app.processing.embedder import embed_text
from app.storage.vector_store import hybrid_search
from app.utils.logger import get_logger

logger = get_logger("rag_pipeline")

# Config
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "granite3.1-dense:8b"
RELEVANCE_THRESHOLD = 0.45


def _is_quality_result(item: dict) -> bool:
    """Check if a search result is high-quality and relevant."""
    if item.get('distance', 1.0) > RELEVANCE_THRESHOLD:
        return False
    summary = item.get('summary', '').strip()
    if len(summary) < 30:
        return False

    lower = summary.lower()
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

    words = summary.split()
    if len(words) > 5:
        short_words = sum(1 for w in words if len(w) <= 2)
        if short_words / len(words) > 0.4:
            return False

    return True


def build_context(results: list[dict], max_context_chars: int = 3000) -> str:
    """Build a clean context string from relevant, high-quality results."""
    context_parts = []
    total = 0
    for item in results:
        if not _is_quality_result(item):
            continue
        entry = item['summary'].strip()
        if total + len(entry) > max_context_chars:
            break
        context_parts.append(entry)
        total += len(entry)
    return "\n\n".join(context_parts)


def _query_ollama(prompt: str) -> str:
    """Send a prompt to Ollama and get the response."""
    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 500,
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return ""


def answer_query(query: str, top_k: int = 5) -> dict:
    """
    Full RAG pipeline:
    1. Embed query
    2. Retrieve relevant documents (hybrid search)
    3. Build context from results
    4. Generate answer with Ollama (Granite 8B)
    """
    # Step 1: Embed and retrieve (fetch extra to filter garbage)
    query_embedding = embed_text(query)
    results = hybrid_search(query, query_embedding, top_k=max(top_k * 3, 15))

    if not results:
        return {
            "answer": "No relevant information found in the knowledge base.",
            "sources": [],
            "query": query,
        }

    # Step 2: Build context from quality results only
    context = build_context(results)
    quality_results = [r for r in results if _is_quality_result(r)]

    if not context:
        return {
            "answer": (
                "I found some results but none were closely relevant to your question. "
                "Try being more specific, or check the sources below for loosely related content."
            ),
            "sources": results[:top_k],
            "query": query,
        }

    # Step 3: Generate answer with Ollama
    prompt = (
        "You are a helpful knowledge base assistant. Answer the user's question "
        "using ONLY the information provided below. Be concise, clear, and conversational. "
        "If the information doesn't fully answer the question, say what you can and note "
        "what's missing. Do not make up information.\n\n"
        f"--- Information from knowledge base ---\n{context}\n"
        f"--- End of information ---\n\n"
        f"User question: {query}\n\n"
        f"Answer:"
    )

    answer = _query_ollama(prompt)

    if not answer or len(answer) < 10:
        # Fallback: compose from quality results
        parts = [r['summary'].strip().replace(" . ", ". ") for r in quality_results[:3]]
        answer = "Here's what I found:\n\n" + "\n\n".join(parts) if parts else (
            "I couldn't generate an answer. Check the sources below."
        )

    logger.info(f"RAG answer generated for query: {query[:50]}...")

    # Return quality sources to frontend
    sources = quality_results[:top_k]
    if len(sources) < top_k:
        seen = {r['id'] for r in sources}
        for r in results:
            if r['id'] not in seen:
                sources.append(r)
                if len(sources) >= top_k:
                    break

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
    }
