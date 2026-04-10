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

    Creates seven tables if they don't exist:
    - users: stores user informations
    - tags: stores tag information
    - books: stores books that group ideas
    - ideas: stores ideas with contents, each belonging to a book
    - relations: manages many-to-many relationships between ideas and tags
    - book_authors: manages many-to-many relationships between books and users
    - impact_comments: stores impact comments on ideas

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
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        FOREIGN KEY (owner_id) REFERENCES users (id),
        FOREIGN KEY (book_id) REFERENCES books (id)
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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS book_authors (
        book_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (book_id, user_id),
        FOREIGN KEY (book_id) REFERENCES books(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS idea_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idea_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        value INTEGER NOT NULL CHECK (value IN (-1, 1)),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (idea_id, user_id),
        FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS impact_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        idea_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Migration: add is_admin column if missing
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    if 'is_admin' not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

    conn.commit()
    conn.close()

# GET IDEA OR TAGS
def get_idea_from_tags(tags: str, book_id: int | None = None) -> list[dict[Hashable, str]]:
    """
    Retrieve ideas associated with specific tags.

    Fetches ideas that are linked to the specified tags from the database.

    Args:
        tags (str): Semicolon-separated string of tag names
        book_id (int | None): Optional book ID to filter ideas by book

    Returns:
        list[dict[Hashable, str]]: List of dictionaries containing ideas
    """
    if not tags:
        return get_ideas()
    else:
        tags_list = tags.split(";")
        placeholders = ", ".join(["?"] * len(tags_list))
        conn = sqlite3.connect(os.getenv('NAME_DB'))
        if book_id is not None:
            query = f"""
            SELECT i.id, i.title, i.content, i.book_id,
                   COALESCE(SUM(iv.value), 0) AS score
            FROM ideas i
            JOIN relations r ON i.id = r.idea_id
            JOIN tags t ON r.tag_name = t.name
            LEFT JOIN idea_votes iv ON i.id = iv.idea_id
            WHERE t.name IN ({placeholders}) AND i.book_id = ?
            GROUP BY i.id, i.title, i.content, i.book_id;
            """
            params: list = tags_list + [book_id]
        else:
            query = f"""
            SELECT i.id, i.title, i.content, i.book_id,
                   COALESCE(SUM(iv.value), 0) AS score
            FROM ideas i
            JOIN relations r ON i.id = r.idea_id
            JOIN tags t ON r.tag_name = t.name
            LEFT JOIN idea_votes iv ON i.id = iv.idea_id
            WHERE t.name IN ({placeholders})
            GROUP BY i.id, i.title, i.content, i.book_id;
            """
            params = tags_list
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
    return df.to_dict("records")

def get_ideas(book_id: int | None = None) -> list[dict[Hashable, Any]]:
    """
    Retrieve ideas from the database with limit to prevent memory issues.

    Args:
        book_id (int | None): Optional book ID to filter ideas by book

    Returns:
        list[dict[Hashable, Any]]: List of dictionaries containing ideas
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    if book_id is not None:
        query = """
        SELECT
            i.id,
            i.title,
            i.content,
            i.book_id,
            GROUP_CONCAT(r.tag_name, ';') AS tags,
            COALESCE(SUM(iv.value), 0) AS score
        FROM
            ideas i
        LEFT JOIN
            relations r ON i.id = r.idea_id
        LEFT JOIN
            idea_votes iv ON i.id = iv.idea_id
        WHERE
            i.book_id = ?
        GROUP BY
            i.id, i.title, i.content, i.book_id;
        """
        df = pd.read_sql_query(query, conn, params=[book_id])
    else:
        query = """
        SELECT
            i.id,
            i.title,
            i.content,
            i.book_id,
            GROUP_CONCAT(r.tag_name, ';') AS tags,
            COALESCE(SUM(iv.value), 0) AS score
        FROM
            ideas i
        LEFT JOIN
            relations r ON i.id = r.idea_id
        LEFT JOIN
            idea_votes iv ON i.id = iv.idea_id
        GROUP BY
            i.id, i.title, i.content, i.book_id;
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
        i.book_id,
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
        i.id, i.title, i.content, i.book_id;
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

def get_tags(book_id: int | None = None) -> list[dict[Hashable, Any]]:
    """
    Retrieve tags from the database.

    Gets all records from the tags table, or only those used by ideas in a specific book.

    Args:
        book_id (int | None): Optional book ID to filter tags to those used in that book

    Returns:
        list[dict[Hashable, Any]]: List of dictionaries containing tags
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    if book_id is not None:
        query = """
        SELECT DISTINCT t.name FROM tags t
        JOIN relations r ON t.name = r.tag_name
        JOIN ideas i ON r.idea_id = i.id
        WHERE i.book_id = ?
        """
        df = pd.read_sql_query(query, conn, params=[book_id])
    else:
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
        i.book_id,
        GROUP_CONCAT(r.tag_name, ';') AS tags
    FROM
        ideas i
    LEFT JOIN
        relations r ON i.id = r.idea_id
    WHERE
        i.title IN ({placeholders})
    GROUP BY
        i.id, i.title, i.content, i.book_id;
    """
    df = pd.read_sql_query(query, conn, params=titles)
    conn.close()
    
    # Handle potential NaN values in the dataframe
    df = df.fillna('')
    return df.to_dict("records")

# ADD FUNCTIONS
def add_idea(title: str, content: str, owner_email: str, book_id: int) -> int:
    """
    Add a new idea to the database.

    Inserts a new record into the ideas table and adds the corresponding
    embedding to the ChromaClient.

    Args:
        title (str): Name of the idea to add
        content (str): content of the idea to add
        owner_email (str): Email of the idea's owner
        book_id (int): ID of the book this idea belongs to

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
            "INSERT INTO ideas (title, content, owner_id, book_id) VALUES (?, ?, ?, ?)",
            (title, content, owner_id, book_id)
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

# BOOK FUNCTIONS
def add_book(title: str) -> int:
    """
    Add a new book to the database.

    Args:
        title (str): Title of the book

    Returns:
        int: the id of the new book, or -1 on error
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO books (title) VALUES (?)", (title,))
        conn.commit()
        new_id = cursor.lastrowid
        logger.info(f"Book '{title}' added successfully.")
        return new_id
    except sqlite3.Error as e:
        logger.info(f"Error adding book '{title}': {e}")
        return -1
    finally:
        conn.close()


def get_books() -> list[dict[Any, Any]]:
    """
    Retrieve all books from the database.

    Returns:
        list[dict]: List of dictionaries containing all books
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    df = pd.read_sql_query("SELECT id, title FROM books", conn)
    conn.close()
    return df.to_dict("records")


def remove_book(book_id: int) -> None:
    """
    Remove a book from the database.

    Args:
        book_id (int): ID of the book to remove

    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
        logger.info(f"Book '{book_id}' removed successfully.")
    except sqlite3.Error as e:
        logger.info(f"Error deleting book: {e}")
    finally:
        conn.close()


def add_book_author(book_id: int, user_id: int) -> None:
    """
    Add a user as an author of a book.

    Args:
        book_id (int): ID of the book
        user_id (int): ID of the user

    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO book_authors (book_id, user_id) VALUES (?, ?)",
            (book_id, user_id)
        )
        conn.commit()
        logger.info(f"User '{user_id}' added as author of book '{book_id}'.")
    except sqlite3.IntegrityError:
        logger.info("Error: This book-author relation already exists or foreign keys are invalid.")
    finally:
        conn.close()


def remove_book_author(book_id: int, user_id: int) -> None:
    """
    Remove a user from the authors of a book.

    Args:
        book_id (int): ID of the book
        user_id (int): ID of the user

    Returns:
        None
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM book_authors WHERE book_id = ? AND user_id = ?",
            (book_id, user_id)
        )
        conn.commit()
        logger.info(f"User '{user_id}' removed from authors of book '{book_id}'.")
    except sqlite3.Error as e:
        logger.info(f"Error removing book author: {e}")
    finally:
        conn.close()


def get_book_authors(book_id: int) -> list[dict[Any, Any]]:
    """
    Retrieve all authors of a book.

    Args:
        book_id (int): ID of the book

    Returns:
        list[dict]: List of user dicts (id, username, email) who authored the book
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    query = """
    SELECT u.id, u.username, u.email
    FROM users u
    JOIN book_authors ba ON u.id = ba.user_id
    WHERE ba.book_id = ?
    """
    df = pd.read_sql_query(query, conn, params=[book_id])
    conn.close()
    return df.to_dict("records")


def get_users() -> list[dict[Any, Any]]:
    """
    Retrieve all users from the database.

    Returns:
        list[dict]: List of user dicts containing id, username, email, and is_admin
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    df = pd.read_sql_query("SELECT id, username, email, is_admin FROM users", conn)
    conn.close()
    return df.to_dict("records")


def get_user_by_id(user_id: int) -> dict[Any, Any] | None:
    """
    Retrieve a single user by ID.

    Args:
        user_id (int): The user's ID.

    Returns:
        dict | None: User dict (id, username, email, is_admin) or None if not found.
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username, email, is_admin FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "username": row[1], "email": row[2], "is_admin": bool(row[3])}
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict[Any, Any] | None:
    """
    Retrieve a single user by email.

    Args:
        email (str): The user's email address.

    Returns:
        dict | None: User dict (id, username, email, is_admin) or None if not found.
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username, email, is_admin FROM users WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"id": row[0], "username": row[1], "email": row[2], "is_admin": bool(row[3])}
    finally:
        conn.close()


