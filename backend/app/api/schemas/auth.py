"""
Authentication request/response schemas
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request Schemas ──────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="用戶名")
    email: EmailStr = Field(..., description="電子郵箱")
    password: str = Field(..., min_length=8, max_length=100, description="密碼")
    display_name: Optional[str] = Field(None, max_length=100, description="顯示名稱")


class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., description="用戶名或電子郵箱")
    password: str = Field(..., description="密碼")


class RefreshTokenRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="刷新令牌")


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    old_password: str = Field(..., description="舊密碼")
    new_password: str = Field(..., min_length=8, max_length=100, description="新密碼")


class UpdateProfileRequest(BaseModel):
    """Update user profile request"""
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=10)


# ── Response Schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="訪問令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌類型")
    expires_in: int = Field(..., description="過期時間（秒）")


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: int = Field(..., description="用戶 ID")
    exp: datetime = Field(..., description="過期時間")
    type: str = Field(..., description="令牌類型")


class UserResponse(BaseModel):
    """User public profile response"""
    id: int
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    bio: Optional[str]
    is_premium: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """User detailed profile response"""
    email: EmailStr
    timezone: str
    language: str
    is_active: bool
    is_verified: bool
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """Registration success response"""
    user: UserResponse
    message: str = "註冊成功"


class LoginResponse(BaseModel):
    """Login success response"""
    user: UserDetailResponse
    tokens: TokenResponse


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
