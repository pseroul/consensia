#!/usr/bin/env python3
"""
Re-embed all ideas after model change from all-distilroberta-v1 to all-MiniLM-L6-v2.

Usage:
    cd backend
    python scripts/migrate_embeddings.py

This script:
  1. Reads all ideas (with tags) from SQLite
  2. Deletes the old ChromaDB collection
  3. Recreates it with the new embedding model (all-MiniLM-L6-v2)
  4. Re-inserts all ideas with their formatted text

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
from utils import format_text


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
    ideas = cursor.fetchall()
    conn.close()

    print(f"Found {len(ideas)} ideas in SQLite")

    if not ideas:
        print("No ideas to migrate. Done.")
        return

    # 2. Delete old collection and recreate with new model
    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=chroma_path)

    # Delete old collection if it exists
    try:
        client.delete_collection("Ideas")
        print("Deleted old 'Ideas' collection")
    except Exception:
        print("No existing 'Ideas' collection to delete")

    # Create new collection with the new model
    new_model = "all-MiniLM-L6-v2"
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=new_model
    )
    collection = client.get_or_create_collection(
        name="Ideas",
        embedding_function=emb_fn,
    )
    print(f"Created new collection with model: {new_model}")

    # 3. Re-insert all ideas
    for _idea_id, title, content, tags_str in ideas:
        tags = [t for t in tags_str.split(";") if t]
        doc = format_text(title, content, tags)
        collection.add(
            documents=[doc],
            metadatas=[{"title": title}],
            ids=[title],
        )

    print(f"Re-embedded {len(ideas)} ideas with {new_model}")
    print("Migration complete!")


if __name__ == "__main__":
    main()
