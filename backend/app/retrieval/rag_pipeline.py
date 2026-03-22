import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from app.config import settings, DEVICE
from app.processing.embedder import embed_text
from app.storage.vector_store import hybrid_search
from app.utils.logger import get_logger

logger = get_logger("rag_pipeline")

_model = None
_tokenizer = None


def _load_llm():
    global _model, _tokenizer
    if _model is not None:
        return

    model_name = settings.rag_llm_model
    logger.info(f"Loading RAG LLM: {model_name}")

    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    device = DEVICE if DEVICE != "mps" else "cpu"
    _model = _model.to(device)
    _model.eval()
    logger.info(f"RAG LLM loaded on {device}")


def build_context(results: list[dict], max_context_chars: int = 2000) -> str:
    """Build a context string from search results for the LLM."""
    context_parts = []
    total = 0
    for i, item in enumerate(results):
        entry = f"[Source {i+1} ({item['source_type']}): {item['source']}]\n{item['summary']}"
        if total + len(entry) > max_context_chars:
            break
        context_parts.append(entry)
        total += len(entry)
    return "\n\n".join(context_parts)


def answer_query(query: str, top_k: int = 5) -> dict:
    """
    Full RAG pipeline:
    1. Embed query
    2. Retrieve relevant documents (hybrid search)
    3. Build context from results
    4. Generate answer with LLM
    """
    _load_llm()

    # Step 1: Embed and retrieve
    query_embedding = embed_text(query)
    results = hybrid_search(query, query_embedding, top_k=top_k)

    if not results:
        return {
            "answer": "No relevant information found in the knowledge base.",
            "sources": [],
            "query": query,
        }

    # Step 2: Build context
    context = build_context(results)

    # Step 3: Generate answer
    prompt = (
        f"Based on the following stored information, answer the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Answer:"
    )

    try:
        device = DEVICE if DEVICE != "mps" else "cpu"
        inputs = _tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        ).to(device)

        with torch.no_grad():
            output_ids = _model.generate(
                **inputs, max_new_tokens=300, num_beams=4
            )

        answer = _tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        logger.info(f"RAG answer generated for query: {query[:50]}...")
    except Exception as e:
        logger.error(f"RAG generation error: {e}")
        answer = f"Found {len(results)} relevant results. Top result: {results[0]['summary']}"

    return {
        "answer": answer,
        "sources": results,
        "query": query,
    }
