from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from sqlalchemy.orm import selectinload

from api.core.models import User, Skill, UserSkill
from api.core.schemas import UserCreate, UserUpdate
from api.core.security import get_password_hash, verify_password
import string
import secrets


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.skills),
            selectinload(User.communities),
            selectinload(User.owned_communities),
            selectinload(User.moderated_communities),
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(
        select(User)
        .where(User.email == email)
        .options(
            selectinload(User.skills),
            selectinload(User.communities),
            selectinload(User.owned_communities),
            selectinload(User.moderated_communities),
        )
    )
    return result.scalar_one_or_none()


async def get_users(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await session.execute(
        select(User)
        .options(
            selectinload(User.skills),
            selectinload(User.communities),
            selectinload(User.owned_communities),
            selectinload(User.moderated_communities),
        )
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


async def get_or_create_skill(session: AsyncSession, skill_name: str) -> Skill:
    """Get existing skill or create new one."""
    result = await session.execute(
        select(Skill).where(Skill.name == skill_name)
    )
    skill = result.scalar_one_or_none()
    
    if not skill:
        skill = Skill(name=skill_name)
        session.add(skill)
        await session.flush()
    
    return skill


async def update_user_skills(session: AsyncSession, user: User, skill_names: List[str]):
    """Update user skills without triggering lazy-load on relationship."""
    # Remove existing links directly from association table
    await session.execute(
        delete(UserSkill).where(UserSkill.user_id == user.id)
    )

    if not skill_names:
        return

    # Insert new links directly
    for skill_name in skill_names:
        skill = await get_or_create_skill(session, skill_name)
        link = UserSkill(user_id=user.id, skill_id=skill.id)
        session.add(link)


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    # Extract base user data
    user_data = user_in.model_dump(exclude={"password", "skills"})
    
    # Create user with hashed password
    db_user = User(
        **user_data,
        password=get_password_hash(user_in.password)
    )

    session.add(db_user)
    await session.flush()

    # Handle skills
    if user_in.skills:
        await update_user_skills(session, db_user, user_in.skills)

    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_current_user(session: AsyncSession, user_id: int, user_in: UserUpdate) -> Optional[User]:
    """Update current user with profile data."""
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        return None

    # Update base user fields
    update_data = user_in.model_dump(exclude_unset=True, exclude={"skills"})
    for field, value in update_data.items():
        setattr(db_user, field, value)

    # Update skills if provided
    if user_in.skills is not None:
        await update_user_skills(session, db_user, user_in.skills)

    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_user_profile_photo(session: AsyncSession, user_id: int, profile_photo_url: str) -> Optional[User]:
    """Update user profile photo."""
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        return None
    
    db_user.profile_photo = profile_photo_url
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def delete_user_profile_photo(session: AsyncSession, user_id: int) -> Optional[User]:
    """Delete user profile photo."""
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        return None
    
    db_user.profile_photo = None
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def delete_user(session: AsyncSession, user_id: int) -> bool:
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        return False
    await session.delete(db_user)
    await session.commit()
    return True


async def authenticate_user(session: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate user by email and password."""
    user = await get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.password):
        return None
    return user


async def change_user_password(session: AsyncSession, user_id: int, current_password: str, new_password: str) -> bool:
    """Change user password."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    if not verify_password(current_password, user.password):
        return False
    
    user.password = get_password_hash(new_password)
    await session.commit()
    return True


# --- Skills CRUD Operations ---
async def get_all_skills(session: AsyncSession) -> List[Skill]:
    """Get all available skills."""
    result = await session.execute(select(Skill))
    return result.scalars().all()


async def add_skill_to_user(session: AsyncSession, user_id: int, skill_name: str) -> bool:
    """Add a skill to user."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    skill = await get_or_create_skill(session, skill_name)
    
    # Check if skill already exists for user
    if skill not in user.skills:
        user.skills.append(skill)
        await session.commit()
    
    return True


async def remove_skill_from_user(session: AsyncSession, user_id: int, skill_name: str) -> bool:
    """Remove a skill from user."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    result = await session.execute(
        select(Skill).where(Skill.name == skill_name)
    )
    skill = result.scalar_one_or_none()
    
    if skill and skill in user.skills:
        user.skills.remove(skill)
        await session.commit()
        return True
    
    return False


async def get_user_skills(session: AsyncSession, user_id: int) -> List[str]:
    """Get skills for a user."""
    user = await get_user_by_id(session, user_id)
    if not user:
        return []
    
    return [skill.name for skill in user.skills]


# --- VK OAuth CRUD Operations ---
async def get_user_by_vk_id(session: AsyncSession, vk_id: int) -> Optional[User]:
    """Get user by VK ID"""
    result = await session.execute(
        select(User)
        .where(User.vk_id == vk_id)
        .options(
            selectinload(User.skills),
            selectinload(User.communities),
            selectinload(User.owned_communities),
            selectinload(User.moderated_communities),
        )
    )
    return result.scalar_one_or_none()


async def create_user_from_vk(session: AsyncSession, vk_user_info) -> User:
    """Create a new user from VK OAuth data"""
    # Generate a random password for OAuth users
    alphabet = string.ascii_letters + string.digits
    random_password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    # Create email if not provided by VK
    email = vk_user_info.email or f"vk_{vk_user_info.id}@example.com"
    
    # Check if email already exists
    existing_user = await get_user_by_email(session, email)
    if existing_user:
        # If user exists with this email, append random string
        email = f"vk_{vk_user_info.id}_{secrets.token_hex(4)}@example.com"
    
    user = User(
        email=email,
        first_name=vk_user_info.first_name,
        last_name=vk_user_info.last_name,
        password=get_password_hash(random_password),
        vk_id=vk_user_info.id,
        vk_avatar=vk_user_info.photo_200
    )
    
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_vk_info(session: AsyncSession, user_id: int, vk_user_info) -> Optional[User]:
    """Update user's VK information"""
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    user.vk_avatar = vk_user_info.photo_200
    user.first_name = vk_user_info.first_name
    user.last_name = vk_user_info.last_name
    
    await session.commit()
    await session.refresh(user)
    return user