"""
Security utilities for authentication and authorization

Design Decisions:
1. Bcrypt for password hashing (industry standard, slow by design)
2. JWT tokens with RS256 or HS256 (configurable)
3. Access token (short-lived) + Refresh token (long-lived)
4. Token payload includes: user_id, email, expiration
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Cost factor (2^12 iterations)
)


# ============================================
# Password Hashing
# ============================================

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    
    Why bcrypt?
    - Slow by design (prevents brute force)
    - Automatic salt generation
    - Industry standard
    - Adaptive (cost factor can increase over time)
    
    Time Complexity: O(2^cost) - intentionally slow!
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    
    Returns True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================
# JWT Token Management
# ============================================

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token
    
    Token payload:
    - sub: user_id (subject)
    - email: user email
    - exp: expiration timestamp
    - iat: issued at timestamp
    - type: "access"
    
    Default expiration: 30 minutes
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token
    
    Refresh tokens:
    - Longer expiration (7 days default)
    - Can be used to get new access token
    - Should be stored securely (httpOnly cookie)
    
    Token payload:
    - sub: user_id
    - exp: expiration timestamp
    - iat: issued at timestamp
    - type: "refresh"
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token
    
    Raises:
    - JWTError: if token is invalid/expired
    
    Returns token payload if valid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


def verify_token_type(payload: Dict[str, Any], expected_type: str) -> bool:
    """
    Verify token type (access vs refresh)
    
    Prevents using refresh token as access token and vice versa
    """
    token_type = payload.get("type")
    return token_type == expected_type


# ============================================
# Token Blacklist (for logout)
# ============================================

# TODO: Implement token blacklist with Redis
# When user logs out, add token to blacklist
# Check blacklist before validating token
# TTL = token expiration time

async def is_token_blacklisted(token: str) -> bool:
    """
    Check if token is blacklisted (logged out)
    
    Implementation: Redis SET with TTL
    Key: "blacklist:{token_hash}"
    TTL: token expiration time
    """
    # TODO: Implement with Redis
    return False


async def blacklist_token(token: str, exp: datetime) -> None:
    """
    Add token to blacklist (on logout)
    
    TTL = time until token expires
    After expiration, token is invalid anyway, so can be removed
    """
    # TODO: Implement with Redis
    pass


# ============================================
# Password Validation
# ============================================

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    
    Requirements:
    - At least 8 characters
    - Contains uppercase letter
    - Contains lowercase letter
    - Contains number
    - Contains special character
    
    Returns: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, ""


# ============================================
# Example Usage
# ============================================

"""
# Register user
hashed_pw = hash_password("SecurePassword123!")

# Login
if verify_password("SecurePassword123!", hashed_pw):
    access_token = create_access_token({"sub": str(user_id), "email": user.email})
    refresh_token = create_refresh_token({"sub": str(user_id)})
    
# Protected route
payload = decode_token(access_token)
if verify_token_type(payload, "access"):
    user_id = payload["sub"]
    
# Refresh access token
refresh_payload = decode_token(refresh_token)
if verify_token_type(refresh_payload, "refresh"):
    new_access_token = create_access_token({"sub": refresh_payload["sub"]})
"""
