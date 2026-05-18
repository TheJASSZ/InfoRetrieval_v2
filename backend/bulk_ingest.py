#!/usr/bin/env python3
"""Bulk ingestion script for demo preparation.

Ingests documents, images, and URLs into ChromaDB via the running backend API.
Requires the backend to be running on localhost:8000.

Usage:
    python bulk_ingest.py [--docs] [--images] [--urls] [--all]
"""

import argparse
import asyncio
import httpx
import os
import sys
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api"
WATCH_DOCS = Path(__file__).parent.parent / "watch_data" / "documents"
WATCH_IMAGES = Path(__file__).parent.parent / "watch_data" / "images"

# 50 curated, reliable URLs across diverse topics (no logins, no paywalls)
DEMO_URLS = [
    # Tech / CS
    "https://en.wikipedia.org/wiki/Information_retrieval",
    "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    "https://en.wikipedia.org/wiki/Vector_database",
    "https://en.wikipedia.org/wiki/Natural_language_processing",
    "https://en.wikipedia.org/wiki/Transformer_(deep_learning_model)",
    "https://en.wikipedia.org/wiki/Large_language_model",
    "https://en.wikipedia.org/wiki/Word_embedding",
    "https://en.wikipedia.org/wiki/Cosine_similarity",
    "https://en.wikipedia.org/wiki/TF%E2%80%93IDF",
    "https://en.wikipedia.org/wiki/BERT_(language_model)",
    # Science
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Neural_network_(machine_learning)",
    "https://en.wikipedia.org/wiki/Convolutional_neural_network",
    "https://en.wikipedia.org/wiki/Recurrent_neural_network",
    "https://en.wikipedia.org/wiki/Gradient_descent",
    # Programming
    "https://en.wikipedia.org/wiki/Python_(programming_language)",
    "https://en.wikipedia.org/wiki/FastAPI",
    "https://en.wikipedia.org/wiki/React_(software)",
    "https://en.wikipedia.org/wiki/TypeScript",
    "https://en.wikipedia.org/wiki/PostgreSQL",
    # Data / AI
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Deep_learning",
    "https://en.wikipedia.org/wiki/Reinforcement_learning",
    "https://en.wikipedia.org/wiki/Computer_vision",
    "https://en.wikipedia.org/wiki/Optical_character_recognition",
    # Algorithms
    "https://en.wikipedia.org/wiki/PageRank",
    "https://en.wikipedia.org/wiki/K-nearest_neighbors_algorithm",
    "https://en.wikipedia.org/wiki/Random_forest",
    "https://en.wikipedia.org/wiki/Support_vector_machine",
    "https://en.wikipedia.org/wiki/Principal_component_analysis",
    # Systems
    "https://en.wikipedia.org/wiki/MapReduce",
    "https://en.wikipedia.org/wiki/Apache_Spark",
    "https://en.wikipedia.org/wiki/Docker_(software)",
    "https://en.wikipedia.org/wiki/Kubernetes",
    "https://en.wikipedia.org/wiki/Microservices",
    # Databases
    "https://en.wikipedia.org/wiki/NoSQL",
    "https://en.wikipedia.org/wiki/Redis",
    "https://en.wikipedia.org/wiki/Elasticsearch",
    "https://en.wikipedia.org/wiki/Apache_Kafka",
    "https://en.wikipedia.org/wiki/GraphQL",
    # Math / Stats
    "https://en.wikipedia.org/wiki/Bayesian_inference",
    "https://en.wikipedia.org/wiki/Cross-entropy",
    "https://en.wikipedia.org/wiki/Attention_(machine_learning)",
    "https://en.wikipedia.org/wiki/Softmax_function",
    "https://en.wikipedia.org/wiki/Backpropagation",
    # Miscellaneous interesting topics
    "https://en.wikipedia.org/wiki/Boston",
    "https://en.wikipedia.org/wiki/Northeastern_University",
    "https://en.wikipedia.org/wiki/Climate_change",
    "https://en.wikipedia.org/wiki/Quantum_computing",
    "https://en.wikipedia.org/wiki/Blockchain",
]


async def check_backend():
    """Check if backend is running."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8000/health", timeout=5)
            return r.status_code == 200
    except Exception:
        return False


async def get_existing_sources():
    """Get sources already in ChromaDB to avoid duplicates."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE_URL}/stats", timeout=10)
            # We'll just track by URL to avoid re-ingesting
            return set()
    except Exception:
        return set()


