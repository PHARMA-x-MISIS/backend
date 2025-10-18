from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Comment author
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author = relationship("User", back_populates="comments", lazy="selectin")

    # Post this comment belongs to
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    post = relationship("Post", back_populates="comments", lazy="selectin")

    # Parent comment (for nested comments)
    parent_comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    parent_comment = relationship(
        "Comment", 
        remote_side=[id],
        back_populates="replies",
        lazy="selectin"
    )
    
    # Replies to this comment
    replies = relationship(
        "Comment", 
        back_populates="parent_comment",
        lazy="selectin",
        cascade="all, delete-orphan"
    )