"""
User Schemas for API Request/Response

Design Decision: Separate schemas for different contexts:
- UserCreate: Registration (includes password)
- UserLogin: Authentication (email + password)
- UserResponse: Public user info (no password!)
- UserUpdate: Profile updates
- TokenResponse: JWT tokens
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator

from app.core.security import validate_password_strength


class UserCreate(BaseModel):
    """
    Schema for user registration
    
    Design: Minimal required fields
    - Email must be valid (EmailStr validation)
    - Password must be strong (custom validator)
    - Full name optional but recommended
    """
    email: EmailStr = Field(
        ...,
        description="User email address (unique)",
        example="user@example.com"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User password (min 8 chars)",
        example="SecurePassword123!"
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="User's full name",
        example="John Doe"
    )
    
    @validator("password")
    def validate_password(cls, v):
        """Validate password strength"""
        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123!",
                "full_name": "John Doe"
            }
        }


class UserLogin(BaseModel):
    """
    Schema for user login
    
    Simple: email + password
    """
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123!"
            }
        }


class UserResponse(BaseModel):
    """
    Schema for user information in responses
    
    Design Decision: Never expose password or sensitive data
    - id: UUID for security (harder to enumerate)
    - email: for display
    - full_name: optional
    - is_active: account status
    - created_at: registration date
    """
    id: UUID = Field(description="User unique identifier")
    email: EmailStr = Field(description="User email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(description="Account active status")
    created_at: datetime = Field(description="Account creation timestamp")
    
    class Config:
        from_attributes = True  # Allow ORM model conversion
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class UserUpdate(BaseModel):
    """
    Schema for updating user profile
    
    All fields optional (PATCH semantics)
    """
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated full name"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Updated email (must be unique)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Updated Doe",
                "email": "john.updated@example.com"
            }
        }


class PasswordChange(BaseModel):
    """
    Schema for password change
    
    Requires old password for security (prevents session hijacking)
    """
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password"
    )
    
    @validator("new_password")
    def validate_new_password(cls, v, values):
        """Validate new password strength and ensure it's different"""
        # Check strength
        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Ensure different from old password
        if "old_password" in values and v == values["old_password"]:
            raise ValueError("New password must be different from old password")
        
        return v


class TokenResponse(BaseModel):
    """
    Schema for authentication tokens
    
    Design: Standard OAuth2 response format
    - access_token: Short-lived JWT (30 min)
    - refresh_token: Long-lived JWT (7 days)
    - token_type: Always "bearer"
    - expires_in: Seconds until access token expires
    """
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Seconds until access token expires")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }


class TokenRefresh(BaseModel):
    """
    Schema for token refresh request
    """
    refresh_token: str = Field(..., description="Refresh token to exchange")


class UserWithToken(BaseModel):
    """
    Schema combining user info with tokens (for registration/login response)
    """
    user: UserResponse = Field(description="User information")
    tokens: TokenResponse = Field(description="Authentication tokens")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                    "is_active": True,
                    "created_at": "2024-01-15T10:30:00Z"
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800
                }
            }
        }
