"""
Community request/response schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class ContentStatus(str):
    """Content moderation status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class VoteType(str):
    """Vote type"""
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


# ── Strategy Sharing ──────────────────────────────────────────────────────────

class CreateStrategyRequest(BaseModel):
    """Create shared strategy request"""
    title: str = Field(..., min_length=3, max_length=200, description="策略標題")
    content: str = Field(..., min_length=10, description="策略內容（Markdown）")
    tags: List[str] = Field(default_factory=list, description="標籤列表")
    decision_ids: Optional[List[int]] = Field(None, description="關聯的決策 ID")
    is_public: bool = Field(default=True, description="是否公開")
    thumbnail_url: Optional[str] = Field(None, description="縮略圖 URL")


class UpdateStrategyRequest(BaseModel):
    """Update shared strategy request"""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    thumbnail_url: Optional[str] = None


class StrategyResponse(BaseModel):
    """Shared strategy response"""
    id: int
    user_id: int
    author_username: str
    author_display_name: Optional[str]
    author_avatar_url: Optional[str]
    title: str
    content: str
    tags: List[str]
    view_count: int
    upvote_count: int
    downvote_count: int
    comment_count: int
    is_public: bool
    status: str
    decision_ids: Optional[List[int]]
    created_at: datetime
    updated_at: datetime
    is_owner: bool = Field(False, description="是否為作者")

    class Config:
        from_attributes = True


class StrategyListResponse(BaseModel):
    """Strategy list response"""
    items: List[StrategyResponse]
    total: int
    page: int
    page_size: int


# ── Discussion ─────────────────────────────────────────────────────────────────

class CreateDiscussionRequest(BaseModel):
    """Create discussion request"""
    title: str = Field(..., min_length=3, max_length=200, description="標題")
    content: str = Field(..., min_length=10, description="內容")
    category: str = Field(..., description="分類: general, question, analysis, feedback")
    tags: List[str] = Field(default_factory=list, description="標籤")
    related_strategy_id: Optional[int] = Field(None, description="關聯策略 ID")


class UpdateDiscussionRequest(BaseModel):
    """Update discussion request"""
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    content: Optional[str] = Field(None, min_length=10)
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class DiscussionResponse(BaseModel):
    """Discussion response"""
    id: int
    user_id: int
    author_username: str
    author_display_name: Optional[str]
    author_avatar_url: Optional[str]
    title: str
    content: str
    category: str
    tags: List[str]
    view_count: int
    reply_count: int
    upvote_count: int
    downvote_count: int
    status: str
    related_strategy_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False

    class Config:
        from_attributes = True


class DiscussionListResponse(BaseModel):
    """Discussion list response"""
    items: List[DiscussionResponse]
    total: int
    page: int
    page_size: int


# ── Comments ───────────────────────────────────────────────────────────────────

class CreateCommentRequest(BaseModel):
    """Create comment request"""
    content: str = Field(..., min_length=1, max_length=5000, description="評論內容")
    parent_id: Optional[int] = Field(None, description="父評論 ID（回覆）")


class UpdateCommentRequest(BaseModel):
    """Update comment request"""
    content: str = Field(..., min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    """Comment response"""
    id: int
    user_id: int
    author_username: str
    author_display_name: Optional[str]
    author_avatar_url: Optional[str]
    content: str
    parent_id: Optional[int]
    target_type: str  # strategy, discussion, comment
    target_id: int
    upvote_count: int
    downvote_count: int
    reply_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """Comment list response"""
    items: List[CommentResponse]
    total: int
    page: int
    page_size: int


# ── Votes ──────────────────────────────────────────────────────────────────────

class VoteRequest(BaseModel):
    """Vote request"""
    vote_type: str = Field(..., description="upvote 或 downvote")


class VoteResponse(BaseModel):
    """Vote response"""
    target_type: str
    target_id: int
    vote_type: str
    total_upvotes: int
    total_downvotes: int


# ── User Interaction ───────────────────────────────────────────────────────────

class FollowUserRequest(BaseModel):
    """Follow user request"""
    target_user_id: int


class FollowResponse(BaseModel):
    """Follow response"""
    is_following: bool
    follower_count: int
    following_count: int


class NotificationSettings(BaseModel):
    """Notification settings"""
    email_on_mention: bool = True
    email_on_reply: bool = True
    email_on_strategy_comment: bool = True
    push_on_mention: bool = True
    push_on_reply: bool = True


class NotificationResponse(BaseModel):
    """Notification response"""
    id: int
    type: str
    title: str
    content: str
    is_read: bool
    data: Optional[Dict[str, Any]]
    created_at: datetime


# ── Content Moderation ────────────────────────────────────────────────────────

class ReportContentRequest(BaseModel):
    """Report content request"""
    target_type: str = Field(..., description="strategy, discussion, comment, user")
    target_id: int = Field(..., description="目標 ID")
    reason: str = Field(..., description="舉報原因")
    details: Optional[str] = Field(None, description="詳細說明")


class ModerateContentRequest(BaseModel):
    """Moderate content request"""
    content_type: str = Field(..., description="strategy, discussion, comment")
    content_id: int
    action: str = Field(..., description="approve, reject, flag")
    reason: Optional[str] = Field(None, description="處理原因")


class ModerationLogResponse(BaseModel):
    """Moderation log response"""
    id: int
    moderator_id: int
    content_type: str
    content_id: int
    action: str
    reason: Optional[str]
    created_at: datetime