def create_user(username: str, email: str, is_admin: bool = False) -> dict[Any, Any]:
    """
    Create a new user with a generated OTP secret.

    Args:
        username (str): Unique username.
        email (str): Unique email address.
        is_admin (bool): Whether the user has admin privileges.

    Returns:
        dict: Created user info including id, username, email, is_admin, and otp_uri.

    Raises:
        ValueError: If username or email already exists.
    """
    from authenticator import generate_otp_secret, get_provisioning_uri
    otp_secret = generate_otp_secret()
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, otp_secret, int(is_admin))
        )
        conn.commit()
        new_id = cursor.lastrowid
        otp_uri = get_provisioning_uri(email, otp_secret)
        logger.info(f"User '{email}' created successfully (admin={is_admin}).")
        return {
            "id": new_id,
            "username": username,
            "email": email,
            "is_admin": is_admin,
            "otp_uri": otp_uri,
        }
    except sqlite3.IntegrityError as e:
        raise ValueError(f"User with this username or email already exists: {e}") from e
    finally:
        conn.close()


def update_user(user_id: int, username: str, email: str, is_admin: bool) -> bool:
    """
    Update a user's profile.

    Args:
        user_id (int): ID of the user to update.
        username (str): New username.
        email (str): New email address.
        is_admin (bool): New admin status.

    Returns:
        bool: True if a row was updated, False if user not found.

    Raises:
        ValueError: If the new username or email conflicts with an existing user.
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET username = ?, email = ?, is_admin = ? WHERE id = ?",
            (username, email, int(is_admin), user_id)
        )
        conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            logger.info(f"User '{user_id}' updated successfully.")
        return updated
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Username or email already taken: {e}") from e
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    """
    Delete a user from the database.

    Args:
        user_id (int): ID of the user to delete.

    Returns:
        bool: True if a row was deleted, False if user not found.
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"User '{user_id}' deleted successfully.")
        return deleted
    except sqlite3.Error as e:
        logger.info(f"Error deleting user '{user_id}': {e}")
        return False
    finally:
        conn.close()


