#!/usr/bin/env python3
"""Ingest only the remaining unindexed documents and images."""

import asyncio
import httpx
import time
from pathlib import Path
import chromadb

BASE_URL = "http://localhost:8000/api"
DOC_DIR = Path(__file__).parent.parent / "watch_data" / "documents"
IMG_DIR = Path(__file__).parent.parent / "watch_data" / "images"


def get_indexed_sources():
    """Get already-indexed source names from ChromaDB."""
    client = chromadb.PersistentClient(path="./chroma_data")
    col = client.get_collection("info_store")
    all_data = col.get(include=["metadatas"])
    doc_sources = set()
    img_sources = set()
    for m in all_data["metadatas"]:
        src = m.get("source", "")
        name = Path(src).name if "/" in src else src
        st = m.get("source_type", "")
        if st == "document":
            doc_sources.add(name)
        elif st in ("image_ocr", "image_caption"):
            img_sources.add(name)
    return doc_sources, img_sources


async def ingest_file(client, filepath, idx, total, label):
    try:
        filename = filepath.name
        with open(filepath, "rb") as f:
            r = await client.post(
                f"{BASE_URL}/store/file",
                files={"file": (filename, f)},
                timeout=120.0,
            )
        if r.status_code == 200:
            data = r.json()
            print(f"  [{idx}/{total}] OK {label}: {filename}")
            return True
        else:
            print(f"  [{idx}/{total}] FAIL {label}: {filename} ({r.status_code})")
            return False
    except Exception as e:
        print(f"  [{idx}/{total}] ERROR {label}: {filepath.name} -> {str(e)[:60]}")
        return False


async def main():
    indexed_docs, indexed_imgs = get_indexed_sources()

    # Find missing docs
    missing_docs = sorted(
        [f for f in DOC_DIR.glob("*") if f.name not in indexed_docs]
    )
    # Find missing images
    missing_imgs = sorted(
        [f for f in IMG_DIR.glob("*.jpg") if f.name not in indexed_imgs]
    )

    print(f"Remaining: {len(missing_docs)} docs, {len(missing_imgs)} images")
    total = len(missing_docs) + len(missing_imgs)
    ok, fail = 0, 0
    start = time.time()

    sem = asyncio.Semaphore(2)

    async def _do(client, f, idx, label):
        nonlocal ok, fail
        async with sem:
            if await ingest_file(client, f, idx, total, label):
                ok += 1
            else:
                fail += 1

    async with httpx.AsyncClient() as client:
        tasks = []
        i = 1
        for f in missing_docs:
            tasks.append(_do(client, f, i, "DOC"))
            i += 1
        for f in missing_imgs:
            tasks.append(_do(client, f, i, "IMG"))
            i += 1
        await asyncio.gather(*tasks)

    elapsed = time.time() - start
    print(f"\nDone: {ok} OK, {fail} failed in {elapsed:.1f}s ({elapsed/max(ok,1):.1f}s/item)")


if __name__ == "__main__":
    asyncio.run(main())
