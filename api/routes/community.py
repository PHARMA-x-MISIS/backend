from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from api.core.db.community_crud import (
    get_community_by_id, get_communities, get_user_communities, get_owned_communities,
    create_community, update_community, delete_community, join_community, leave_community,
    add_moderator, remove_moderator, is_community_owner, is_community_moderator,
    is_community_member, update_community_avatar as update_community_avatar_crud,
    delete_community_avatar as delete_community_avatar_crud
)
from api.core.db.user_crud import get_user_by_id
from api.core.schemas import CommunityCreate, CommunityUpdate, CommunityRead, CommunityModeratorAdd, CommunityModeratorRemove
from api.core.database import get_async_session
from api.core.dependencies import get_current_user, get_current_active_user
from api.core.models import User, Community
from api.core.file_upload import file_upload_service

router = APIRouter(prefix="/communities", tags=["communities"])


# --- Community CRUD Endpoints ---
@router.post("/", response_model=CommunityRead, status_code=status.HTTP_201_CREATED)
async def create_new_community(
    community_in: CommunityCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new community."""
    community = await create_community(session, community_in, current_user.id)
    return CommunityRead.model_validate(community)


@router.get("/", response_model=List[CommunityRead])
async def read_communities(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session)
):
    """Get all communities."""
    communities = await get_communities(session, skip=skip, limit=limit)
    return [CommunityRead.model_validate(c) for c in communities]


@router.get("/my", response_model=List[CommunityRead])
async def read_my_communities(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get communities the current user is a member of."""
    communities = await get_user_communities(session, current_user.id)
    return [CommunityRead.model_validate(c) for c in communities]


@router.get("/owned", response_model=List[CommunityRead])
async def read_owned_communities(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Get communities owned by the current user."""
    communities = await get_owned_communities(session, current_user.id)
    return [CommunityRead.model_validate(c) for c in communities]


@router.get("/subscriptions", response_model=List[CommunityRead])
async def list_my_subscriptions(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """List communities the current user is subscribed to (alias of /my)."""
    communities = await get_user_communities(session, current_user.id)
    return [CommunityRead.model_validate(c) for c in communities]


@router.get("/{community_id}", response_model=CommunityRead)
async def read_community(
    community_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    """Get community by ID."""
    community = await get_community_by_id(session, community_id)
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    return CommunityRead.model_validate(community)


@router.put("/{community_id}", response_model=CommunityRead)
async def update_existing_community(
    community_id: int,
    community_in: CommunityUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Update community information."""
    # Check if user is owner or moderator
    is_owner = await is_community_owner(session, community_id, current_user.id)
    is_moderator = await is_community_moderator(session, community_id, current_user.id)
    
    if not (is_owner or is_moderator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this community"
        )
    
    community = await update_community(session, community_id, community_in)
    if not community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    return CommunityRead.model_validate(community)


@router.delete("/{community_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_community(
    community_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a community (only owner can do this)."""
    if not await is_community_owner(session, community_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the community owner can delete the community"
        )
    
    success = await delete_community(session, community_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community not found"
        )
    return None


# --- Community Membership Endpoints ---
@router.post("/{community_id}/join")
async def join_existing_community(
    community_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Join a community."""
    success = await join_community(session, community_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error joining community"
        )
    return {"message": "Successfully joined the community"}


@router.post("/{community_id}/leave")
async def leave_existing_community(
    community_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Leave a community."""
    # Check if user is the owner (owners cannot leave, they must delete or transfer ownership)
    if await is_community_owner(session, community_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Community owner cannot leave the community. Transfer ownership or delete the community instead."
        )
    
    success = await leave_community(session, community_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error leaving community or not a member"
        )
    return {"message": "Successfully left the community"}



# --- Community Moderator Endpoints ---
@router.post("/{community_id}/moderators")
async def add_community_moderator(
    community_id: int,
    moderator_data: CommunityModeratorAdd,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Add a moderator to the community (only owner can do this)."""
    # Verify the target user exists
    target_user = await get_user_by_id(session, moderator_data.user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify target user is a community member
    if not await is_community_member(session, community_id, moderator_data.user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be a community member to become a moderator"
        )
    
    success = await add_moderator(session, community_id, moderator_data.user_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the community owner can add moderators"
        )
    return {"message": "Moderator added successfully"}


@router.delete("/{community_id}/moderators/{user_id}")
async def remove_community_moderator(
    community_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Remove a moderator from the community (only owner can do this)."""
    success = await remove_moderator(session, community_id, user_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the community owner can remove moderators"
        )
    return {"message": "Moderator removed successfully"}


# --- Community Avatar Endpoints ---
@router.put("/{community_id}/avatar", response_model=CommunityRead)
async def upload_community_avatar(
    community_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Upload or update community avatar."""
    # Check if user is owner or moderator
    is_owner = await is_community_owner(session, community_id, current_user.id)
    is_moderator = await is_community_moderator(session, community_id, current_user.id)
    
    if not (is_owner or is_moderator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update community avatar"
        )
    
    try:
        # Upload file
        avatar_url = await file_upload_service.upload_community_avatar(file, community_id)
        
        # Update community avatar in database
        community = await update_community_avatar_crud(session, community_id, avatar_url)
        if not community:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error updating community avatar"
            )
        return CommunityRead.model_validate(community)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{community_id}/avatar", response_model=CommunityRead)
async def delete_community_avatar(
    community_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Delete community avatar."""
    # Check if user is owner or moderator
    is_owner = await is_community_owner(session, community_id, current_user.id)
    is_moderator = await is_community_moderator(session, community_id, current_user.id)
    
    if not (is_owner or is_moderator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete community avatar"
        )
    
    community = await get_community_by_id(session, community_id)
    if not community or not community.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No community avatar to delete"
        )
    
    # Delete file from storage
    await file_upload_service.delete_file(community.avatar_url)
    
    # Update community in database
    community = await delete_community_avatar_crud(session, community_id)
    if not community:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error deleting community avatar"
        )
    return CommunityRead.model_validate(community)