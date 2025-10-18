from pydantic import BaseModel, ConfigDict, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime


class CommentBase(BaseModel):
    text: str


class CommentCreate(CommentBase):
    post_id: int
    parent_comment_id: Optional[int] = None

    @field_validator("parent_comment_id", mode="before")
    @classmethod
    def _normalize_parent_id(cls, v):
        if v in (0, "0", "", None):
            return None
        return v


class CommentUpdate(BaseModel):
    text: Optional[str] = None


class CommentRead(CommentBase):
    id: int
    author_id: int
    post_id: int
    parent_comment_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List['CommentRead'] = []
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("replies", when_used="always")
    def _serialize_replies(self, replies):
        if not replies:
            return []
        # Serialize only one nesting level to avoid lazy-loading deeper trees
        serialized = []
        for r in replies:
            if isinstance(r, dict):
                item = dict(r)
                item["replies"] = []
                serialized.append(item)
            else:
                serialized.append({
                    "id": getattr(r, "id"),
                    "author_id": getattr(r, "author_id"),
                    "post_id": getattr(r, "post_id"),
                    "parent_comment_id": getattr(r, "parent_comment_id"),
                    "text": getattr(r, "text"),
                    "created_at": getattr(r, "created_at"),
                    "updated_at": getattr(r, "updated_at"),
                    "replies": []
                })
        return serialized

    @field_validator("replies", mode="before")
    @classmethod
    def _coerce_replies_before(cls, v):
        if v is None:
            return []
        # Flatten to one level early to avoid triggering lazy loads
        flat = []
        try:
            for r in v:
                if isinstance(r, dict):
                    item = dict(r)
                    item["replies"] = []
                    flat.append(item)
                else:
                    flat.append({
                        "id": getattr(r, "id"),
                        "author_id": getattr(r, "author_id"),
                        "post_id": getattr(r, "post_id"),
                        "parent_comment_id": getattr(r, "parent_comment_id"),
                        "text": getattr(r, "text"),
                        "created_at": getattr(r, "created_at"),
                        "updated_at": getattr(r, "updated_at"),
                        "replies": []
                    })
        except Exception:
            return v
        return flat


# For recursive models
CommentRead.update_forward_refs()