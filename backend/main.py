from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Hashable, List, Optional, Any
import sqlite3
import uvicorn
from authenticator import verify_access
from fastapi.middleware.cors import CORSMiddleware
from config import set_env_var
from data_similarity import DataSimilarity
from llm_client import create_llm_client
import logging
import os
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from data_handler import (
    init_database, get_ideas, get_user_ideas, get_idea_from_tags,
    get_content, get_tags, get_tags_from_idea, add_idea, add_tag,
    add_relation, remove_idea, remove_tag, remove_relation, update_idea, get_similar_idea,
    add_book, get_books, remove_book, add_book_author, remove_book_author, get_book_authors,
    get_users, cast_vote, remove_vote, get_idea_votes, get_user_vote,
    get_user_by_id, get_user_by_email, create_user, update_user, delete_user, count_admins,
    is_book_author, get_idea_book_id, create_impact_comment, get_idea_impact_comments,
    get_book_impact_comments, update_impact_comment, delete_impact_comment,
)

logger = logging.getLogger("uvicorn.error")

# JWT Configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-here-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Initialisation of the database and variable
set_env_var()
init_database()

# Add CORS middleware
# Explicitly allow only trusted origins
origins = os.environ.get('ALLOWED_ORIGINS', '').split(',')

app = FastAPI(title="Idea Management API", description="API for managing ideas and tags with SQLite")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme for JWT authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    

# Pydantic models
class IdeaItem(BaseModel):
    """Data model for idea items with title, content, tags, and book.

    Attributes:
        id (int): The id of the idea.
        title (str): The name of the idea.
        content (str): The description of the idea item.
        tags (Optional[str]): Tags associated with the idea item,
                             separated by semicolons.
        book_id (Optional[int]): ID of the book this idea belongs to.
    """
    id: Optional[int] = None
    title: str
    content: str
    tags: Optional[str] = None  # tags are semicolon-separated
    book_id: Optional[int] = None


class BookItem(BaseModel):
    """Data model for books.

    Attributes:
        id (Optional[int]): The id of the book.
        title (str): The title of the book.
    """
    id: Optional[int] = None
    title: str


class BookAuthorItem(BaseModel):
    """Data model for book-author relationships.

    Attributes:
        book_id (int): The id of the book.
        user_id (int): The id of the user (author).
    """
    book_id: int
    user_id: int

class TagItem(BaseModel):
    """Data model for tag items.
    
    Attributes:
        name (str): The name of the tag.
    """
    name: str

class RelationItem(BaseModel):
    """Data model for relations between ideas and tags.
    
    Attributes:
        idea_id (int): The id of the idea.
        tag_name (str): The name of the tag.
    """
    idea_id: int
    tag_name: str


class VoteItem(BaseModel):
    """Data model for casting a vote on an idea.

    Attributes:
        value (int): 1 for upvote, -1 for downvote.
    """
    value: int


class ImpactCommentItem(BaseModel):
    """Data model for creating or updating an impact comment.

    Attributes:
        content (str): Text content of the impact comment.
    """
    content: str


class LoginRequest(BaseModel):
    """Data model for login requests with email and OTP code.

    Attributes:
        email (str): The user's email address.
        otp_code (str): The one-time password code for verification.
    """
    email: str
    otp_code: str


class RefreshRequest(BaseModel):
    """Payload for silent token refresh.

    Attributes:
        refresh_token (str): A valid, unexpired refresh token.
    """
    refresh_token: str


class AdminUserCreate(BaseModel):
    """Payload for admin user creation.

    Attributes:
        username (str): Unique username.
        email (str): Unique email address.
        is_admin (bool): Whether the new user has admin privileges.
    """
    username: str
    email: str
    is_admin: bool = False


class AdminUserUpdate(BaseModel):
    """Payload for admin user update.

    Attributes:
        username (str): New username.
        email (str): New email address.
        is_admin (bool): New admin status.
    """
    username: str
    email: str
    is_admin: bool