def count_admins() -> int:
    """Return the total number of admin users."""
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        return cursor.fetchone()[0]
    finally:
        conn.close()


# VOTE FUNCTIONS

def cast_vote(idea_id: int, user_email: str, value: int) -> bool:
    """
    Cast or update a vote on an idea.

    Uses INSERT OR REPLACE so a second call simply flips the value.

    Args:
        idea_id (int): ID of the idea to vote on
        user_email (str): Email of the voting user
        value (int): Vote value — must be 1 (upvote) or -1 (downvote)

    Returns:
        bool: True on success, False if user or idea not found / value invalid
    """
    if value not in (1, -1):
        return False
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if not row:
            return False
        user_id = row[0]
        cursor.execute(
            """
            INSERT INTO idea_votes (idea_id, user_id, value)
            VALUES (?, ?, ?)
            ON CONFLICT(idea_id, user_id) DO UPDATE SET value = excluded.value,
                                                        created_at = datetime('now')
            """,
            (idea_id, user_id, value),
        )
        conn.commit()
        logger.info(f"Vote ({value}) cast by user '{user_email}' on idea '{idea_id}'.")
        return True
    except sqlite3.Error as e:
        logger.info(f"Error casting vote: {e}")
        return False
    finally:
        conn.close()


def remove_vote(idea_id: int, user_email: str) -> bool:
    """
    Remove a user's vote from an idea.

    Args:
        idea_id (int): ID of the idea
        user_email (str): Email of the voting user

    Returns:
        bool: True on success, False if user not found
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if not row:
            return False
        user_id = row[0]
        cursor.execute(
            "DELETE FROM idea_votes WHERE idea_id = ? AND user_id = ?",
            (idea_id, user_id),
        )
        conn.commit()
        logger.info(f"Vote removed by user '{user_email}' on idea '{idea_id}'.")
        return True
    except sqlite3.Error as e:
        logger.info(f"Error removing vote: {e}")
        return False
    finally:
        conn.close()


def get_idea_votes(idea_id: int) -> dict[str, int]:
    """
    Get aggregated vote data for an idea.

    Args:
        idea_id (int): ID of the idea

    Returns:
        dict: {'score': int, 'count': int}
              score = SUM of all values (+1/-1), count = total number of votes
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COALESCE(SUM(value), 0), COUNT(*) FROM idea_votes WHERE idea_id = ?",
            (idea_id,),
        )
        row = cursor.fetchone()
        return {"score": row[0], "count": row[1]}
    finally:
        conn.close()


