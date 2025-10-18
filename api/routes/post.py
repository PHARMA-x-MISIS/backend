from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from api.core.db.post_crud import (
    create_post, get_post_by_id, get_posts, get_user_posts, get_community_posts,
    update_post, delete_post, like_post, unlike_post, get_post_likes,
    add_photos_to_post, remove_photo_from_post
)
from api.core.db.community_crud import is_community_member, is_community_owner, is_community_moderator
from api.core.schemas import PostCreate, PostUpdate, PostRead, LikeResponse
from api.core.database import get_async_session
from api.core.dependencies import get_current_user, get_current_active_user
from api.core.models import User
from api.core.file_upload import file_upload_service

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_new_post(
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new post."""
    # If posting to community, verify user is owner or moderator (members cannot post)
    if post_in.community_id:
        is_owner = await is_community_owner(session, post_in.community_id, current_user.id)
        is_moderator = await is_community_moderator(session, post_in.community_id, current_user.id)
        
        if not (is_owner or is_moderator):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only community owner or moderators can create posts"
            )
    
    post = await create_post(session, post_in, current_user.id)
    return PostRead.model_validate(post)


@router.get("/", response_model=List[PostRead])
async def read_posts(
    skip: int = 0,
    limit: int = 100,
    community_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session)
):
    """Get posts (optionally filtered by community)."""
    if community_id:
        posts = await get_community_posts(session, community_id, skip=skip, limit=limit)
    else:
        posts = await get_posts(session, skip=skip, limit=limit)
    return [PostRead.model_validate(p) for p in posts]


@router.get("/my", response_model=List[PostRead])
async def read_my_posts(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get current user's posts."""
    posts = await get_user_posts(session, current_user.id)
    return [PostRead.model_validate(p) for p in posts]


@router.get("/{post_id}", response_model=PostRead)
async def read_post(
    post_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get post by ID."""
    post = await get_post_by_id(session, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return PostRead.model_validate(post)


@router.put("/{post_id}", response_model=PostRead)
async def update_existing_post(
    post_id: int,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update post information."""
    post = await update_post(session, post_id, post_in, current_user.id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or you don't have permission to edit"
        )
    return PostRead.model_validate(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_post(
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a post."""
    success = await delete_post(session, post_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or you don't have permission to delete"
        )
    return None


@router.post("/{post_id}/like", response_model=LikeResponse)
async def like_post_endpoint(
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Like a post."""
    success = await like_post(session, post_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error liking post or already liked"
        )
    
    post = await get_post_by_id(session, post_id)
    return LikeResponse(liked=True, like_count=len(post.likes))


@router.post("/{post_id}/unlike", response_model=LikeResponse)
async def unlike_post_endpoint(
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Unlike a post."""
    success = await unlike_post(session, post_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error unliking post or not liked"
        )
    
    post = await get_post_by_id(session, post_id)
    return LikeResponse(liked=False, like_count=len(post.likes))


@router.post("/{post_id}/photos")
async def add_post_photos(
    post_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Add photos to post."""
    try:
        photo_urls = []
        for file in files:
            photo_url = await file_upload_service.upload_post_photo(file, post_id)
            photo_urls.append(photo_url)
        
        await add_photos_to_post(session, post_id, photo_urls, current_user.id)
        return {"message": "Photos added successfully", "photo_urls": photo_urls}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{post_id}/photos/{photo_id}")
async def remove_post_photo(
    post_id: int,
    photo_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Remove photo from post."""
    success = await remove_photo_from_post(session, post_id, photo_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error removing photo or photo not found"
        )
    return {"message": "Photo removed successfully"}