# Helper function to get database connection
def get_db():
    """Get a database connection for SQLite operations.
    
    This function creates a connection to the SQLite database and yields it
    for use in database operations. The connection is automatically closed
    after use.
    
    Yields:
        sqlite3.Connection: A SQLite database connection object.
    """
    db_path = os.environ.get('NAME_DB', 'data/knowledge.db')
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()

# JWT Utility Functions
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    jwt_kind: str = "access",
) -> str:
    """Create a JWT token (access or refresh).

    Args:
        data (dict): Data to encode in the token.
        expires_delta (Optional[timedelta]): Token expiration time.
        jwt_kind (str): Either "access" (default) or "refresh".

    Returns:
        str: Encoded JWT token.
    """
    to_encode = data.copy()
    to_encode.update({"type": jwt_kind})
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get the current user from JWT token.
    
    Args:
        token (str): JWT token from authorization header
        
    Returns:
        dict: User information from token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        if payload.get("type", "access") != "access":
            raise credentials_exception
        is_admin: bool = bool(payload.get("is_admin", False))
        return {"email": email, "is_admin": is_admin}
    except JWTError:
        raise credentials_exception from None

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency that allows access only to admin users.

    Raises:
        HTTPException: 403 if the authenticated user is not an admin.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Admin user-management endpoints
@app.get("/admin/users", response_model=List[dict])
async def admin_list_users(admin: dict = Depends(require_admin)) -> List[dict]:
    """List all users (admin only).

    Returns:
        List[dict]: All users with id, username, email, and is_admin.
    """
    try:
        return get_users()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving users: {str(e)}") from e


@app.post("/admin/users", response_model=dict, status_code=201)
async def admin_create_user(
    payload: AdminUserCreate, admin: dict = Depends(require_admin)
) -> dict:
    """Create a new user (admin only).

    Returns:
        dict: Created user info including the TOTP provisioning URI.

    Raises:
        HTTPException: 409 if username or email already exists.
    """
    try:
        user = create_user(payload.username, payload.email, payload.is_admin)
        return user
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}") from e


@app.put("/admin/users/{user_id}", response_model=dict)
async def admin_update_user(
    user_id: int, payload: AdminUserUpdate, admin: dict = Depends(require_admin)
) -> dict:
    """Update a user's profile (admin only).

    Returns:
        dict: Updated user info.

    Raises:
        HTTPException: 404 if user not found, 409 on uniqueness conflict.
    """
    try:
        updated = update_user(user_id, payload.username, payload.email, payload.is_admin)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        user = get_user_by_id(user_id)
        return user
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}") from e


@app.delete("/admin/users/{user_id}", response_model=dict)
async def admin_delete_user(
    user_id: int, admin: dict = Depends(require_admin)
) -> dict:
    """Delete a user (admin only).

    Guards:
        - Cannot delete yourself.
        - Cannot delete the last remaining admin.

    Raises:
        HTTPException: 400 on guard violations, 404 if user not found.
    """
    target = get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target["email"] == admin["email"]:
        raise HTTPException(status_code=400, detail="Cannot self-delete your own account")

    if target["is_admin"] and count_admins() <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last admin account",
        )

    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User '{user_id}' deleted successfully"}


# GET endpoints
@app.get("/ideas", response_model=List[IdeaItem])
async def get_all_ideas(
    book_id: Optional[int] = None, current_user: dict = Depends(get_current_user)
) -> List[dict[Hashable, Any]]:
    """Get all ideas, optionally filtered to a specific book.

    Args:
        book_id (Optional[int]): Optional book ID to restrict ideas to that book.

    Returns:
        List[dict[Hashable, Any]]: List of ideas with their details.

    Raises:
        HTTPException: If there's an error retrieving data from the database.
    """
    try:
        ideas = get_ideas(book_id)
        return ideas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}") from e
@app.get("/user/ideas", response_model=List[IdeaItem])
async def get_all_user_ideas(current_user: dict = Depends(get_current_user)) -> List[dict[Hashable, Any]]:
    """Get all ideas with optional limit.
    
    Args:
        current_user (dict): Current authenticated user from JWT token
        limit (int, optional): Maximum number of ideas to return. 
                              Defaults to 500.
    
    Returns:
        List[dict[Hashable, Any]]: List of ideas with their details.
    
    Raises:
        HTTPException: If there's an error retrieving data from the database.
    """
    try:
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")
        ideas = get_user_ideas(user_email)
        return ideas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data: {str(e)}") from e
