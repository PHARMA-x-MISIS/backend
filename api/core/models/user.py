from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    patronymic = Column(String(50), nullable=True, default="")
    email = Column(String(200), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    contact = Column(String(255), nullable=True)  # New field
    place_of_job = Column(String(255), nullable=True)  # New field
    place_of_study = Column(String(255), nullable=True)  # New field
    profile_photo = Column(String(255), nullable=True)  # New field for profile photo
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # VK OAuth fields
    vk_id = Column(Integer, nullable=True, unique=True)
    vk_avatar = Column(Text, nullable=True)

    # Direct relationships
    skills = relationship(
        "Skill", secondary="user_skills", back_populates="users", lazy="selectin"
    )
    communities = relationship(
        "Community", secondary="user_communities", back_populates="members", lazy="selectin"
    )
    
    # Communities owned by this user
    owned_communities = relationship("Community", back_populates="owner", lazy="selectin")
    
    # Communities where user is moderator
    moderated_communities = relationship(
        "Community", secondary="community_moderators", back_populates="moderators", lazy="selectin"
    )
    
    # Posts created by user
    posts = relationship("Post", back_populates="author", lazy="selectin")
    
    # Comments created by user
    comments = relationship("Comment", back_populates="author", lazy="selectin")
    
    # Likes given by user
    likes = relationship("Like", back_populates="user", lazy="selectin")


class UserSkill(Base):
    __tablename__ = "user_skills"

    user_id = Column(
        Integer(), ForeignKey("users.id"), primary_key=True, nullable=False
    )
    skill_id = Column(
        Integer(), ForeignKey("skills.id"), primary_key=True, nullable=False
    )