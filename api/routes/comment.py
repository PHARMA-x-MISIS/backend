from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.core.db.comment_crud import (
    create_comment, get_comment_by_id, get_post_comments, get_user_comments,
    update_comment, delete_comment, get_comment_replies
)
from api.core.schemas import CommentCreate, CommentUpdate, CommentRead
from api.core.database import get_async_session
from api.core.dependencies import get_current_user, get_current_active_user
from api.core.models import User

router = APIRouter(prefix="/comments", tags=["comments"])


@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create_new_comment(
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new comment."""
    try:
        comment = await create_comment(session, comment_in, current_user.id)
    except ValueError as e:
        msg = str(e)
        if "Post not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return CommentRead.model_validate(comment)


@router.get("/post/{post_id}", response_model=List[CommentRead])
async def read_post_comments(
    post_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get comments for a post."""
    comments = await get_post_comments(session, post_id)
    return [CommentRead.model_validate(c) for c in comments]


@router.get("/my", response_model=List[CommentRead])
async def read_my_comments(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get current user's comments."""
    comments = await get_user_comments(session, current_user.id)
    return [CommentRead.model_validate(c) for c in comments]


@router.get("/{comment_id}", response_model=CommentRead)
async def read_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get comment by ID."""
    comment = await get_comment_by_id(session, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )
    return CommentRead.model_validate(comment)


@router.get("/{comment_id}/replies", response_model=List[CommentRead])
async def read_comment_replies(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get replies to a comment."""
    replies = await get_comment_replies(session, comment_id)
    return [CommentRead.model_validate(r) for r in replies]


@router.put("/{comment_id}", response_model=CommentRead)
async def update_existing_comment(
    comment_id: int,
    comment_in: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update comment information."""
    comment = await update_comment(session, comment_id, comment_in, current_user.id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or you don't have permission to edit"
        )
    return CommentRead.model_validate(comment)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a comment."""
    success = await delete_comment(session, comment_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or you don't have permission to delete"
        )
    return None