@app.get("/ideas/tags/{tags}", response_model=List[IdeaItem])
async def get_ideas_by_tags(
    tags: str, book_id: Optional[int] = None, current_user: dict = Depends(get_current_user)
) -> List[dict[Hashable, str]]:
    """Get ideas by tags (semicolon separated).

    Args:
        tags (str): Tags to filter ideas, separated by semicolons.
        book_id (Optional[int]): Optional book ID to restrict ideas to a specific book.
        current_user (dict): Current authenticated user from JWT token

    Returns:
        List[dict[Hashable, str]]: List of ideas matching the specified tags.

    Raises:
        HTTPException: If there's an error retrieving data from the database.
    """
    try:
        ideas = get_idea_from_tags(tags, book_id)
        return ideas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data by tags: {str(e)}") from e
@app.get("/ideas/search/{subname}", response_model=List[IdeaItem])
async def search_ideas(subname: str, current_user: dict = Depends(get_current_user)) -> List[dict[Hashable, Any]]:
    """Search ideas by partial name.
    
    Args:
        subname (str): Partial name to search for in ideas.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        List[dict[Hashable, Any]]: List of ideas matching the search term.
    
    Raises:
        HTTPException: If there's an error searching data in the database.
    """
    try:
        data = get_similar_idea(subname)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching data: {str(e)}") from e
@app.get("/ideas/{idea_id}/content", response_model=str)
async def get_idea_content(idea_id: int, current_user: dict = Depends(get_current_user)) -> str:
    """Get content of a specific idea.
    
    Args:
        idea_id (int): The ID of the idea to retrieve content for.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        str: The content of the specified idea.
    
    Raises:
        HTTPException: If there's an error retrieving the content from the database.
    """
    try:
        content = get_content(idea_id)
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}") from e
@app.get("/tags", response_model=List[TagItem])
async def get_all_tags(
    book_id: Optional[int] = None, current_user: dict = Depends(get_current_user)
) -> List[dict[Hashable, Any]]:
    """Get all tags, optionally filtered to those used in a specific book.

    Args:
        book_id (Optional[int]): Optional book ID to restrict tags to that book.
        current_user (dict): Current authenticated user from JWT token

    Returns:
        List[dict[Hashable, Any]]: List of tags.

    Raises:
        HTTPException: If there's an error retrieving tags from the database.
    """
    try:
        tags = get_tags(book_id)
        return tags
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tags: {str(e)}") from e
@app.get("/ideas/{idea_id}/tags", response_model=List[str])
async def get_tags_for_idea(idea_id: int, current_user: dict = Depends(get_current_user)):
    """Get tags for a specific idea.
    
    Args:
        idea_id (int): The id of the idea to retrieve tags for.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        List[str]: List of tags associated with the specified idea.
    
    Raises:
        HTTPException: If there's an error retrieving tags from the database.
    """
    try:
        tags = get_tags_from_idea(idea_id)
        return tags
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tags for data: {str(e)}") from e
@app.get("/ideas/similar/{idea}", response_model=List[IdeaItem])
async def get_similar_ideas_endpoint(idea: str, current_user: dict = Depends(get_current_user)):
    """Get similar ideas based on semantic similarity.
    
    Args:
        idea (str): The name of the idea to find similar items for.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        List[IdeaItem]: List of similar ideas based on semantic similarity.
    
    Raises:
        HTTPException: If the idea is not found or there's an error 
                      retrieving similar data.
    """
    try:
        # Call the original function to get similar data
        similar_data = get_similar_idea(idea)
        return similar_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving similar ideas: {str(e)}") from e
