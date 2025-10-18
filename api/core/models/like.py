from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class Like(Base):
    __tablename__ = "likes"

    user_id = Column(
        Integer(), ForeignKey("users.id"), primary_key=True, nullable=False
    )
    post_id = Column(
        Integer(), ForeignKey("posts.id"), primary_key=True, nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="likes", lazy="selectin")
    post = relationship("Post", back_populates="likes", lazy="selectin")