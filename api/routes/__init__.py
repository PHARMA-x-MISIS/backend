from .user import router as user_router
from .community import router as community_router
from .post import router as post_router
from .comment import router as comment_router

__all__ = ["user_router", "community_router", "post_router", "comment_router"]