# POST endpoints
@app.post("/ideas", response_model=dict)
async def create_idea(data: IdeaItem, current_user: dict = Depends(get_current_user)) -> dict[str, str | int]:
    """Add a new idea item.
    
    Args:
        idea (IdeaItem): The idea item data to add, including title, content, and optional tags.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the idea item was added.
    
    Raises:
        HTTPException: If there's an error adding the data to the database.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=400, detail="User email not found in token")
    if data.book_id is None:
        raise HTTPException(status_code=400, detail="book_id is required")
    try:
        new_id = add_idea(data.title, data.content, owner_email=user_email, book_id=data.book_id)
        
        # Handle tags if provided - convert string to list if needed
        if data.tags and data.tags.strip():
            # Split the semicolon-separated string into individual tags
            tags_list = [tag.strip() for tag in data.tags.split(';') if tag.strip()]
            for tag in tags_list:
                try:
                    add_tag(tag)
                    add_relation(new_id, tag)
                except Exception as e:
                    # Continue processing other tags even if one fails
                    logger.info(f"Warning: Failed to process tag '{tag}': {str(e)}")
        
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding idea: {str(e)}") from e
@app.post("/tags", response_model=dict)
async def create_tag(tag: TagItem, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Add a new tag.
    
    Args:
        tag (TagItem): The tag data to add.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the tag was added.
    
    Raises:
        HTTPException: If there's an error adding the tag to the database.
    """
    try:
        add_tag(tag.name)
        return {"message": f"Tag '{tag.name}' added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding tag: {str(e)}") from e
