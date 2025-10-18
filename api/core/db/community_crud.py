from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from sqlalchemy.orm import selectinload

from api.core.models import Community, User, UserCommunity, CommunityModerator, CommunitySkill, Skill
from api.core.schemas import CommunityCreate, CommunityUpdate
from api.core.db.user_crud import get_or_create_skill


async def get_community_by_id(session: AsyncSession, community_id: int) -> Optional[Community]:
    result = await session.execute(
        select(Community)
        .where(Community.id == community_id)
        .options(
            selectinload(Community.owner),
            selectinload(Community.members),
            selectinload(Community.moderators),
            selectinload(Community.skills),
            selectinload(Community.posts),
        )
    )
    community = result.scalar_one_or_none()
    if community:
        # populate derived counts for serialization
        community.member_count = len(community.members or [])
        community.moderator_count = len(community.moderators or [])
    return community


async def get_communities(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[Community]:
    result = await session.execute(
        select(Community)
        .options(
            selectinload(Community.owner),
            selectinload(Community.members),
            selectinload(Community.moderators),
            selectinload(Community.skills),
        )
        .offset(skip).limit(limit)
    )
    communities = result.scalars().all()
    for c in communities:
        c.member_count = len(c.members or [])
        c.moderator_count = len(c.moderators or [])
    return communities


async def get_user_communities(session: AsyncSession, user_id: int) -> List[Community]:
    result = await session.execute(
        select(Community)
        .join(UserCommunity)
        .where(UserCommunity.user_id == user_id)
        .options(
            selectinload(Community.owner),
            selectinload(Community.members),
            selectinload(Community.moderators),
            selectinload(Community.skills),
        )
    )
    communities = result.scalars().all()
    for c in communities:
        c.member_count = len(c.members or [])
        c.moderator_count = len(c.moderators or [])
    return communities


async def get_owned_communities(session: AsyncSession, user_id: int) -> List[Community]:
    result = await session.execute(
        select(Community)
        .where(Community.owner_id == user_id)
        .options(
            selectinload(Community.owner),
            selectinload(Community.members),
            selectinload(Community.moderators),
            selectinload(Community.skills),
        )
    )
    communities = result.scalars().all()
    for c in communities:
        c.member_count = len(c.members or [])
        c.moderator_count = len(c.moderators or [])
    return communities


async def update_community_skills(session: AsyncSession, community: Community, skill_names: List[str]):
    """Update community skills - clear existing and add new ones."""
    # Clear existing skills
    if community.skills:
        community.skills.clear()
    
    # Add new skills
    for skill_name in skill_names:
        skill = await get_or_create_skill(session, skill_name)
        community.skills.append(skill)


async def create_community(session: AsyncSession, community_in: CommunityCreate, owner_id: int) -> Community:
    """Create a new community."""
    community_data = community_in.model_dump(exclude={"skills"})
    
    db_community = Community(
        **community_data,
        owner_id=owner_id
    )

    session.add(db_community)
    await session.flush()

    # Add owner as first member and moderator
    user_community = UserCommunity(
        user_id=owner_id,
        community_id=db_community.id,
        role="admin"
    )
    session.add(user_community)

    # Add owner as moderator
    moderator = CommunityModerator(
        user_id=owner_id,
        community_id=db_community.id
    )
    session.add(moderator)

    # Handle skills
    if community_in.skills:
        await update_community_skills(session, db_community, community_in.skills)

    await session.commit()
    await session.refresh(db_community)
    return db_community


async def update_community(session: AsyncSession, community_id: int, community_in: CommunityUpdate) -> Optional[Community]:
    """Update community information."""
    db_community = await get_community_by_id(session, community_id)
    if not db_community:
        return None

    # Update base community fields
    update_data = community_in.model_dump(exclude_unset=True, exclude={"skills"})
    for field, value in update_data.items():
        setattr(db_community, field, value)

    # Update skills if provided
    if community_in.skills is not None:
        await update_community_skills(session, db_community, community_in.skills)

    await session.commit()
    await session.refresh(db_community)
    return db_community


async def delete_community(session: AsyncSession, community_id: int) -> bool:
    """Delete a community."""
    db_community = await get_community_by_id(session, community_id)
    if not db_community:
        return False
    await session.delete(db_community)
    await session.commit()
    return True


async def join_community(session: AsyncSession, community_id: int, user_id: int) -> bool:
    """Add user to community."""
    # Ensure community exists to avoid FK violation
    exists_result = await session.execute(
        select(Community.id).where(Community.id == community_id)
    )
    if exists_result.scalar_one_or_none() is None:
        return False

    # Check if user is already a member
    result = await session.execute(
        select(UserCommunity)
        .where(
            and_(
                UserCommunity.user_id == user_id,
                UserCommunity.community_id == community_id
            )
        )
    )
    existing_membership = result.scalar_one_or_none()
    
    if existing_membership:
        return True  # Already a member

    # Add user to community
    user_community = UserCommunity(
        user_id=user_id,
        community_id=community_id,
        role="member"
    )
    session.add(user_community)
    await session.commit()
    return True


async def leave_community(session: AsyncSession, community_id: int, user_id: int) -> bool:
    """Remove user from community."""
    result = await session.execute(
        select(UserCommunity)
        .where(
            and_(
                UserCommunity.user_id == user_id,
                UserCommunity.community_id == community_id
            )
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        return False

    # Remove user from community
    await session.delete(membership)
    
    # Also remove from moderators if they were a moderator
    result = await session.execute(
        select(CommunityModerator)
        .where(
            and_(
                CommunityModerator.user_id == user_id,
                CommunityModerator.community_id == community_id
            )
        )
    )
    moderator = result.scalar_one_or_none()
    if moderator:
        await session.delete(moderator)
    
    await session.commit()
    return True


async def add_moderator(session: AsyncSession, community_id: int, user_id: int, owner_id: int) -> bool:
    """Add moderator to community (only owner can do this)."""
    # Verify the requester is the owner
    community = await get_community_by_id(session, community_id)
    if not community or community.owner_id != owner_id:
        return False

    # Check if user is already a moderator
    result = await session.execute(
        select(CommunityModerator)
        .where(
            and_(
                CommunityModerator.user_id == user_id,
                CommunityModerator.community_id == community_id
            )
        )
    )
    existing_moderator = result.scalar_one_or_none()
    
    if existing_moderator:
        return True  # Already a moderator

    # Add user as moderator
    moderator = CommunityModerator(
        user_id=user_id,
        community_id=community_id
    )
    session.add(moderator)
    await session.commit()
    return True


async def remove_moderator(session: AsyncSession, community_id: int, user_id: int, owner_id: int) -> bool:
    """Remove moderator from community (only owner can do this)."""
    # Verify the requester is the owner
    community = await get_community_by_id(session, community_id)
    if not community or community.owner_id != owner_id:
        return False

    # Find and remove moderator
    result = await session.execute(
        select(CommunityModerator)
        .where(
            and_(
                CommunityModerator.user_id == user_id,
                CommunityModerator.community_id == community_id
            )
        )
    )
    moderator = result.scalar_one_or_none()
    
    if not moderator:
        return False

    await session.delete(moderator)
    await session.commit()
    return True


async def is_community_owner(session: AsyncSession, community_id: int, user_id: int) -> bool:
    """Check if user is the owner of the community."""
    result = await session.execute(
        select(Community)
        .where(
            and_(
                Community.id == community_id,
                Community.owner_id == user_id
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def is_community_moderator(session: AsyncSession, community_id: int, user_id: int) -> bool:
    """Check if user is a moderator of the community."""
    result = await session.execute(
        select(CommunityModerator)
        .where(
            and_(
                CommunityModerator.community_id == community_id,
                CommunityModerator.user_id == user_id
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def is_community_member(session: AsyncSession, community_id: int, user_id: int) -> bool:
    """Check if user is a member of the community."""
    result = await session.execute(
        select(UserCommunity)
        .where(
            and_(
                UserCommunity.community_id == community_id,
                UserCommunity.user_id == user_id
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def update_community_avatar(session: AsyncSession, community_id: int, avatar_url: str) -> Optional[Community]:
    """Update community avatar."""
    db_community = await get_community_by_id(session, community_id)
    if not db_community:
        return None
    
    db_community.avatar_url = avatar_url
    await session.commit()
    await session.refresh(db_community)
    return db_community


async def delete_community_avatar(session: AsyncSession, community_id: int) -> Optional[Community]:
    """Delete community avatar."""
    db_community = await get_community_by_id(session, community_id)
    if not db_community:
        return None
    
    db_community.avatar_url = None
    await session.commit()
    await session.refresh(db_community)
    return db_community