from pydantic import BaseModel, ConfigDict, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime


class PostBase(BaseModel):
    text: str


class PostCreate(PostBase):
    community_id: Optional[int] = None
    skills: List[str] = []
    photo_urls: List[str] = []


class PostUpdate(BaseModel):
    text: Optional[str] = None
    skills: Optional[List[str]] = None


class PostRead(PostBase):
    id: int
    author_id: int
    community_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    skills: List[str] = []
    photo_urls: List[str] = []
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False
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

    @field_validator("photo_urls", mode="before")
    @classmethod
    def _coerce_photos_before(cls, v):
        if v is None:
            return []
        try:
            return [p.photo_url for p in v]
        except Exception:
            return v

    @field_serializer("photo_urls", when_used="always")
    def _serialize_photos(self, photo_urls):
        return [p.photo_url if hasattr(p, "photo_url") else p for p in (photo_urls or [])]


class LikeResponse(BaseModel):
    liked: bool
    like_count: int