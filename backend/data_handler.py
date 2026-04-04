import sqlite3
from typing import Any, Hashable
import pandas as pd
from chroma_client import ChromaClient
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
from config import set_env_var

logger = logging.getLogger("uvicorn.error")

def init_database() -> None:
    """
    Initialize the SQLite database with required tables.
    
    Creates four tables if they don't exist:
    - users: stores user informations
    - tags: stores tag information
    - ideas: stores ideas with contents
    - relations: manages many-to-many relationships between data and tags
    
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY);
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relations (
        idea_id INTEGER,
        tag_name TEXT,
        PRIMARY KEY (idea_id, tag_name),
        FOREIGN KEY (idea_id) REFERENCES ideas(id),
        FOREIGN KEY (tag_name) REFERENCES tags(name)
    );
    """)

    conn.commit()
    conn.close()

# GET IDEA OR TAGS
def get_idea_from_tags(tags: str) -> list[dict[Hashable, str]]:
    """
    Retrieve ideas associated with specific tags.
    
    Fetches ideas that are linked to the specified tags from the database.
    
    Args:
        tags (str): Semicolon-separated string of tag names
        
    Returns:
        list[dict[Hashable, str]]: List of dictionaries containing ideas
    """
    if not tags:
        return get_ideas()
    else:
        tags_list = tags.split(";")
        placeholders = ", ".join(["?"] * len(tags_list))
        conn = sqlite3.connect(os.getenv('NAME_DB'))
        query = f"""
        SELECT DISTINCT i. id, i.title, i.content
        FROM ideas i
        JOIN relations r ON i.id = r.idea_id
        JOIN tags t ON r.tag_name = t.name
        WHERE t.name IN ({placeholders});
        """
        df = pd.read_sql_query(query, conn, params=tags_list)
        conn.close()
    return df.to_dict("records")

def get_ideas() -> list[dict[Hashable, Any]]:
    """
    Retrieve all ideas from the database with limit to prevent memory issues.
    
    Gets all records from the ideas table in the SQLite database.
    
    Args:
        limit (int): Maximum number of records to return
        
    Returns:
        list[dict[Hashable, Any]]: List of dictionaries containing all ideas
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    query = """
    SELECT 
        i.id, 
        i.title, 
        i.content, 
        GROUP_CONCAT(r.tag_name, ';') AS tags
    FROM 
        ideas i
    LEFT JOIN 
        relations r ON i.id = r.idea_id
    GROUP BY 
        i.id, i.title, i.content;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Handle potential NaN values in the dataframe
    df = df.fillna('')
    return df.to_dict("records")

def get_user_ideas(user_email: str) -> list[dict[Hashable, Any]]:
    """
    Retrieve all ideas of a user from the database with limit to prevent memory issues.
    
    Gets all records from the ideas table in the SQLite database.
    
    Args:
        user_email (str): user email address
        
    Returns:
        list[dict[Hashable, Any]]: List of dictionaries containing all ideas
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    query = """
    SELECT 
        i.id, 
        i.title, 
        i.content, 
        GROUP_CONCAT(r.tag_name, ';') AS tags
    FROM 
        ideas i
    LEFT JOIN 
        relations r ON i.id = r.idea_id
    JOIN 
        users u ON i.owner_id = u.id
    WHERE 
        u.email = ?
    GROUP BY 
        i.id, i.title, i.content;
    """
    df = pd.read_sql_query(query, conn, params=[user_email])
    conn.close()
    
    # Handle potential NaN values in the dataframe
    df = df.fillna('')
    return df.to_dict("records")

def get_content(idea_id: int) -> str:
    """
    Retrieve the content of a specific idea.
    
    Gets the content for an idea with the specified id.
    
    Args:
        idea_id (int): ID of the idea to retrieve content for
        
    Returns:
        str: content of the idea
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    df = pd.read_sql_query("SELECT content FROM ideas WHERE id=(?)", conn, params=[idea_id])
    conn.close()
    return df['content'].iloc[0]

