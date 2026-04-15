
import chromadb
from chromadb.utils import embedding_functions
import os
import utils
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm_client import LlmPort

logger = logging.getLogger("uvicorn.error")

class ChromaClient:
    """
    A class for managing embeddings and similarity calculations using ChromaDB.

    Provides functionality for storing, retrieving, and querying text data with
    semantic embeddings, including operations for inserting, updating, removing,
    and finding similar data items.

    Note: switching from all-MiniLM-L6-v2 (384 dims) to all-mpnet-base-v2 (768 dims)
    changes the collection dimension. The existing collection must be deleted and
    re-populated via bulk_insert after this model change.
    """

    _WORD_THRESHOLD: int = 60  # summarize descriptions longer than this

    def __init__(self, collection_name: str = "Ideas", llm: "LlmPort | None" = None) -> None:
        """
        Initialize the ChromaClient with a ChromaDB client and collection.

        Args:
            collection_name (str, optional): Name of the ChromaDB collection to use.
                Defaults to "Ideas".
            llm (LlmPort | None, optional): LLM backend used to summarize long
                descriptions before embedding. When None, original text is used as-is.
        """

        self.model_name = "all-mpnet-base-v2"
        self._llm = llm

        self.client = chromadb.PersistentClient(path=os.getenv('CHROMA_DB'))
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.model_name)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.emb_fn
        )

    def _maybe_summarize(self, text: str) -> str:
        """Summarize text if it exceeds the word threshold and an LLM is available."""
        if self._llm is None or len(text.split()) <= self._WORD_THRESHOLD:
            return text
        try:
            return self._llm.summarize_texts([text])[0]
        except Exception:
            logger.warning("Summarization failed, using original text")
            return text

    def insert_idea(self, title: str, content: str, tags: list[str], comments: list[str] | None = None) -> None:
        """
        Insert new data into the embedding database.

        Adds a new document to the ChromaDB collection with the provided
        title, content, and tags, formatted for embedding. Long descriptions
        are summarized when an LLM is available. The original description is
        always stored in metadata for retrieval.

        Args:
            title (str): The title of the idea to insert
            content (str): The content of the idea to insert
            tags (list[str]): The tags of the idea to insert
            comments (list[str] | None): Optional impact comments to include in the embedding
        """
        summary = self._maybe_summarize(content)
        comments_summary = None
        if comments:
            joined = " ".join(comments)
            comments_summary = [self._maybe_summarize(joined)]
        self.collection.add(
            documents=[utils.format_text(title, summary, tags, comments_summary)],
            metadatas=[{
                "title": title,
                "tags": ",".join(tags),
                "description": content,
            }],
            ids=[title]
        )

    def update_idea(self, title: str, content: str, tags: list[str], comments: list[str] | None = None) -> None:
        """
        Update existing data in the embedding database.

        Updates an existing document in the ChromaDB collection with new
        content while preserving the existing ID. Long descriptions are
        summarized when an LLM is available. The original description is
        always stored in metadata for retrieval.

        Args:
            title (str): The name/title of the idea to update
            content (str): The new content for the idea
            tags (list[str]): The new tags of the idea
            comments (list[str] | None): Optional impact comments to include in the embedding
        """
        summary = self._maybe_summarize(content)
        comments_summary = None
        if comments:
            joined = " ".join(comments)
            comments_summary = [self._maybe_summarize(joined)]
        self.collection.update(
            documents=[utils.format_text(title, summary, tags, comments_summary)],
            metadatas=[{
                "title": title,
                "tags": ",".join(tags),
                "description": content,
            }],
            ids=[title]
        )

    def remove_idea(self, title: str) -> None:
        """
        Remove data from the embedding database.

        Deletes a document from the ChromaDB collection based on its ID.

        Args:
            title: str: The id of the idea to remove
        """
        self.collection.delete(ids=[title])

    def get_similar_idea(self, idea: str, n_results: int = 10) -> list[dict[str, str]]:
        """
        Find similar data items based on semantic similarity.

        Performs a semantic search in the ChromaDB collection to find
        data items similar to the provided query.

        Args:
            idea (str): The query text to search against
            n_results (int, optional): Number of similar results to return.
                Defaults to 10.

        Returns:
            list[str]: List of idea titles of similar data items
        """

        results = self.collection.query(
            query_texts=[idea],
            n_results=n_results
        )
        logger.info(f"chroma_client:get_similar_data({idea}) ->\n {results}")
        titles: list[str] = results["ids"][0]
        return titles

    def get_all_ideas(self, max_items: int = 500) -> chromadb.GetResult:
        """
        Retrieve all ideas from the embedding database.

        Gets all documents, embeddings, and metadata from the ChromaDB collection.

        Returns:
            chromadb.GetResult: All data from the collection including embeddings,
                documents, and metadatas
        """
        return self.collection.get(include=['embeddings', 'documents', 'metadatas'], limit=max_items)

    def bulk_insert(self, ideas: list[dict]) -> None:
        """Insert all ideas with batch summarization for efficiency.

        Each idea dict must have keys: ``title`` (str), ``description`` (str),
        ``tags`` (list[str]). An optional ``comments`` key may hold a list[str].

        Long descriptions and comments are summarized in batches when an LLM is
        available, which is far more efficient than calling _maybe_summarize one
        text at a time for large collections.

        Args:
            ideas: List of idea dicts to insert.
        """
        descriptions = [idea["description"] for idea in ideas]
        all_comments = [" ".join(idea.get("comments", [])) for idea in ideas]

        if self._llm is not None:
            long_desc_indices = [i for i, d in enumerate(descriptions) if len(d.split()) > self._WORD_THRESHOLD]
            if long_desc_indices:
                long_texts = [descriptions[i] for i in long_desc_indices]
                try:
                    summaries = self._llm.summarize_texts(long_texts)
                    for idx, summary in zip(long_desc_indices, summaries, strict=False):
                        descriptions[idx] = summary
                except Exception:
                    logger.warning("Batch summarization failed, using original texts")

            long_comment_indices = [i for i, c in enumerate(all_comments) if len(c.split()) > self._WORD_THRESHOLD]
            if long_comment_indices:
                long_comments = [all_comments[i] for i in long_comment_indices]
                try:
                    comment_summaries = self._llm.summarize_texts(long_comments)
                    for idx, summary in zip(long_comment_indices, comment_summaries, strict=False):
                        all_comments[idx] = summary
                except Exception:
                    logger.warning("Batch comment summarization failed, using originals")

        documents = []
        metadatas = []
        ids = []
        for i, idea in enumerate(ideas):
            comments_arg = [all_comments[i]] if all_comments[i].strip() else None
            documents.append(utils.format_text(idea["title"], descriptions[i], idea["tags"], comments_arg))
            metadatas.append({
                "title": idea["title"],
                "tags": ",".join(idea["tags"]),
                "description": idea["description"],
            })
            ids.append(idea["title"])

        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