def get_user_vote(idea_id: int, user_email: str) -> int | None:
    """
    Get the current user's vote on a specific idea.

    Args:
        idea_id (int): ID of the idea
        user_email (str): Email of the user

    Returns:
        int | None: 1, -1, or None if the user has not voted
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT v.value FROM idea_votes v
            JOIN users u ON v.user_id = u.id
            WHERE v.idea_id = ? AND u.email = ?
            """,
            (idea_id, user_email),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# IMPACT COMMENT FUNCTIONS

def get_idea_book_id(idea_id: int) -> int | None:
    """
    Get the book_id of an idea.

    Args:
        idea_id (int): ID of the idea

    Returns:
        int | None: book_id if found, None otherwise
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT book_id FROM ideas WHERE id = ?", (idea_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def is_book_author(book_id: int, user_email: str) -> bool:
    """
    Check whether a user is an author of a given book.

    Args:
        book_id (int): ID of the book
        user_email (str): Email of the user

    Returns:
        bool: True if the user is a book author, False otherwise
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 1 FROM book_authors ba
            JOIN users u ON ba.user_id = u.id
            WHERE ba.book_id = ? AND u.email = ?
            """,
            (book_id, user_email),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def create_impact_comment(idea_id: int, user_email: str, content: str) -> int | None:
    """
    Create an impact comment on an idea.

    Args:
        idea_id (int): ID of the idea
        user_email (str): Email of the commenting user
        content (str): Text content of the comment

    Returns:
        int | None: ID of the new comment, or None if user not found
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_email,))
        row = cursor.fetchone()
        if not row:
            return None
        user_id = row[0]
        cursor.execute(
            "INSERT INTO impact_comments (idea_id, user_id, content) VALUES (?, ?, ?)",
            (idea_id, user_id, content),
        )
        conn.commit()
        comment_id = cursor.lastrowid
        logger.info(f"Impact comment created by '{user_email}' on idea '{idea_id}'.")
        return comment_id
    except sqlite3.Error as e:
        logger.info(f"Error creating impact comment: {e}")
        return None
    finally:
        conn.close()


