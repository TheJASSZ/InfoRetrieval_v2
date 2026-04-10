import re
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from app.config import settings, DEVICE
from app.utils.logger import get_logger

logger = get_logger("tagger")

_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return

    model_name = settings.summarizer_model
    logger.info(f"Loading tagger model: {model_name}")
    _tokenizer = AutoTokenizer.from_pretrained(model_name)
    _model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    device = DEVICE if DEVICE != "mps" else "cpu"
    _model = _model.to(device)
    _model.eval()
    logger.info("Tagger model loaded")


def _extract_keywords(text: str, max_tags: int = 5) -> list[str]:
    """Simple keyword extraction fallback using word frequency."""
    import string
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "out", "off", "over", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "both", "each", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "this", "that", "these", "those", "it", "its", "i", "me",
        "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
        "they", "them", "their", "what", "which", "who", "whom",
        "also", "about", "up", "down", "get", "got", "one", "two",
    }
    words = text.lower().translate(str.maketrans("", "", string.punctuation)).split()
    freq = {}
    for w in words:
        if w not in stopwords and len(w) > 2 and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=freq.get, reverse=True)
    return ranked[:max_tags]


def generate_tags(text: str, max_tags: int = 5) -> list[str]:
    """Generate descriptive tags from text content using T5, with keyword fallback."""
    _load_model()
    try:
        prompt = f"Extract the main topics as comma-separated keywords: {text[:500]}"
        device = DEVICE if DEVICE != "mps" else "cpu"
        inputs = _tokenizer(
            prompt, return_tensors="pt", max_length=512, truncation=True
        ).to(device)

        with torch.no_grad():
            output_ids = _model.generate(**inputs, max_length=60, num_beams=2)

        raw = _tokenizer.decode(output_ids[0], skip_special_tokens=True)

        # Filter out tags that look like the prompt leaking through
        prompt_fragments = [
            "generate", "short topic", "tags for", "separated by commas",
            "extract", "main topics", "comma-separated", "keywords",
        ]
        raw_lower = raw.lower()
        if any(frag in raw_lower for frag in prompt_fragments):
            logger.warning(f"Tagger echoed prompt, falling back to keywords: {raw[:80]}")
            tags = _extract_keywords(text, max_tags)
            logger.info(f"Keyword-extracted tags: {tags}")
            return tags

        # Parse comma-separated tags and clean them
        tags = [t.strip().lower() for t in re.split(r"[,;]", raw) if t.strip()]
        tags = [t for t in tags if len(t) > 1 and len(t) < 50][:max_tags]

        # If T5 returned nothing useful, fall back to keywords
        if not tags:
            tags = _extract_keywords(text, max_tags)
            logger.info(f"Keyword-extracted tags (empty T5 output): {tags}")
            return tags

        logger.info(f"Generated tags: {tags}")
        return tags
    except Exception as e:
        logger.error(f"Tag generation error: {e}")
        return _extract_keywords(text, max_tags)
