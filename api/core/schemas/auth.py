from pydantic import BaseModel, EmailStr
from typing import Optional


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserChangePassword(BaseModel):
    current_password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None


class VKUserInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    photo_200: Optional[str] = None


class VKAuthRequest(BaseModel):
    code: str


class VKAuthResponse(BaseModel):
    access_token: str
    token_type: str
    is_new_user: bool