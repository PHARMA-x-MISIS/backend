from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class Post(Base):
    __tablename__ = "posts"

    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Post author (can be user or community)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author = relationship("User", back_populates="posts", lazy="selectin")

    # Community (if this is a community post)
    community_id = Column(Integer, ForeignKey("communities.id"), nullable=True)
    community = relationship("Community", back_populates="posts", lazy="selectin")

    # Post skills
    skills = relationship(
        "Skill", secondary="post_skills", back_populates="posts", lazy="selectin"
    )

    # Post photos
    photos = relationship("PostPhoto", back_populates="post", lazy="selectin", cascade="all, delete-orphan")

    # Post likes
    likes = relationship("Like", back_populates="post", lazy="selectin", cascade="all, delete-orphan")
    
    # Post comments
    comments = relationship("Comment", back_populates="post", lazy="selectin", cascade="all, delete-orphan")


class PostPhoto(Base):
    __tablename__ = "post_photos"

    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    photo_url = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    post = relationship("Post", back_populates="photos", lazy="selectin")


class PostSkill(Base):
    __tablename__ = "post_skills"

    post_id = Column(
        Integer(), ForeignKey("posts.id"), primary_key=True, nullable=False
    )
    skill_id = Column(
        Integer(), ForeignKey("skills.id"), primary_key=True, nullable=False
    )