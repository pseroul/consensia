#!/usr/bin/env python3
"""
Re-embed all ideas after model change from all-MiniLM-L6-v2 to all-mpnet-base-v2.

Usage:
    cd backend
    python scripts/migrate_embeddings.py

This script:
  1. Reads all ideas (with tags) from SQLite
  2. Deletes the old ChromaDB collection
  3. Recreates it with the new embedding model (all-mpnet-base-v2)
  4. Re-inserts all ideas via ChromaClient.bulk_insert with richer metadata

The new model uses 768-dimensional vectors (up from 384) and a 512-token
context window, which improves semantic clustering quality.

Prerequisites:
  - Environment variables NAME_DB and CHROMA_DB must be set (or defaults used)
  - Run `python -c "from config import set_env_var; set_env_var()"` first
    if env vars are not already configured
"""

import os
import sys
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import set_env_var


def main() -> None:
    set_env_var()

    db_path = os.getenv("NAME_DB")
    chroma_path = os.getenv("CHROMA_DB")

    print(f"SQLite database: {db_path}")
    print(f"ChromaDB path:   {chroma_path}")

    # 1. Read all ideas with tags from SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT
            i.id, i.title, i.content,
            COALESCE(GROUP_CONCAT(r.tag_name, ';'), '') AS tags
        FROM ideas i
        LEFT JOIN relations r ON i.id = r.idea_id
        GROUP BY i.id, i.title, i.content
    """)
    rows = cursor.fetchall()
    conn.close()

    print(f"Found {len(rows)} ideas in SQLite")

    if not rows:
        print("No ideas to migrate. Done.")
        return

    # 2. Delete old collection and recreate with new model
    import chromadb

    client = chromadb.PersistentClient(path=chroma_path)

    try:
        client.delete_collection("Ideas")
        print("Deleted old 'Ideas' collection")
    except Exception:
        print("No existing 'Ideas' collection to delete")

    # 3. Re-insert all ideas via ChromaClient (handles model + metadata correctly)
    from chroma_client import ChromaClient

    chroma = ChromaClient(collection_name="Ideas")
    print(f"Created new collection with model: {chroma.model_name}")

    ideas = [
        {
            "title": title,
            "description": content,
            "tags": [t for t in tags_str.split(";") if t],
        }
        for _idea_id, title, content, tags_str in rows
    ]

    chroma.bulk_insert(ideas)

    print(f"Re-embedded {len(ideas)} ideas with {chroma.model_name}")
    print("Migration complete!")


if __name__ == "__main__":
    main()
