from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StoreURLRequest(BaseModel):
    url: str


class StoreFileRequest(BaseModel):
    path: str


class StoreTextRequest(BaseModel):
    text: str
    title: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5


class BookmarkSyncRequest(BaseModel):
    bookmark_path: Optional[str] = None


class WatchdogConfigRequest(BaseModel):
    directories: list[str]


class StoredItem(BaseModel):
    id: str
    summary: str
    source_type: str
    source: str
    tags: list[str]
    distance: float
    created_at: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[StoredItem]
    query: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[StoredItem]
    query: str


class IngestResponse(BaseModel):
    message: str
    summary: str
    tags: list[str]
    source_type: str
