from pydantic import BaseModel, EmailStr, ConfigDict, field_serializer, field_validator
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    patronymic: Optional[str] = ""
    description: Optional[str] = None
    contact: Optional[str] = None  # New field
    place_of_job: Optional[str] = None  # New field
    place_of_study: Optional[str] = None  # New field


class UserCreate(UserBase):
    password: str
    skills: List[str] = []


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    description: Optional[str] = None
    contact: Optional[str] = None
    place_of_job: Optional[str] = None
    place_of_study: Optional[str] = None
    skills: Optional[List[str]] = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    profile_photo: Optional[str] = None
    vk_avatar: Optional[str] = None
    skills: List[str] = []
    communities: List[str] = []
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

    @field_validator("communities", mode="before")
    @classmethod
    def _coerce_communities_before(cls, v):
        if v is None:
            return []
        try:
            return [c.title for c in v]
        except Exception:
            return v

    @field_serializer("skills", when_used="always")
    def serialize_skills(self, skills):
        return [s.name if hasattr(s, "name") else s for s in (skills or [])]

    @field_serializer("communities", when_used="always")
    def serialize_communities(self, communities):
        if not communities:
            return []
        serialized = []
        for item in communities:
            if isinstance(item, str):
                serialized.append(item)
            else:
                serialized.append(getattr(item, "title", str(item)))
        return serialized


class UserProfilePhotoUpdate(BaseModel):
    profile_photo: str  # URL of the uploaded photo