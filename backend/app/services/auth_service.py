"""
Authentication Service

Responsibilities:
1. User registration
2. User login (email + password)
3. Token generation (access + refresh)
4. Token refresh
5. Password management

Design Decision: Service Layer Pattern
- Separates business logic from HTTP handlers
- Reusable across different interfaces
- Easier to test
"""
from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.core.config import get_settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token_type,
)
from app.core.exceptions import (
    DatabaseException,
    DuplicateRecordException,
    RecordNotFoundException,
)
from app.core.retry import with_db_retry
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    TokenResponse,
    UserWithToken,
)

settings = get_settings()


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass


class AuthService:
    """
    Authentication Service
    
    Handles user registration, login, and token management
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ========== REGISTRATION ==========
    
    @with_db_retry()
    async def register_user(self, user_data: UserCreate) -> UserWithToken:
        """
        Register a new user
        
        Algorithm:
        1. Check if email already exists
        2. Hash password with bcrypt
        3. Create user record
        4. Generate tokens
        5. Return user + tokens
        
        Raises:
        - DuplicateRecordException: if email exists
        - DatabaseException: on database error
        """
        try:
            # Check if email exists
            existing_user = await self._get_user_by_email(user_data.email)
            if existing_user:
                raise DuplicateRecordException(
                    resource="User",
                    field="email",
                    value=user_data.email
                )
            
            # Hash password
            hashed_password = hash_password(user_data.password)
            
            # Create user
            user = User(
                id=uuid4(),
                email=user_data.email,
                hashed_password=hashed_password,
                full_name=user_data.full_name,
                is_active=True,
            )
            
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            
            # Generate tokens
            tokens = self._generate_tokens(user)
            
            return UserWithToken(
                user=UserResponse.model_validate(user),
                tokens=tokens
            )
            
        except DuplicateRecordException:
            raise
        except Exception as e:
            await self.db.rollback()
            raise DatabaseException(f"Failed to register user: {str(e)}") from e
    
    # ========== LOGIN ==========
    
    @with_db_retry()
    async def login(self, email: str, password: str) -> UserWithToken:
        """
        Authenticate user and generate tokens
        
        Algorithm:
        1. Find user by email
        2. Verify password
        3. Check if account is active
        4. Generate tokens
        5. Return user + tokens
        
        Raises:
        - AuthenticationError: if credentials invalid or account inactive
        """
        try:
            # Find user
            user = await self._get_user_by_email(email)
            if not user:
                raise AuthenticationError("Invalid email or password")
            
            # Verify password
            if not verify_password(password, user.hashed_password):
                raise AuthenticationError("Invalid email or password")
            
            # Check if active
            if not user.is_active:
                raise AuthenticationError("Account is inactive. Please contact support.")
            
            # Generate tokens
            tokens = self._generate_tokens(user)
            
            return UserWithToken(
                user=UserResponse.model_validate(user),
                tokens=tokens
            )
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise DatabaseException(f"Login failed: {str(e)}") from e
    
    # ========== TOKEN REFRESH ==========
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Generate new access token from refresh token
        
        Algorithm:
        1. Decode refresh token
        2. Verify it's a refresh token (not access)
        3. Check if user still exists and active
        4. Generate new access token
        
        Raises:
        - AuthenticationError: if token invalid or user inactive
        """
        try:
            # Decode token
            payload = decode_token(refresh_token)
            
            # Verify token type
            if not verify_token_type(payload, "refresh"):
                raise AuthenticationError("Invalid token type")
            
            # Get user ID from token
            user_id_str = payload.get("sub")
            if not user_id_str:
                raise AuthenticationError("Invalid token payload")
            
            user_id = UUID(user_id_str)
            
            # Get user from database
            user = await self._get_user_by_id(user_id)
            if not user:
                raise AuthenticationError("User not found")
            
            if not user.is_active:
                raise AuthenticationError("Account is inactive")
            
            # Generate new access token only
            access_token = create_access_token(
                data={"sub": str(user.id), "email": user.email}
            )
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,  # Keep same refresh token
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            )
            
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}") from e
        except AuthenticationError:
            raise
        except Exception as e:
            raise DatabaseException(f"Token refresh failed: {str(e)}") from e
    
    # ========== PASSWORD MANAGEMENT ==========
    
    @with_db_retry()
    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password
        
        Requires old password for security (prevents session hijacking)
        
        Returns True on success
        Raises AuthenticationError if old password incorrect
        """
        try:
            user = await self._get_user_by_id(user_id)
            if not user:
                raise RecordNotFoundException("User", str(user_id))
            
            # Verify old password
            if not verify_password(old_password, user.hashed_password):
                raise AuthenticationError("Current password is incorrect")
            
            # Hash new password
            user.hashed_password = hash_password(new_password)
            
            await self.db.commit()
            return True
            
        except AuthenticationError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise DatabaseException(f"Password change failed: {str(e)}") from e
    
    # ========== USER MANAGEMENT ==========
    
    @with_db_retry()
    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        """Get user by ID"""
        user = await self._get_user_by_id(user_id)
        if user:
            return UserResponse.model_validate(user)
        return None
    
    @with_db_retry()
    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Get user by email"""
        user = await self._get_user_by_email(email)
        if user:
            return UserResponse.model_validate(user)
        return None
    
    @with_db_retry()
    async def deactivate_user(self, user_id: UUID) -> bool:
        """
        Deactivate user account (soft delete)
        
        Design Decision: Soft delete instead of hard delete
        - Preserve data for audit
        - Can reactivate later
        - Prevents login but keeps history
        """
        try:
            user = await self._get_user_by_id(user_id)
            if not user:
                raise RecordNotFoundException("User", str(user_id))
            
            user.is_active = False
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            raise DatabaseException(f"Failed to deactivate user: {str(e)}") from e
    
    # ========== INTERNAL HELPERS ==========
    
    async def _get_user_by_email(self, email: str) -> Optional[User]:
        """Get user from database by email"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user from database by ID"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    def _generate_tokens(self, user: User) -> TokenResponse:
        """Generate access and refresh tokens for user"""
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
