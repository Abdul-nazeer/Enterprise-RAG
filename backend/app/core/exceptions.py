"""
Custom Exceptions with Proper Error Handling

Design Principles:
1. Specific exceptions for each error type
2. HTTP status code mapping
3. User-friendly error messages
4. Detailed logging for debugging
"""
from typing import Any, Optional
from fastapi import HTTPException, status


class BaseAppException(Exception):
    """
    Base exception for all application errors
    
    Why custom exceptions?
    - Consistent error handling across app
    - Easy to catch specific error types
    - Can attach metadata (error codes, details)
    - Translates to appropriate HTTP responses
    """
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException"""
        return HTTPException(
            status_code=self.status_code,
            detail={
                "message": self.message,
                "error_type": self.__class__.__name__,
                **self.details
            }
        )


# ============================================
# Database Exceptions
# ============================================

class DatabaseException(BaseAppException):
    """Base database error"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class DatabaseConnectionError(DatabaseException):
    """Cannot connect to database"""
    def __init__(self, details: Optional[dict] = None):
        super().__init__(
            message="Failed to connect to database. Please try again later.",
            details=details
        )


class RecordNotFoundException(DatabaseException):
    """Record not found in database"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with id '{identifier}' not found",
            details={"resource": resource, "id": identifier}
        )
        self.status_code = status.HTTP_404_NOT_FOUND


class DuplicateRecordException(DatabaseException):
    """Trying to create duplicate record"""
    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            message=f"{resource} with {field}='{value}' already exists",
            details={"resource": resource, "field": field, "value": value}
        )
        self.status_code = status.HTTP_409_CONFLICT


# ============================================
# Session Exceptions
# ============================================

class SessionException(BaseAppException):
    """Base session error"""
    pass


class SessionNotFoundException(SessionException):
    """Session not found"""
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session '{session_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id}
        )


class SessionExpiredException(SessionException):
    """Session has expired"""
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session '{session_id}' has expired. Please create a new session.",
            status_code=status.HTTP_410_GONE,
            details={"session_id": session_id}
        )


class SessionLimitExceededException(SessionException):
    """User has too many active sessions"""
    def __init__(self, user_id: str, max_sessions: int):
        super().__init__(
            message=f"Maximum {max_sessions} active sessions allowed",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"user_id": user_id, "max_sessions": max_sessions}
        )


class SessionStateException(SessionException):
    """Invalid session state transition"""
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ============================================
# Cache Exceptions
# ============================================

class CacheException(BaseAppException):
    """Base cache error (Redis)"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


# ============================================
# Upload Exceptions
# ============================================

class UploadException(BaseAppException):
    """Base upload error"""
    pass


class FileTooLargeException(UploadException):
    """File exceeds size limit"""
    def __init__(self, file_size: int, max_size: int):
        super().__init__(
            message=f"File size {file_size / 1024 / 1024:.1f}MB exceeds limit of {max_size / 1024 / 1024:.0f}MB",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details={"file_size_bytes": file_size, "max_size_bytes": max_size}
        )


class UnsupportedFileTypeException(UploadException):
    """File type not supported"""
    def __init__(self, file_type: str, supported_types: list[str]):
        super().__init__(
            message=f"File type '{file_type}' not supported. Supported: {', '.join(supported_types)}",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            details={"file_type": file_type, "supported_types": supported_types}
        )


class FileProcessingException(UploadException):
    """Error processing uploaded file"""
    def __init__(self, filename: str, error: str):
        super().__init__(
            message=f"Failed to process file '{filename}': {error}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"filename": filename, "error": error}
        )


class MaxFilesExceededException(UploadException):
    """Too many files in session"""
    def __init__(self, current_count: int, max_count: int):
        super().__init__(
            message=f"Session already has {current_count} files. Maximum allowed: {max_count}",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"current_count": current_count, "max_count": max_count}
        )


# ============================================
# Authentication Exceptions
# ============================================

class AuthenticationException(BaseAppException):
    """Base auth error"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )


class InvalidCredentialsException(AuthenticationException):
    """Invalid username or password"""
    def __init__(self):
        super().__init__(message="Invalid email or password")


class TokenExpiredException(AuthenticationException):
    """JWT token expired"""
    def __init__(self):
        super().__init__(message="Token has expired. Please login again.")


class InvalidTokenException(AuthenticationException):
    """Invalid JWT token"""
    def __init__(self):
        super().__init__(message="Invalid authentication token")


# ============================================
# Authorization Exceptions
# ============================================

class AuthorizationException(BaseAppException):
    """Base authorization error"""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details
        )


class InsufficientPermissionsException(AuthorizationException):
    """User lacks required permissions"""
    def __init__(self, required_permission: str):
        super().__init__(
            message=f"Insufficient permissions. Required: {required_permission}",
            details={"required_permission": required_permission}
        )


# ============================================
# Rate Limiting Exceptions
# ============================================

class RateLimitExceededException(BaseAppException):
    """Rate limit exceeded"""
    def __init__(self, limit: int, window: str):
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window}",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"limit": limit, "window": window}
        )


# ============================================
# External Service Exceptions
# ============================================

class ExternalServiceException(BaseAppException):
    """Base external service error"""
    pass


class LLMServiceException(ExternalServiceException):
    """LLM API error"""
    def __init__(self, service: str, error: str):
        super().__init__(
            message=f"LLM service '{service}' error: {error}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"service": service, "error": error}
        )


class VectorDatabaseException(ExternalServiceException):
    """Vector database error"""
    def __init__(self, error: str):
        super().__init__(
            message=f"Vector database error: {error}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"error": error}
        )


class CacheException(ExternalServiceException):
    """Redis cache error"""
    def __init__(self, error: str):
        super().__init__(
            message=f"Cache error: {error}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"error": error}
        )
