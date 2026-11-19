"""
Session Management Routes

Endpoints:
- POST /sessions - Create new session
- GET /sessions - List user's sessions
- GET /sessions/{session_id} - Get session details
- PUT /sessions/{session_id} - Update session state
- DELETE /sessions/{session_id} - Delete session
- POST /sessions/{session_id}/extend - Extend session TTL
- GET /sessions/stats - Get session statistics
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api.dependencies import get_current_user
from app.db.base import get_db
from app.db.redis import get_redis
from app.models.user import User
from app.models.session import SessionState
from app.services.session_service import SessionService
from app.schemas.session import (
    SessionCreate,
    SessionResponse,
    SessionUpdate,
    SessionStats,
)
from app.core.exceptions import (
    SessionNotFoundException,
    SessionExpiredException,
    SessionStateException,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new session",
    description="Create a new RAG session for document uploads and queries"
)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Create a new session
    
    Each session:
    - Has its own Qdrant collection (session_id = collection name)
    - Isolated document storage
    - Isolated query context
    - Auto-expires after 24 hours of inactivity
    
    Returns session ID and expiration info.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        session = await service.create_session(user_id=current_user.id)
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List user sessions",
    description="Get all sessions for current user with optional filtering"
)
async def list_sessions(
    state: Optional[SessionState] = Query(None, description="Filter by state"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    List user's sessions
    
    Supports:
    - Pagination (page, page_size)
    - Filtering by state (ACTIVE, INACTIVE, EXPIRED)
    - Ordered by most recent activity
    
    Returns list of sessions with metadata.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        sessions, total = await service.list_user_sessions(
            user_id=current_user.id,
            state=state,
            page=page,
            page_size=page_size
        )
        
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session details",
    description="Get detailed information about a specific session"
)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get session by ID
    
    Returns:
    - Session metadata
    - Document count
    - Query count
    - State and expiration info
    
    Checks cache first (Redis), then database if needed.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        session = await service.get_session(session_id)
        
        # Verify session belongs to current user
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        return session
    except SessionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except SessionExpiredException as e:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


@router.put(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update session",
    description="Update session state (ACTIVE ↔ INACTIVE)"
)
async def update_session(
    session_id: UUID,
    update_data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Update session state
    
    Allowed transitions:
    - ACTIVE → INACTIVE (user closes session)
    - INACTIVE → ACTIVE (user reopens session)
    
    Forbidden transitions:
    - → EXPIRED (system only)
    - → DELETED (use DELETE endpoint)
    - FROM DELETED (terminal state)
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        # Verify ownership
        session = await service.get_session(session_id)
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        # Update state
        if update_data.state:
            updated_session = await service.update_session_state(
                session_id=session_id,
                new_state=update_data.state
            )
            return updated_session
        else:
            return session
            
    except SessionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except SessionStateException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete session",
    description="Soft delete session (mark as DELETED)"
)
async def delete_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Delete session (soft delete)
    
    - Marks session as DELETED
    - Qdrant collection cleanup (future: async job)
    - Document files cleanup (future: async job)
    - Removes from cache
    
    Soft delete preserves audit trail.
    Hard delete happens later via cleanup job.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        # Verify ownership
        session = await service.get_session(session_id)
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        await service.delete_session(session_id)
        return None
        
    except SessionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.post(
    "/{session_id}/extend",
    response_model=SessionResponse,
    summary="Extend session TTL",
    description="Reset session expiration (extend by 24 hours)"
)
async def extend_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Extend session TTL
    
    Resets expiration to NOW + 24 hours.
    Use when user wants to keep session alive.
    
    Only works for ACTIVE sessions.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        # Verify ownership
        session = await service.get_session(session_id)
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this session"
            )
        
        extended_session = await service.extend_session(session_id)
        return extended_session
        
    except SessionNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except SessionStateException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend session: {str(e)}"
        )


@router.get(
    "/stats/overview",
    response_model=SessionStats,
    summary="Get session statistics",
    description="Get aggregated statistics for user's sessions"
)
async def get_session_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get session statistics
    
    Returns:
    - Total sessions created
    - Active/Inactive/Expired counts
    - Total documents uploaded
    - Total queries made
    - Averages per session
    
    Useful for dashboard/analytics.
    """
    service = SessionService(db=db, redis=redis)
    
    try:
        stats = await service.get_session_stats(user_id=current_user.id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