@app.post("/relations", response_model=dict)
async def create_relation(relation: RelationItem, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Create a relationship between data and tag.
    
    Args:
        relation (RelationItem): The relationship data containing data name and tag name.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the relationship was created.
    
    Raises:
        HTTPException: If there's an error creating the relationship in the database.
    """
    try:
        add_relation(relation.idea_id, relation.tag_name)
        return {"message": f"Relation between '{relation.idea_id}' and '{relation.tag_name}' added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating relation: {str(e)}") from e
# PUT endpoint
@app.put("/ideas/{id}", response_model=dict)
async def update_idea_item(id: int, idea: IdeaItem, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Update an existing idea.
    
    Args:
        id (int): the idea id
        idea (IdeaItem): The updated idea information including title, content, and optional tags.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the idea was updated.
    
    Raises:
        HTTPException: If there's an error updating the data in the database.
    """
    try:
        update_idea(id=id, title=idea.title, content=idea.content)
        if idea.tags and idea.tags.strip():
            # Split the semicolon-separated string into individual tags
            tags_list = [tag.strip() for tag in idea.tags.split(';') if tag.strip()]
            
            # Get current tags for this idea
            current_tags = get_tags_from_idea(id)
            
            # Convert current tags to set for easy comparison
            current_tags_set = set(current_tags)
            
            # Convert new tags to set for easy comparison
            new_tags_set = set(tags_list)
            
            # Find tags to remove (current tags not in new tags)
            tags_to_remove = current_tags_set - new_tags_set
            
            # Find tags to add (new tags not in current tags)
            tags_to_add = new_tags_set - current_tags_set
            
            # Remove obsolete relations (tags that existed before but are not in new tags)
            for tag in tags_to_remove:
                try:
                    remove_relation(id, tag)
                except Exception as e:
                    logger.info(f"Warning: Failed to remove relation for tag '{tag}': {str(e)}")
            
            # Add new relations (tags that are in new tags but didn't exist before)
            for tag in tags_to_add:
                try:
                    add_tag(tag)
                    add_relation(id, tag)
                except Exception as e:
                    # Continue processing other tags even if one fails
                    logger.info(f"Warning: Failed to process tag '{tag}': {str(e)}")
        return {"message": f"Idea '{id}' updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating idea: {str(e)}") from e
# DELETE endpoints
@app.delete("/ideas/{id}", response_model=dict)
async def delete_idea(id: int, idea: IdeaItem, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Remove a idea.
    
    Args:
        id (int): The id of the idea to remove.
        idea (IdeaItem): The idea information including title, content, and optional tags.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the idea was removed.
    
    Raises:
        HTTPException: If there's an error removing the data from the database.
    """
    try:
        remove_idea(id=id, title=idea.title)
        return {"message": f"Idea '{id}' removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing idea: {str(e)}") from e
@app.delete("/tags/{name}", response_model=dict)
async def delete_tag(name: str, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Remove a tag.
    
    Args:
        name (str): The name of the tag to remove.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the tag was removed.
    
    Raises:
        HTTPException: If there's an error removing the tag from the database.
    """
    try:
        remove_tag(name)
        return {"message": f"Tag '{name}' removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing tag: {str(e)}") from e
@app.delete("/relations", response_model=dict)
async def delete_relation(relation: RelationItem, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Remove a relationship between data and tag.
    
    Args:
        relation (RelationItem): The relationship data containing idea id and tag name.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        dict[str, str]: A success message indicating the relationship was removed.
    
    Raises:
        HTTPException: If there's an error removing the relationship from the database.
    """
    try:
        remove_relation(relation.idea_id, relation.tag_name)
        return {"message": f"Relation between '{relation.idea_id}' and '{relation.tag_name}' removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing relation: {str(e)}") from e
# Book endpoints
@app.get("/books", response_model=List[BookItem])
async def get_all_books(current_user: dict = Depends(get_current_user)) -> List[dict]:
    """Get all books.

    Returns:
        List[BookItem]: List of all books.
    """
    try:
        return get_books()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving books: {str(e)}") from e


@app.post("/books", response_model=dict)
async def create_book(book: BookItem, current_user: dict = Depends(get_current_user)) -> dict:
    """Create a new book.

    Args:
        book (BookItem): The book data to create.

    Returns:
        dict: The id of the created book.
    """
    try:
        new_id = add_book(book.title)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating book: {str(e)}") from e


@app.delete("/books/{book_id}", response_model=dict)
async def delete_book(book_id: int, current_user: dict = Depends(get_current_user)) -> dict:
    """Remove a book.

    Args:
        book_id (int): The id of the book to remove.

    Returns:
        dict: A success message.
    """
    try:
        remove_book(book_id)
        return {"message": f"Book '{book_id}' removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing book: {str(e)}") from e


@app.get("/books/{book_id}/authors", response_model=List[dict])
async def get_authors_for_book(book_id: int, current_user: dict = Depends(get_current_user)) -> List[dict]:
    """Get all authors of a book.

    Args:
        book_id (int): The id of the book.

    Returns:
        List[dict]: List of user dicts (id, username, email).
    """
    try:
        return get_book_authors(book_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving book authors: {str(e)}") from e


@app.post("/book-authors", response_model=dict)
async def create_book_author(item: BookAuthorItem, current_user: dict = Depends(get_current_user)) -> dict:
    """Add a user as an author of a book.

    Args:
        item (BookAuthorItem): The book_id and user_id to link.

    Returns:
        dict: A success message.
    """
    try:
        add_book_author(item.book_id, item.user_id)
        return {"message": f"User '{item.user_id}' added as author of book '{item.book_id}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding book author: {str(e)}") from e


@app.delete("/book-authors", response_model=dict)
async def delete_book_author(item: BookAuthorItem, current_user: dict = Depends(get_current_user)) -> dict:
    """Remove a user from the authors of a book.

    Args:
        item (BookAuthorItem): The book_id and user_id to unlink.

    Returns:
        dict: A success message.
    """
    try:
        remove_book_author(item.book_id, item.user_id)
        return {"message": f"User '{item.user_id}' removed from authors of book '{item.book_id}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing book author: {str(e)}") from e


@app.get("/users", response_model=List[dict])
async def get_all_users(current_user: dict = Depends(get_current_user)) -> List[dict]:
    """List all registered users (id, username, email).

    Returns:
        List[dict]: List of user dicts.
    """
    try:
        return get_users()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving users: {str(e)}") from e


# Vote endpoints
@app.get("/ideas/{idea_id}/votes", response_model=dict)
async def get_votes_for_idea(idea_id: int, current_user: dict = Depends(get_current_user)) -> dict:
    """Get aggregated vote data for an idea plus the current user's vote.

    Args:
        idea_id (int): ID of the idea.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: {'score': int, 'count': int, 'user_vote': int | None}
    """
    try:
        user_email = current_user.get("email")
        votes = get_idea_votes(idea_id)
        votes["user_vote"] = get_user_vote(idea_id, user_email)
        return votes
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving votes: {str(e)}") from e


@app.post("/ideas/{idea_id}/vote", response_model=dict)
async def vote_for_idea(idea_id: int, vote: VoteItem, current_user: dict = Depends(get_current_user)) -> dict:
    """Cast or update a vote on an idea.

    Args:
        idea_id (int): ID of the idea to vote on.
        vote (VoteItem): Vote data containing value (1 or -1).
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: Updated vote summary.

    Raises:
        HTTPException: 400 if value is not 1 or -1, 404 if user not found.
    """
    if vote.value not in (1, -1):
        raise HTTPException(status_code=400, detail="Vote value must be 1 or -1")
    user_email = current_user.get("email")
    try:
        success = cast_vote(idea_id, user_email, vote.value)
        if not success:
            raise HTTPException(status_code=404, detail="User or idea not found")
        votes = get_idea_votes(idea_id)
        votes["user_vote"] = vote.value
        return votes
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error casting vote: {str(e)}") from e


@app.delete("/ideas/{idea_id}/vote", response_model=dict)
async def delete_vote_for_idea(idea_id: int, current_user: dict = Depends(get_current_user)) -> dict:
    """Remove the current user's vote from an idea.

    Args:
        idea_id (int): ID of the idea.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: Updated vote summary.

    Raises:
        HTTPException: 404 if user not found.
    """
    user_email = current_user.get("email")
    try:
        success = remove_vote(idea_id, user_email)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        votes = get_idea_votes(idea_id)
        votes["user_vote"] = None
        return votes
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing vote: {str(e)}") from e


# Impact comment endpoints

@app.get("/ideas/{idea_id}/impact-comments", response_model=list)
async def get_impact_comments_for_idea(idea_id: int, current_user: dict = Depends(get_current_user)) -> list:
    """Get all impact comments for an idea.

    Args:
        idea_id (int): ID of the idea.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        list: List of impact comment dicts.
    """
    try:
        return get_idea_impact_comments(idea_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving impact comments: {str(e)}") from e


@app.post("/ideas/{idea_id}/impact-comments", response_model=dict)
async def create_impact_comment_for_idea(
    idea_id: int, comment: ImpactCommentItem, current_user: dict = Depends(get_current_user)
) -> dict:
    """Create an impact comment on an idea.

    Only users who are authors of the idea's book can comment.

    Args:
        idea_id (int): ID of the idea.
        comment (ImpactCommentItem): Comment content.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: The created comment.

    Raises:
        HTTPException: 404 if idea not found, 403 if not a book author.
    """
    user_email = current_user.get("email")
    try:
        book_id = get_idea_book_id(idea_id)
        if book_id is None:
            raise HTTPException(status_code=404, detail="Idea not found")
        if not is_book_author(book_id, user_email):
            raise HTTPException(status_code=403, detail="Not a book author")
        comment_id = create_impact_comment(idea_id, user_email, comment.content)
        if comment_id is None:
            raise HTTPException(status_code=404, detail="User not found")
        comments = get_idea_impact_comments(idea_id)
        created = next((c for c in comments if c["id"] == comment_id), None)
        return created
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating impact comment: {str(e)}") from e


@app.put("/impact-comments/{comment_id}", response_model=dict)
async def update_impact_comment_endpoint(
    comment_id: int, comment: ImpactCommentItem, current_user: dict = Depends(get_current_user)
) -> dict:
    """Update an impact comment (owner only).

    Args:
        comment_id (int): ID of the comment to update.
        comment (ImpactCommentItem): New comment content.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 403 if the user does not own the comment.
    """
    user_email = current_user.get("email")
    try:
        success = update_impact_comment(comment_id, user_email, comment.content)
        if not success:
            raise HTTPException(status_code=403, detail="Comment not found or not the owner")
        return {"detail": "Comment updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating impact comment: {str(e)}") from e


@app.delete("/impact-comments/{comment_id}", response_model=dict)
async def delete_impact_comment_endpoint(
    comment_id: int, current_user: dict = Depends(get_current_user)
) -> dict:
    """Delete an impact comment.

    Admins can delete any comment; regular users can only delete their own.

    Args:
        comment_id (int): ID of the comment to delete.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: 403 if not authorized to delete.
    """
    user_email = current_user.get("email")
    is_admin = current_user.get("is_admin", False)
    try:
        success = delete_impact_comment(comment_id, user_email, is_admin)
        if not success:
            raise HTTPException(status_code=403, detail="Comment not found or not authorized")
        return {"detail": "Comment deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting impact comment: {str(e)}") from e


@app.get("/books/{book_id}/impact-comments", response_model=list)
async def get_impact_comments_for_book(book_id: int, current_user: dict = Depends(get_current_user)) -> list:
    """Get all impact comments for all ideas in a book.

    Used by the TableOfContents page for the markdown export.

    Args:
        book_id (int): ID of the book.
        current_user (dict): Current authenticated user from JWT token.

    Returns:
        list: List of comment dicts with idea_title included.
    """
    try:
        return get_book_impact_comments(book_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving book impact comments: {str(e)}") from e


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}

# TOC endpoint
@app.get("/toc/structure", response_model=list)
async def get_toc_structure(current_user: dict = Depends(get_current_user)) -> list:
    """Get hierarchical table of contents structure from all data.
    
    Args:
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        list: Hierarchical table of contents structure generated from all data.
    
    Raises:
        HTTPException: If there's an error generating the TOC structure.
    """
    
    try:
        llm = create_llm_client()
        data_similarity = DataSimilarity(llm=llm)
        toc = None
        toc = data_similarity.load_toc_structure()
        if toc is not None:
            return toc
        else:
            return data_similarity.generate_toc_structure()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating TOC structure: {str(e)}") from e
@app.post("/toc/update", response_model=dict)
async def update_toc_structure(current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    """Update the hierarchical table of contents structure

    Args:
        current_user (dict): Current authenticated user from JWT token

    Returns:
        list: Hierarchical table of contents structure generated from all data.

    Raises:
        HTTPException: If there's an error updating the toc.
    """
    try:
        llm = create_llm_client()
        data_similarity = DataSimilarity(llm=llm)
        data_similarity.generate_toc_structure()
        return {"message": "toc added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating TOC structure: {str(e)}") from e
@app.post("/verify-otp")
def verify_otp(request: LoginRequest) -> dict[str, str]:
    """Verify the OTP code sent by React and return JWT token.
    
    Args:
        request (LoginRequest): The login request containing email and OTP code.
    
    Returns:
        dict[str, str]: A success response with JWT token if verification passes.
    
    Raises:
        HTTPException: If the OTP code is invalid or expired.
    """
    # Check the 6-digit code
    if verify_access(request.email, request.otp_code):
        try:
            user = get_user_by_email(request.email)
            is_admin = bool(user["is_admin"]) if user else False
        except Exception:
            is_admin = False
        token_data = {"sub": request.email, "is_admin": is_admin}
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            jwt_kind="access",
        )
        refresh_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            jwt_kind="refresh",
        )
        return {
            "status": "success",
            "message": "Connection authorized",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid or expired code")


@app.post("/auth/refresh")
def refresh_tokens(request: RefreshRequest) -> dict[str, str]:
    """Exchange a valid refresh token for a new access + refresh token pair.

    Args:
        request (RefreshRequest): Body containing the refresh_token.

    Returns:
        dict[str, str]: New access_token and refresh_token.

    Raises:
        HTTPException: 401 if the token is invalid, expired, or not a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        tok_kind: str = payload.get("type", "access")
        if email is None or tok_kind != "refresh":
            raise credentials_exception
        is_admin: bool = bool(payload.get("is_admin", False))
    except JWTError:
        raise credentials_exception from None

    token_data = {"sub": email, "is_admin": is_admin}
    new_access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        jwt_kind="access",
    )
    new_refresh_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        jwt_kind="refresh",
    )
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


if __name__ == "__main__":
        
    uvicorn.run(app, host="0.0.0.0", port=8000)
