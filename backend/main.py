from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Hashable, List, Optional, Any
import sqlite3
import uvicorn
from authenticator import verify_access
from fastapi.middleware.cors import CORSMiddleware
from config import set_env_var
from data_similarity import DataSimilarity
import logging
import os
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from data_handler import (
    init_database, get_ideas, get_user_ideas, get_idea_from_tags,
    get_content, get_tags, get_tags_from_idea, add_idea, add_tag,
    add_relation, remove_idea, remove_tag, remove_relation, update_idea, get_similar_idea
)

logger = logging.getLogger("uvicorn.error")

# JWT Configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-here-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
    """Ideam model for idea items with title, content, and tags.
    
    Attributes:
        id (int): The id of the idea.
        title (str): The name of the idea.
        content (str): The description of the idea item.
        tags (Optional[str]): Tags associated with the idea item, 
                             separated by semicolons.
    """
    id: Optional[int] = None
    title: str
    content: str
    tags: Optional[str] = None #tags are semicolon-separated

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


class LoginRequest(BaseModel):
    """Data model for login requests with email and OTP code.
    
    Attributes:
        email (str): The user's email address.
        otp_code (str): The one-time password code for verification.
    """
    email: str
    otp_code: str

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
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token.
    
    Args:
        data (dict): Data to encode in the token
        expires_delta (Optional[timedelta]): Token expiration time
        
    Returns:
        str: JWT access token
    """
    to_encode = data.copy()
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
        return {"email": email}
    except JWTError:
        raise credentials_exception from None

# GET endpoints
@app.get("/ideas", response_model=List[IdeaItem])
async def get_all_ideas(current_user: dict = Depends(get_current_user)) -> List[dict[Hashable, Any]]:
    """Get all ideas.
    
    Returns:
        List[dict[Hashable, Any]]: List of ideas with their details.
    
    Raises:
        HTTPException: If there's an error retrieving data from the database.
    """
    try:
        ideas = get_ideas()
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
async def get_ideas_by_tags(tags: str, current_user: dict = Depends(get_current_user)) -> List[dict[Hashable, str]]:
    """Get ideas by tags (semicolon separated).
    
    Args:
        tags (str): Tags to filter ideas, separated by semicolons.
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        List[dict[Hashable, str]]: List of ideas matching the specified tags.
    
    Raises:
        HTTPException: If there's an error retrieving data from the database.
    """
    try:
        ideas = get_idea_from_tags(tags)
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
async def get_all_tags(current_user: dict = Depends(get_current_user)) -> List[dict[Hashable, Any]]:
    """Get all tags.
    
    Args:
        current_user (dict): Current authenticated user from JWT token
    
    Returns:
        List[dict[Hashable, Any]]: List of all tags in the system.
    
    Raises:
        HTTPException: If there's an error retrieving tags from the database.
    """
    try:
        tags = get_tags()
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
    try:
        user_email = current_user.get("email")
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in token")
        new_id = add_idea(data.title, data.content, owner_email=user_email)
        
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
        data_similarity = DataSimilarity()
        toc = None
        toc =  data_similarity.load_toc_structure()
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
        data_similarity = DataSimilarity()
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
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": request.email}, expires_delta=access_token_expires
        )
        return {
            "status": "success", 
            "message": "Connection authorized",
            "access_token": access_token,
            "token_type": "bearer"
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid or expired code")

if __name__ == "__main__":
        
    uvicorn.run(app, host="0.0.0.0", port=8000)