def get_idea_impact_comments(idea_id: int) -> list[dict]:
    """
    Get all impact comments for an idea.

    Args:
        idea_id (int): ID of the idea

    Returns:
        list[dict]: List of comment dicts with keys: id, idea_id, user_id,
                    username, user_email, content, created_at
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ic.id, ic.idea_id, ic.user_id, u.username, u.email AS user_email,
                   ic.content, ic.created_at
            FROM impact_comments ic
            JOIN users u ON ic.user_id = u.id
            WHERE ic.idea_id = ?
            ORDER BY ic.created_at ASC
            """,
            (idea_id,),
        )
        rows = cursor.fetchall()
        cols = ["id", "idea_id", "user_id", "username", "user_email", "content", "created_at"]
        return [dict(zip(cols, row, strict=True)) for row in rows]
    finally:
        conn.close()


def get_book_impact_comments(book_id: int) -> list[dict]:
    """
    Get all impact comments for all ideas in a book.

    Args:
        book_id (int): ID of the book

    Returns:
        list[dict]: List of comment dicts with keys: id, idea_id, idea_title,
                    username, content, created_at
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT ic.id, ic.idea_id, i.title AS idea_title, u.username,
                   ic.content, ic.created_at
            FROM impact_comments ic
            JOIN ideas i ON ic.idea_id = i.id
            JOIN users u ON ic.user_id = u.id
            WHERE i.book_id = ?
            ORDER BY i.id, ic.created_at ASC
            """,
            (book_id,),
        )
        rows = cursor.fetchall()
        cols = ["id", "idea_id", "idea_title", "username", "content", "created_at"]
        return [dict(zip(cols, row, strict=True)) for row in rows]
    finally:
        conn.close()


def update_impact_comment(comment_id: int, user_email: str, content: str) -> bool:
    """
    Update an impact comment (owner only).

    Args:
        comment_id (int): ID of the comment to update
        user_email (str): Email of the requesting user (must own the comment)
        content (str): New text content

    Returns:
        bool: True if updated, False if not found or not the owner
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE impact_comments
            SET content = ?
            WHERE id = ? AND user_id = (SELECT id FROM users WHERE email = ?)
            """,
            (content, comment_id, user_email),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.info(f"Error updating impact comment: {e}")
        return False
    finally:
        conn.close()


def delete_impact_comment(comment_id: int, user_email: str, is_admin: bool) -> bool:
    """
    Delete an impact comment.

    Admins can delete any comment; regular users can only delete their own.

    Args:
        comment_id (int): ID of the comment to delete
        user_email (str): Email of the requesting user
        is_admin (bool): Whether the requesting user is an admin

    Returns:
        bool: True if deleted, False if not found or not authorized
    """
    conn = sqlite3.connect(os.getenv('NAME_DB'))
    cursor = conn.cursor()
    try:
        if is_admin:
            cursor.execute("DELETE FROM impact_comments WHERE id = ?", (comment_id,))
        else:
            cursor.execute(
                """
                DELETE FROM impact_comments
                WHERE id = ? AND user_id = (SELECT id FROM users WHERE email = ?)
                """,
                (comment_id, user_email),
            )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.info(f"Error deleting impact comment: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Regenerate all embeddings')
    parser.add_argument('-e', '--embedding', help='regenerate embeddings for chromadb', action="store_true")
    args = parser.parse_args()
    set_env_var()
    if args.embedding:
        embed_all_ideas()
