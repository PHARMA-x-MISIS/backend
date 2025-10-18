from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from sqlalchemy.orm import selectinload

from api.core.models import Post, PostPhoto, Like, User, Community
from api.core.schemas import PostCreate, PostUpdate
from api.core.db.user_crud import get_or_create_skill


async def get_post_by_id(session: AsyncSession, post_id: int) -> Optional[Post]:
    result = await session.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(
            selectinload(Post.author),
            selectinload(Post.community),
            selectinload(Post.skills),
            selectinload(Post.photos),
            selectinload(Post.likes),
            selectinload(Post.comments),
        )
    )
    return result.scalar_one_or_none()


async def get_posts(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Post]:
    result = await session.execute(
        select(Post)
        .options(
            selectinload(Post.author),
            selectinload(Post.community),
            selectinload(Post.skills),
            selectinload(Post.photos),
            selectinload(Post.likes),
        )
        .offset(skip).limit(limit)
        .order_by(Post.created_at.desc())
    )
    return result.scalars().all()


async def get_user_posts(session: AsyncSession, user_id: int) -> List[Post]:
    result = await session.execute(
        select(Post)
        .where(Post.author_id == user_id)
        .options(
            selectinload(Post.author),
            selectinload(Post.community),
            selectinload(Post.skills),
            selectinload(Post.photos),
            selectinload(Post.likes),
        )
        .order_by(Post.created_at.desc())
    )
    return result.scalars().all()


async def get_community_posts(session: AsyncSession, community_id: int, skip: int = 0, limit: int = 100) -> List[Post]:
    result = await session.execute(
        select(Post)
        .where(Post.community_id == community_id)
        .options(
            selectinload(Post.author),
            selectinload(Post.community),
            selectinload(Post.skills),
            selectinload(Post.photos),
            selectinload(Post.likes),
        )
        .offset(skip).limit(limit)
        .order_by(Post.created_at.desc())
    )
    return result.scalars().all()


async def update_post_skills(session: AsyncSession, post: Post, skill_names: List[str]):
    """Update post skills - clear existing and add new ones."""
    # Clear existing skills
    if post.skills:
        post.skills.clear()
    
    # Add new skills
    for skill_name in skill_names:
        skill = await get_or_create_skill(session, skill_name)
        post.skills.append(skill)


async def add_photos_to_post(session: AsyncSession, post_id: int, photo_urls: List[str], user_id: int) -> Optional[Post]:
    """Add photos to post."""
    post = await get_post_by_id(session, post_id)
    if not post or post.author_id != user_id:
        return None
    
    for photo_url in photo_urls:
        photo = PostPhoto(post_id=post_id, photo_url=photo_url)
        session.add(photo)
    
    await session.commit()
    await session.refresh(post)
    return post


async def remove_photo_from_post(session: AsyncSession, post_id: int, photo_id: int, user_id: int) -> bool:
    """Remove photo from post."""
    post = await get_post_by_id(session, post_id)
    if not post or post.author_id != user_id:
        return False
    
    result = await session.execute(
        select(PostPhoto).where(
            and_(
                PostPhoto.id == photo_id,
                PostPhoto.post_id == post_id
            )
        )
    )
    photo = result.scalar_one_or_none()
    
    if not photo:
        return False
    
    await session.delete(photo)
    await session.commit()
    return True


async def create_post(session: AsyncSession, post_in: PostCreate, author_id: int) -> Post:
    """Create a new post."""
    post_data = post_in.model_dump(exclude={"skills", "photo_urls"})
    
    db_post = Post(
        **post_data,
        author_id=author_id
    )

    session.add(db_post)
    await session.flush()

    # Handle skills
    if post_in.skills:
        await update_post_skills(session, db_post, post_in.skills)

    # Handle photos
    if post_in.photo_urls:
        for photo_url in post_in.photo_urls:
            photo = PostPhoto(post_id=db_post.id, photo_url=photo_url)
            session.add(photo)

    await session.commit()
    await session.refresh(db_post)
    return db_post


async def update_post(session: AsyncSession, post_id: int, post_in: PostUpdate, user_id: int) -> Optional[Post]:
    """Update post information."""
    db_post = await get_post_by_id(session, post_id)
    if not db_post or db_post.author_id != user_id:
        return None

    # Update base post fields
    update_data = post_in.model_dump(exclude_unset=True, exclude={"skills"})
    for field, value in update_data.items():
        setattr(db_post, field, value)

    # Update skills if provided
    if post_in.skills is not None:
        await update_post_skills(session, db_post, post_in.skills)

    await session.commit()
    await session.refresh(db_post)
    return db_post


async def delete_post(session: AsyncSession, post_id: int, user_id: int) -> bool:
    """Delete a post."""
    db_post = await get_post_by_id(session, post_id)
    if not db_post or db_post.author_id != user_id:
        return False
    
    await session.delete(db_post)
    await session.commit()
    return True


async def like_post(session: AsyncSession, post_id: int, user_id: int) -> bool:
    """Like a post."""
    # Check if already liked
    result = await session.execute(
        select(Like).where(
            and_(
                Like.post_id == post_id,
                Like.user_id == user_id
            )
        )
    )
    existing_like = result.scalar_one_or_none()
    
    if existing_like:
        return True  # Already liked

    # Add like
    like = Like(post_id=post_id, user_id=user_id)
    session.add(like)
    await session.commit()
    return True


async def unlike_post(session: AsyncSession, post_id: int, user_id: int) -> bool:
    """Unlike a post."""
    result = await session.execute(
        select(Like).where(
            and_(
                Like.post_id == post_id,
                Like.user_id == user_id
            )
        )
    )
    like = result.scalar_one_or_none()
    
    if not like:
        return False

    await session.delete(like)
    await session.commit()
    return True


async def get_post_likes(session: AsyncSession, post_id: int) -> List[User]:
    """Get users who liked a post."""
    result = await session.execute(
        select(User)
        .join(Like)
        .where(Like.post_id == post_id)
    )
    return result.scalars().all()


async def is_post_author(session: AsyncSession, post_id: int, user_id: int) -> bool:
    """Check if user is the author of the post."""
    result = await session.execute(
        select(Post).where(
            and_(
                Post.id == post_id,
                Post.author_id == user_id
            )
        )
    )
    return result.scalar_one_or_none() is not None