async def ingest_url(client: httpx.AsyncClient, url: str, idx: int, total: int):
    """Ingest a single URL."""
    try:
        r = await client.post(
            f"{BASE_URL}/store/url",
            json={"url": url},
            timeout=120.0,
        )
        if r.status_code == 200:
            data = r.json()
            print(f"  [{idx}/{total}] OK: {url[:60]} -> {data.get('summary', '')[:80]}")
            return True
        else:
            print(f"  [{idx}/{total}] FAIL ({r.status_code}): {url[:60]}")
            return False
    except Exception as e:
        print(f"  [{idx}/{total}] ERROR: {url[:60]} -> {str(e)[:60]}")
        return False


async def ingest_file(client: httpx.AsyncClient, filepath: str, idx: int, total: int):
    """Ingest a single file via the store/file endpoint."""
    try:
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            r = await client.post(
                f"{BASE_URL}/store/file",
                files={"file": (filename, f)},
                timeout=120.0,
            )
        if r.status_code == 200:
            data = r.json()
            print(f"  [{idx}/{total}] OK: {filename} -> {data.get('summary', '')[:80]}")
            return True
        else:
            print(f"  [{idx}/{total}] FAIL ({r.status_code}): {filename}")
            return False
    except Exception as e:
        print(f"  [{idx}/{total}] ERROR: {os.path.basename(filepath)} -> {str(e)[:60]}")
        return False


async def ingest_urls(urls: list[str], concurrency: int = 3):
    """Ingest multiple URLs with concurrency limit."""
    print(f"\n{'='*60}")
    print(f"  INGESTING {len(urls)} URLs (concurrency={concurrency})")
    print(f"{'='*60}")

    semaphore = asyncio.Semaphore(concurrency)
    ok, fail = 0, 0

    async def _do(client, url, idx):
        nonlocal ok, fail
        async with semaphore:
            success = await ingest_url(client, url, idx, len(urls))
            if success:
                ok += 1
            else:
                fail += 1

    start = time.time()
    async with httpx.AsyncClient() as client:
        tasks = [_do(client, url, i + 1) for i, url in enumerate(urls)]
        await asyncio.gather(*tasks)

    elapsed = time.time() - start
    print(f"\n  URLs done: {ok} OK, {fail} failed in {elapsed:.1f}s")
    return ok


async def ingest_files(directory: Path, extensions: list[str], concurrency: int = 2):
    """Ingest files from a directory with concurrency limit."""
    files = []
    for ext in extensions:
        files.extend(sorted(directory.glob(f"*.{ext}")))

    if not files:
        print(f"  No files found in {directory}")
        return 0

    print(f"\n{'='*60}")
    print(f"  INGESTING {len(files)} files from {directory.name} (concurrency={concurrency})")
    print(f"{'='*60}")

    semaphore = asyncio.Semaphore(concurrency)
    ok, fail = 0, 0

    async def _do(client, filepath, idx):
        nonlocal ok, fail
        async with semaphore:
            success = await ingest_file(client, str(filepath), idx, len(files))
            if success:
                ok += 1
            else:
                fail += 1

    start = time.time()
    async with httpx.AsyncClient() as client:
        tasks = [_do(client, f, i + 1) for i, f in enumerate(files)]
        await asyncio.gather(*tasks)

    elapsed = time.time() - start
    print(f"\n  Files done: {ok} OK, {fail} failed in {elapsed:.1f}s")
    return ok


async def main():
    parser = argparse.ArgumentParser(description="Bulk ingest for demo")
    parser.add_argument("--urls", action="store_true", help="Ingest curated URLs")
    parser.add_argument("--docs", action="store_true", help="Ingest documents")
    parser.add_argument("--images", action="store_true", help="Ingest images")
    parser.add_argument("--all", action="store_true", help="Ingest everything")
    parser.add_argument("--concurrency", type=int, default=2, help="Max concurrent requests")
    args = parser.parse_args()

    if not any([args.urls, args.docs, args.images, args.all]):
        args.all = True

    # Check backend
    if not await check_backend():
        print("ERROR: Backend not running at localhost:8000. Start it first.")
        sys.exit(1)

    print("Backend is up. Starting bulk ingestion...\n")
    total_ingested = 0
    start = time.time()

    if args.urls or args.all:
        total_ingested += await ingest_urls(DEMO_URLS, concurrency=args.concurrency)

    if args.docs or args.all:
        total_ingested += await ingest_files(
            WATCH_DOCS, ["pdf", "txt", "docx"], concurrency=args.concurrency
        )

    if args.images or args.all:
        total_ingested += await ingest_files(
            WATCH_IMAGES, ["jpg", "jpeg", "png"], concurrency=args.concurrency
        )

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"  COMPLETE: {total_ingested} items ingested in {elapsed:.1f}s")
    print(f"  Avg: {elapsed/max(total_ingested,1):.1f}s per item")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
