from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class Community(Base):
    __tablename__ = "communities"

    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(255), nullable=True)
    cover_url = Column(String(255), nullable=True)
    is_official = Column(Boolean(), nullable=False, default=False)  # Changed from is_public
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Community owner
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="owned_communities", lazy="selectin")

    # Community members (many-to-many)
    members = relationship(
        "User", secondary="user_communities", back_populates="communities", lazy="selectin"
    )
    
    # Community moderators (many-to-many)
    moderators = relationship(
        "User", secondary="community_moderators", back_populates="moderated_communities", lazy="selectin"
    )
    
    # Community skills
    skills = relationship(
        "Skill", secondary="community_skills", back_populates="communities", lazy="selectin"
    )
    
    # Community posts
    posts = relationship("Post", back_populates="community", lazy="selectin")


class UserCommunity(Base):
    __tablename__ = "user_communities"

    user_id = Column(
        Integer(), ForeignKey("users.id"), primary_key=True, nullable=False
    )
    community_id = Column(
        Integer(), ForeignKey("communities.id"), primary_key=True, nullable=False
    )
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    role = Column(String(20), nullable=False, default="member")  # member, moderator, admin


class CommunityModerator(Base):
    __tablename__ = "community_moderators"

    user_id = Column(
        Integer(), ForeignKey("users.id"), primary_key=True, nullable=False
    )
    community_id = Column(
        Integer(), ForeignKey("communities.id"), primary_key=True, nullable=False
    )
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())


class CommunitySkill(Base):
    __tablename__ = "community_skills"

    community_id = Column(
        Integer(), ForeignKey("communities.id"), primary_key=True, nullable=False
    )
    skill_id = Column(
        Integer(), ForeignKey("skills.id"), primary_key=True, nullable=False
    )