def get_tags() -> list[dict[Hashable, Any]]:
    """
    Retrieve all tags from the database.
    
    Gets all records from the tags table in the SQLite database.
    
    Returns:
        list[dict[Hashable, Any]]: List of dictionaries containing all tags
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    df = pd.read_sql_query("SELECT * FROM tags", conn)
    conn.close()
    return df.to_dict("records")

def get_tags_from_idea(idea: int):
    """
    Retrieve tags associated with a specific idea.
    
    Gets all tags that are linked to the specified idea.
    
    Args:
        idea (int): Id of the idea to retrieve tags for
        
    Returns:
        list[str]: List of tag names associated with the idea
    """
    if not idea:
        return get_tags()
    else:
        conn = sqlite3.connect(os.getenv('NAME_DB'))
        query = "SELECT tag_name FROM relations WHERE idea_id = (?)"
        df = pd.read_sql_query(query, conn, params=[idea])
        conn.close()
    return df['tag_name'].to_list()

def get_similar_idea(idea: str) -> list[dict[str, Any]]:
    """
    Find similar ideas based on semantic similarity.
    
    Uses the ChromaClient to find ideas similar to the specified idea.
    
    Args:
        idea (str): Name of the idea to find similar items for
        
    Returns:
        list[dict[str, Any]]: List of dictionaries containing similar ideas
    """
    logger.info(f"data_handler:get_similar_idea({idea})")
    chroma = ChromaClient()
    titles = chroma.get_similar_idea(idea)

    if not titles:  # Handle empty titles list
        return []

    # Create placeholders for the IN clause
    placeholders = ", ".join(["?"] * len(titles))
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    query = f"""
    SELECT 
        i.id, 
        i.title, 
        i.content, 
        GROUP_CONCAT(r.tag_name, ';') AS tags
    FROM 
        ideas i
    LEFT JOIN 
        relations r ON i.id = r.idea_id
    WHERE
        i.title IN ({placeholders})
    GROUP BY 
        i.id, i.title, i.content;
    """
    df = pd.read_sql_query(query, conn, params=titles)
    conn.close()
    
    # Handle potential NaN values in the dataframe
    df = df.fillna('')
    return df.to_dict("records")

# ADD FUNCTIONS
def add_idea(title: str, content: str, owner_email: str) -> int:
    """
    Add a new idea to the database.
    
    Inserts a new record into the ideas table and adds the corresponding
    embedding to the ChromaClient.
    
    Args:
        title (str): Name of the idea to add
        content (str): content of the idea to add
        owner_email (str): Email of the idea's owner
        
    Returns:
        int: the id of the new idea
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        # Get owner_id from email
        cursor.execute(
            "SELECT id FROM users WHERE email = ?",
            (owner_email,)
        )
        result = cursor.fetchone()
        if not result:
            logger.info(f"Error: User with email '{owner_email}' not found.")
            return -1
        owner_id = result[0]
        
        cursor.execute(
            "INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)",
            (title, content, owner_id)
        )
        conn.commit()
        new_id = cursor.lastrowid
        
        # Run embedding insertion asynchronously using thread pool
        with ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: ChromaClient().insert_idea(title=title, content=content))
            # Wait for completion but don't block the main thread significantly
            future.result(timeout=30)  # 30 second timeout
            
        logger.info(f"idea '{title}'  added successfully.")
        return new_id
    except sqlite3.IntegrityError:
        logger.info(f"Errr : idea '{title}' already exists.")
        return -1
    except Exception as e:
        logger.info(f"Error adding embedding for '{title}': {e}")
        return -1
    finally:
        conn.close()

def add_tag(name: str) -> None:
    """
    Add a new tag to the database.
    
    Inserts a new record into the tags table.
    
    Args:
        name (str): Name of the tag to add
        
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO tags (name) VALUES (?)",
            (name,)
        )
        conn.commit()
        logger.info(f"Tag '{name}' added successfully.")
    except sqlite3.IntegrityError:
        logger.info(f"Error : tag '{name}' already exists.")
    finally:
        conn.close()

def add_relation(idea_id: int, tag_name: str) -> None:
    """
    Create a relationship between a idea and a tag.
    
    Inserts a new record into the relation table linking idea and tag.
    
    Args:
        idea_id (str): Name of the idea
        tag_name (str): Name of the tag
        
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)",
            (idea_id, tag_name)
        )
        conn.commit()
        logger.info(f"Relation between '{idea_id}' and '{tag_name}'  added successfully.")
    except sqlite3.IntegrityError:
        logger.info("Error : This relation already exists or foreign keys are unvalid.")
    finally:
        conn.close()

