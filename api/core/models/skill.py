from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .base import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(
        Integer(), primary_key=True, index=True, nullable=False, autoincrement=True
    )
    name = Column(String(100), nullable=False, unique=True)

    # Relationships
    users = relationship(
        "User", secondary="user_skills", back_populates="skills", lazy="selectin"
    )
    
    communities = relationship(
        "Community", secondary="community_skills", back_populates="skills", lazy="selectin"
    )
    
    posts = relationship(
        "Post", secondary="post_skills", back_populates="skills", lazy="selectin"
    )