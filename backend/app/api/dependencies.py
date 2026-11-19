"""
FastAPI Dependencies for Authentication

Design Pattern: Dependency Injection
- Reusable across all protected routes
- Clean separation of concerns
- Easy to test (mock dependencies)

Usage:
```python
@app.get("/protected")
async def protected_route(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {"user": current_user.email}
```
"""
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, verify_token_type
from app.db.base import get_db
from app.models.user import User
from app.services.auth_service import AuthService

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Extract and validate JWT token from Authorization header
    
    Header format: Authorization: Bearer <token>
    
    Raises:
    - HTTPException 401: if token invalid/expired
    """
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        
        # Verify it's an access token
        if not verify_token_type(payload, "access"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Expected access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    payload: dict = Depends(get_token_payload)
) -> UUID:
    """
    Extract user ID from token payload
    
    Raises:
    - HTTPException 401: if user_id not in token
    """
    user_id_str: Optional[str] = payload.get("sub")
    
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract user ID from token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        return UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from database
    
    Dependency chain:
    1. Extract token from header (get_token_payload)
    2. Validate token and get user_id (get_current_user_id)
    3. Load user from database (this function)
    
    Raises:
    - HTTPException 404: if user not found
    - HTTPException 403: if user inactive
    """
    auth_service = AuthService(db)
    
    try:
        user_response = await auth_service.get_user_by_id(user_id)
        
        if user_response is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Load full user model (not just response schema)
        from sqlalchemy import select
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading user: {str(e)}"
        )


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if token provided, None otherwise
    
    Use case: Endpoints that work for both authenticated and anonymous users
    Example: Public content with personalization for logged-in users
    """
    if credentials is None:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        
        if not verify_token_type(payload, "access"):
            return None
        
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        
        user_id = UUID(user_id_str)
        
        auth_service = AuthService(db)
        user_response = await auth_service.get_user_by_id(user_id)
        
        if user_response and user_response.is_active:
            # Load full user model
            from sqlalchemy import select
            query = select(User).where(User.id == user_id)
            result = await db.execute(query)
            return result.scalar_one_or_none()
        
        return None
        
    except Exception:
        # Silently fail for optional authentication
        return None


# ============================================
# Admin/Role-Based Dependencies (Future)
# ============================================

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require admin role
    
    TODO: Add role field to User model
    """
    # TODO: Implement role checking
    # if not current_user.is_admin:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin access required"
    #     )
    return current_user


# ============================================
# Example Usage in Routes
# ============================================

"""
# Protected route (requires authentication)
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email}

# Optional authentication
@router.get("/content")
async def get_content(user: Optional[User] = Depends(get_optional_current_user)):
    if user:
        return {"content": "personalized", "user": user.email}
    return {"content": "public"}

# Admin only
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    # Only admins can delete users
    pass
"""
