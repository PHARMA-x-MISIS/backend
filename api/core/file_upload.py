import os
import uuid
from fastapi import UploadFile, HTTPException
import shutil
from api.core.settings import UPLOAD_DIR, ALLOWED_IMAGE_TYPES, MAX_FILE_SIZE


class FileUploadService:
    def __init__(self):
        self.upload_dir = UPLOAD_DIR
        self.allowed_types = ALLOWED_IMAGE_TYPES
        self.max_size = MAX_FILE_SIZE
        
        # Create upload directory if it doesn't exist
        os.makedirs(self.upload_dir, exist_ok=True)

    async def upload_profile_photo(self, file: UploadFile, user_id: int) -> str:
        """Upload user profile photo"""
        return await self._upload_image(file, "profiles", user_id)

    async def upload_community_avatar(self, file: UploadFile, community_id: int) -> str:
        """Upload community avatar"""
        return await self._upload_image(file, "communities", community_id)

    async def upload_post_photo(self, file: UploadFile, post_id: int) -> str:
        """Upload post photo"""
        return await self._upload_image(file, "posts", post_id)

    async def _upload_image(self, file: UploadFile, category: str, entity_id: int) -> str:
        """Generic image upload method"""
        # Validate file type
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"File type not allowed. Allowed types: {', '.join(self.allowed_types)}"
            )

        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Seek back to start
        
        if file_size > self.max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {self.max_size // (1024 * 1024)}MB"
            )

        # Generate unique filename
        file_extension = file.filename.split('.')[-1]
        filename = f"{category}_{entity_id}_{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(self.upload_dir, category, filename)
        
        # Create category directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Return relative URL for database storage
        return f"/uploads/{category}/{filename}"

    async def delete_file(self, file_url: str) -> bool:
        """Delete uploaded file"""
        try:
            if file_url.startswith('/uploads/'):
                file_path = os.path.join(self.upload_dir, file_url.replace('/uploads/', ''))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
            return False
        except Exception:
            return False


# Global instance
file_upload_service = FileUploadService()