# REMOVE FUNCTIONS
def remove_idea(id: int, title: str) -> None:
    """
    Remove a idea from the database.
    
    Deletes a record from the idea and removes the corresponding
    embedding from the ChromaClient.
    
    Args:
        id (int): Id of the idea to remove
        title (str): Title of the idea to remove
        
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM ideas WHERE id = ?",
            (id,)
        )
        conn.commit()
        embedding = ChromaClient()
        embedding.remove_idea(title=title)
        logger.info(f"idea '{id}' removed successfully.")
    except sqlite3.Error as e:
        logger.info(f"Error deleting idea : {e}")
    finally:
        conn.close()

def remove_tag(name: str) -> None:
    """
    Remove a tag from the database.
    
    Deletes a record from the tags table.
    
    Args:
        name (str): Name of the tag to remove
        
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM tags WHERE name = ?",
            (name,)
        )
        conn.commit()
        logger.info(f"Tag '{name}' removed successfully.")
    except sqlite3.Error as e:
        logger.info(f"Error deleting tag : {e}")
    finally:
        conn.close()

def remove_relation(idea_id: int, tag_name: str) -> None:
    """
    Remove a relationship between a idea and a tag.
    
    Deletes a record from the relation table.
    
    Args:
        idea_id (int): Name of the idea
        tag_name (str): Name of the tag
        
    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM relations WHERE idea_id = ? AND tag_name = ?",
            (idea_id, tag_name)
        )
        conn.commit()
        
        logger.info(f"Relation between '{idea_id}' and '{tag_name}' removed successfully.")
    except sqlite3.Error as e:
        logger.info(f"Error when deleting relation : {e}")
    finally:
        conn.close()

def update_idea(id: int, title: str, content: str) -> None:
    """
    Update an existing idea in the database.
    
    Updates the content of an existing idea and updates the
    corresponding embedding in the ChromaClient.
    
    Args:
        id (int): Id of the idea
        title (str): Name of the idea to update
        content (str): New content for the idea
        
    Returns:
        None
    """
    logger.info(f"update_idea {id}: {title} / {content}")
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE ideas SET content = ?, title = ? WHERE id = ?",
            (content, title, id)
        )
        conn.commit()
        
        # Run embedding update asynchronously using thread pool
        with ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: ChromaClient().update_idea(title=title, content=content))
            # Wait for completion but don't block the main thread significantly
            future.result(timeout=30)  # 30 second timeout
            
        logger.info(f"idea '{id}'  updated successfully.")
    except sqlite3.IntegrityError:
        logger.info(f"Error : idea '{id}' can't be updated.")
    except Exception as e:
        logger.info(f"Error updating embedding for '{id}': {e}")
    finally:
        conn.close()

def embed_all_ideas() -> None:
    """
    Regenerate embeddings for all ideas in the database.
    
    Retrieves all ideas from the database and creates embeddings
    for each one using the ChromaClient.
    
    Returns:
        None
    """
    try:
        # Use the existing get_ideas() function to retrieve all data
        ideas = get_ideas()
        
        # Create Embedder instance
        embedding = ChromaClient()
        
        # Process all ideas
        total_items = len(ideas)
        logger.info(f"Regenerating embeddings for {total_items} ideas...")
        print(f"Regenerating embeddings for {total_items} ideas...")
        
        for i, item in enumerate(ideas, 1):
            try:
                embedding.insert_idea(title=item['title'], content=item['content'])
                logger.info(f"Processed {i}/{total_items}: {item['title']}")
            except Exception as e:
                logger.info(f"Error processing item '{item['title']}': {e}")
                
        logger.info("Embedding regeneration completed successfully.")
        
    except Exception as e:
        logger.info(f"Error in embed_all_ideas: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Regenerate all embeddings')
    parser.add_argument('-e', '--embedding', help='regenerate embeddings for chromadb', action="store_true")
    args = parser.parse_args()
    set_env_var()
    if args.embedding: 
        embed_all_ideas()
