"""
Authentication Routes

Endpoints:
- POST /auth/register - Register new user
- POST /auth/login - Login with credentials
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Logout (invalidate token)
- GET /auth/me - Get current user info
- PUT /auth/password - Change password
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.services.auth_service import AuthService, AuthenticationError
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserWithToken,
    TokenResponse,
    TokenRefresh,
    PasswordChange,
)
from app.core.exceptions import DuplicateRecordException

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserWithToken,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email and password"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    
    Requirements:
    - Email must be unique
    - Password must be at least 8 characters
    - Password must contain uppercase, lowercase, number, and special character
    
    Returns:
    - User information
    - Access token (30 min expiration)
    - Refresh token (7 days expiration)
    """
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.register_user(user_data)
        return result
    except DuplicateRecordException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=UserWithToken,
    summary="Login",
    description="Authenticate with email and password"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password
    
    Returns:
    - User information
    - Access token (use for API requests)
    - Refresh token (use to get new access token)
    
    Usage:
    ```
    Authorization: Bearer <access_token>
    ```
    """
    auth_service = AuthService(db)
    
    try:
        result = await auth_service.login(credentials.email, credentials.password)
        return result
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using refresh token"
)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token
    
    When access token expires (30 min), use refresh token to get a new one
    without requiring the user to login again.
    
    Refresh token is long-lived (7 days).
    """
    auth_service = AuthService(db)
    
    try:
        new_tokens = await auth_service.refresh_access_token(token_data.refresh_token)
        return new_tokens
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Invalidate current access token"
)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout current user
    
    TODO: Implement token blacklist with Redis
    - Add current token to blacklist
    - Set TTL = token expiration time
    - Check blacklist in auth middleware
    
    For now, client should discard tokens on logout.
    """
    # TODO: Add token to blacklist in Redis
    # await redis.setex(f"blacklist:{token_hash}", ttl, "1")
    return None


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about currently authenticated user"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    
    Requires authentication (Bearer token in Authorization header)
    """
    return UserResponse.model_validate(current_user)


@router.put(
    "/password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change password for current user"
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password
    
    Requires:
    - Current password (for security)
    - New password (must meet strength requirements)
    
    New password must be different from old password.
    """
    auth_service = AuthService(db)
    
    try:
        success = await auth_service.change_password(
            user_id=current_user.id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )
        
        if success:
            return {"message": "Password changed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )
