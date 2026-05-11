"""Pydantic data schemas for typed validation at module boundaries.

These DTOs enforce type safety when data crosses layers (DB -> service -> UI).
They coexist with the raw-dict approach; adoption is incremental.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

try:
    from pydantic import BaseModel, Field, field_validator
    _HAS_PYDANTIC = True
except ImportError:
    _HAS_PYDANTIC = False

if _HAS_PYDANTIC:

    class UserProfile(BaseModel):
        id: int
        first_name: str
        last_name: str
        email: str
        username: str
        is_verified: bool = False
        is_admin: bool = False
        is_active: bool = True
        created_at: Optional[datetime] = None

    class ChatMessage(BaseModel):
        role: str
        content: str = ""
        extra_data: Optional[dict[str, Any]] = None

    class ContactMessage(BaseModel):
        id: int
        user_id: int
        subject: str
        message: str
        status: str = "pending"
        admin_reply: Optional[str] = None
        created_at: Optional[datetime] = None
        username: str = ""
        first_name: str = ""
        last_name: str = ""
        email: str = ""

    class CustomModel(BaseModel):
        name: str
        base_url: str
        api_key: str
        model_id: str

        @field_validator("base_url")
        @classmethod
        def validate_url(cls, v: str) -> str:
            from src.security.url_validator import validate_url
            result = validate_url(v, context="custom_model_schema")
            if not result.safe:
                raise ValueError(f"URL bloqueada: {result.reason}")
            return v

    class ToolCall(BaseModel):
        action: str
        filename: Optional[str] = None
        content: Optional[str] = None
        code: Optional[str] = None
        query: Optional[str] = None
        message: Optional[str] = None

else:
    UserProfile = dict
    ChatMessage = dict
    ContactMessage = dict
    CustomModel = dict
    ToolCall = dict
