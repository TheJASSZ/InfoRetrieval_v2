import os
import torch
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Device
    device_preference: str = "auto"

    # ChromaDB
    chroma_persist_dir: str = str(BASE_DIR / "chroma_data")
    chroma_collection: str = "info_store"

    # Models
    blip_model_path: str = str(BASE_DIR.parent / "models" / "blip_finetuned")
    summarizer_model: str = "google/flan-t5-base"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    rag_llm_model: str = "google/flan-t5-large"

    # Watchdog
    watch_dirs: str = ""
    bookmark_path: str = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome/Default/Bookmarks"
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()


def get_device() -> str:
    pref = settings.device_preference.lower()
    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


DEVICE = get_device()
logging.info(f"Using device: {DEVICE}")
