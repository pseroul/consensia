
import chromadb
from chromadb.utils import embedding_functions
import os
import utils
import logging

logger = logging.getLogger("uvicorn.error")

class ChromaClient:
    """
    A class for managing embeddings and similarity calculations using ChromaDB.
    
    Provides functionality for storing, retrieving, and querying text data with
    semantic embeddings, including operations for inserting, updating, removing,
    and finding similar data items.
    """

    def __init__(self, collection_name: str = "Ideas") -> None:
        """
        Initialize the Embedder with a ChromaDB client and collection.
        
        Args:
            collection_name (str, optional): Name of the ChromaDB collection to use.
                Defaults to "Ideas".
        """

        self.model_name = "all-MiniLM-L6-v2"

        self.client = chromadb.PersistentClient(path=os.getenv('CHROMA_DB'))
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.model_name)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.emb_fn
        )

    def insert_idea(self, title: str, content: str, tags: list[str]) -> None:
        """
        Insert new data into the embedding database.
        
        Adds a new document to the ChromaDB collection with the provided
        name and content, formatted appropriately for embedding.
        
        Args:
            title (str): The title of the idea to insert
            content (str): The content of the idea to insert
            tags (list[str]): The tags of the idea to insert
        """
        self.collection.add(
            documents=[utils.format_text(title, content, tags)],
            metadatas=[{"title": title}],
            ids=[title]
        )

    def update_idea(self, title: str, content: str, tags: list[str]) -> None:
        """
        Update existing data in the embedding database.
        
        Updates an existing document in the ChromaDB collection with new
        content while preserving the existing ID.
        
        Args:
            title (str): The name/title of the idea to update
            content (str): The new content for the idea
            tags (list[str]): The new tags of the idea
        """
        self.collection.update(
            documents=[utils.format_text(title, content, tags)],
            metadatas=[{"title": title}],
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
            name (str): The name/title of the idea
            n_results (int, optional): Number of similar results to return.
                Defaults to 10.
                
        Returns:
            list[dict[str, str]]: List of dictionaries containing 'title' and 'content'
                of similar data items
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
            chromadb.GetResult: All data from the collection including embeddings and documents
        """
        return self.collection.get(include=['embeddings', 'documents'], limit=max_items)
