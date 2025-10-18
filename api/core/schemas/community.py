from pydantic import BaseModel, ConfigDict, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime


class CommunityBase(BaseModel):
    title: str
    description: Optional[str] = None
    is_official: bool = False  # Changed from is_public


class CommunityCreate(CommunityBase):
    skills: List[str] = []  # New field for community skills


class CommunityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_official: Optional[bool] = None
    skills: Optional[List[str]] = None


class CommunityRead(CommunityBase):
    id: int
    owner_id: int
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_count: int = 0
    moderator_count: int = 0
    skills: List[str] = []
    model_config = ConfigDict(from_attributes=True)

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills_before(cls, v):
        if v is None:
            return []
        try:
            return [s.name for s in v]
        except Exception:
            return v

    @field_serializer("skills", when_used="always")
    def _serialize_skills(self, skills):
        return [s.name if hasattr(s, "name") else s for s in (skills or [])]


class CommunityModeratorAdd(BaseModel):
    user_id: int


class CommunityModeratorRemove(BaseModel):
    user_id: int