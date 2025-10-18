from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from fastapi.responses import RedirectResponse

from api.core.db.user_crud import (
    get_user_by_id, get_users, create_user, delete_user,
    authenticate_user, change_user_password, get_user_by_email,
    update_current_user as update_current_user_crud, add_skill_to_user, remove_skill_from_user, 
    get_all_skills, get_user_skills, get_user_by_vk_id, update_user_vk_info, 
    create_user_from_vk, update_user_profile_photo, delete_user_profile_photo
)
from api.core.schemas import UserCreate, UserRead, UserLogin, Token, UserUpdate, UserChangePassword, VKAuthRequest, VKAuthResponse
from api.core.database import get_async_session
from api.core.security import create_access_token
from api.core.dependencies import get_current_user, get_current_active_user
from api.core.models import User
from api.core.vk_oauth import vk_oauth_service
from api.core.file_upload import file_upload_service

router = APIRouter(prefix="/users", tags=["users"])


# --- Authentication Endpoints ---
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, session: AsyncSession = Depends(get_async_session)):
    """Create a new user."""
    # Check if user already exists by email
    existing_user = await get_user_by_email(session, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    user = await create_user(session, user_in)
    return user


@router.post("/login", response_model=Token)
async def login_user(user_in: UserLogin, session: AsyncSession = Depends(get_async_session)):
    """Login user and return access token."""
    user = await authenticate_user(session, user_in.email, user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"user_id": user.id, "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# --- Current User Endpoints ---
@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user


@router.put("/me", response_model=UserRead)
async def update_current_user(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update current user information."""
    updated_user = await update_current_user_crud(session, current_user.id, user_in)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error updating user"
        )
    return updated_user


@router.post("/me/change-password")
async def change_current_user_password(
    password_data: UserChangePassword,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Change current user password."""
    success = await change_user_password(
        session, 
        current_user.id, 
        password_data.current_password, 
        password_data.new_password
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    return {"message": "Password changed successfully"}


# --- Profile Photo Endpoints ---
@router.put("/me/profile-photo", response_model=UserRead)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Upload or update user profile photo."""
    try:
        # Upload file
        photo_url = await file_upload_service.upload_profile_photo(file, current_user.id)
        
        # Update user profile photo in database
        user = await update_user_profile_photo(session, current_user.id, photo_url)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error updating profile photo"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/me/profile-photo", response_model=UserRead)
async def delete_profile_photo(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete user profile photo."""
    if not current_user.profile_photo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile photo to delete"
        )
    
    # Delete file from storage
    await file_upload_service.delete_file(current_user.profile_photo)
    
    # Update user in database
    user = await delete_user_profile_photo(session, current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error deleting profile photo"
        )
    return user


# --- Skills Endpoints ---
@router.get("/me/skills")
async def get_current_user_skills(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get current user skills."""
    skills = await get_user_skills(session, current_user.id)
    return {"skills": skills}


@router.post("/me/skills")
async def add_skill_to_current_user(
    skill_name: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Add a skill to current user."""
    success = await add_skill_to_user(session, current_user.id, skill_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error adding skill"
        )
    return {"message": "Skill added successfully"}


@router.delete("/me/skills/{skill_name}")
async def remove_skill_from_current_user(
    skill_name: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Remove a skill from current user."""
    success = await remove_skill_from_user(session, current_user.id, skill_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error removing skill or skill not found"
        )
    return {"message": "Skill removed successfully"}


@router.get("/skills/all")
async def get_all_available_skills(session: AsyncSession = Depends(get_async_session)):
    """Get all available skills."""
    skills = await get_all_skills(session)
    return [skill.name for skill in skills]


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete current user account."""
    success = await delete_user(session, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error deleting user"
        )
    return None


# --- User Management Endpoints ---
@router.get("/", response_model=List[UserRead])
async def read_users(
    skip: int = 0, 
    limit: int = 100, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get list of users."""
    users = await get_users(session, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserRead)
async def read_user(
    user_id: int, 
    session: AsyncSession = Depends(get_async_session)
):
    """Get user by ID."""
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
    return user


# --- VK OAuth Endpoints ---
@router.get("/auth/vk")
async def vk_auth_start():
    """Redirect to VK OAuth page with state"""
    payload = vk_oauth_service.get_authorization_url()
    return RedirectResponse(payload["url"])


@router.get("/auth/vk/url")
async def vk_auth_start_url():
    """Return VK OAuth URL and state as JSON (for SPA/Swagger)"""
    return vk_oauth_service.get_authorization_url()


@router.get("/auth/vk/callback", response_model=VKAuthResponse)
async def vk_auth_callback(
    code: str,
    state: str | None = None,
    session: AsyncSession = Depends(get_async_session)
):
    """Handle VK OAuth callback"""
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code is required"
        )
    # validate state
    if not vk_oauth_service.validate_and_consume_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state"
        )

    # Exchange code for access token
    token_data = await vk_oauth_service.get_access_token(code)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get access token from VK"
        )

    access_token = token_data["access_token"]
    vk_user_id = token_data["user_id"]
    email = token_data.get("email")

    # Get user info from VK
    vk_user_info = await vk_oauth_service.get_user_info(access_token, vk_user_id)
    if not vk_user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from VK"
        )

    # Use email from token if available (more reliable)
    if email:
        vk_user_info.email = email

    # Check if user already exists with this VK ID
    existing_user = await get_user_by_vk_id(session, vk_user_id)
    is_new_user = False

    if existing_user:
        # Update user info from VK
        user = await update_user_vk_info(session, existing_user.id, vk_user_info)
    else:
        # Check if user exists with the same email
        if vk_user_info.email:
            existing_user_by_email = await get_user_by_email(session, vk_user_info.email)
            if existing_user_by_email:
                # Link VK account to existing user
                existing_user_by_email.vk_id = vk_user_id
                existing_user_by_email.vk_avatar = vk_user_info.photo_200
                await session.commit()
                user = existing_user_by_email
            else:
                # Create new user
                user = await create_user_from_vk(session, vk_user_info)
                is_new_user = True
        else:
            # Create new user without email
            user = await create_user_from_vk(session, vk_user_info)
            is_new_user = True

    # Create JWT token
    jwt_token = create_access_token(data={"user_id": user.id, "email": user.email})
    return VKAuthResponse(
        access_token=jwt_token,
        token_type="bearer",
        is_new_user=is_new_user
    )


@router.post("/auth/vk", response_model=VKAuthResponse)
async def vk_auth_direct(
    auth_data: VKAuthRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Handle VK OAuth with direct code (for mobile apps)"""
    return await vk_auth_callback(auth_data.code, session)


@router.get("/me/vk-unlink")
async def unlink_vk_account(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Unlink VK account from user profile"""
    if not current_user.vk_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VK account is not linked"
        )
    
    current_user.vk_id = None
    current_user.vk_avatar = None
    await session.commit()
    
    return {"message": "VK account unlinked successfully"}