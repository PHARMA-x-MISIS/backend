from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from sqlalchemy.orm import selectinload

from api.core.models import Comment, Post, User
from api.core.schemas import CommentCreate, CommentUpdate


async def get_comment_by_id(session: AsyncSession, comment_id: int) -> Optional[Comment]:
    result = await session.execute(
        select(Comment)
        .where(Comment.id == comment_id)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.post),
            selectinload(Comment.parent_comment),
            selectinload(Comment.replies),
        )
    )
    return result.scalar_one_or_none()


async def get_post_comments(session: AsyncSession, post_id: int) -> List[Comment]:
    """Get top-level comments for a post (without parent)."""
    result = await session.execute(
        select(Comment)
        .where(
            and_(
                Comment.post_id == post_id,
                Comment.parent_comment_id == None
            )
        )
        .options(
            selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.author),
        )
        .order_by(Comment.created_at.asc())
    )
    return result.scalars().all()


async def get_user_comments(session: AsyncSession, user_id: int) -> List[Comment]:
    result = await session.execute(
        select(Comment)
        .where(Comment.author_id == user_id)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.post),
            selectinload(Comment.parent_comment),
            selectinload(Comment.replies).selectinload(Comment.author),
        )
        .order_by(Comment.created_at.desc())
    )
    return result.scalars().all()


async def get_comment_replies(session: AsyncSession, comment_id: int) -> List[Comment]:
    """Get replies to a specific comment."""
    result = await session.execute(
        select(Comment)
        .where(Comment.parent_comment_id == comment_id)
        .options(
            selectinload(Comment.author),
            selectinload(Comment.replies).selectinload(Comment.author),
        )
        .order_by(Comment.created_at.asc())
    )
    return result.scalars().all()


async def create_comment(session: AsyncSession, comment_in: CommentCreate, author_id: int) -> Comment:
    """Create a new comment."""
    # Verify post exists
    result = await session.execute(
        select(Post).where(Post.id == comment_in.post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise ValueError("Post not found")

    # If it's a reply, verify parent comment exists and belongs to the same post
    if comment_in.parent_comment_id is not None:
        result = await session.execute(
            select(Comment).where(
                and_(
                    Comment.id == comment_in.parent_comment_id,
                    Comment.post_id == comment_in.post_id
                )
            )
        )
        parent_comment = result.scalar_one_or_none()
        if not parent_comment:
            raise ValueError("Parent comment not found or doesn't belong to this post")

    db_comment = Comment(
        **comment_in.model_dump(exclude_none=True),
        author_id=author_id
    )

    session.add(db_comment)
    await session.commit()
    await session.refresh(db_comment)
    return db_comment


async def update_comment(session: AsyncSession, comment_id: int, comment_in: CommentUpdate, user_id: int) -> Optional[Comment]:
    """Update comment information."""
    db_comment = await get_comment_by_id(session, comment_id)
    if not db_comment or db_comment.author_id != user_id:
        return None

    # Update comment fields
    update_data = comment_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_comment, field, value)

    await session.commit()
    await session.refresh(db_comment)
    return db_comment


async def delete_comment(session: AsyncSession, comment_id: int, user_id: int) -> bool:
    """Delete a comment."""
    db_comment = await get_comment_by_id(session, comment_id)
    if not db_comment or db_comment.author_id != user_id:
        return False
    
    await session.delete(db_comment)
    await session.commit()
    return True


async def is_comment_author(session: AsyncSession, comment_id: int, user_id: int) -> bool:
    """Check if user is the author of the comment."""
    result = await session.execute(
        select(Comment).where(
            and_(
                Comment.id == comment_id,
                Comment.author_id == user_id
            )
        )
    )
    return result.scalar_one_or_none() is not None