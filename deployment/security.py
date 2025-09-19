"""Security utilities for MinIO MCP Server."""

import hashlib
import hmac
import secrets
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration."""
    
    def __init__(self):
        self.api_key_header = "X-API-Key"
        self.rate_limit_header = "X-RateLimit-Remaining"
        self.max_requests_per_minute = 60
        self.max_requests_per_hour = 1000
        self.token_expire_minutes = 60
        self.refresh_token_expire_days = 7


class APIKeyManager:
    """Manage API keys for authentication."""
    
    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
    
    def generate_api_key(self, user_id: str, permissions: List[str] = None) -> str:
        """Generate a new API key."""
        api_key = secrets.token_urlsafe(32)
        
        self.api_keys[api_key] = {
            "user_id": user_id,
            "permissions": permissions or [],
            "created_at": datetime.utcnow(),
            "last_used": None,
            "usage_count": 0
        }
        
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """Validate API key and return user info."""
        if api_key in self.api_keys:
            key_info = self.api_keys[api_key]
            key_info["last_used"] = datetime.utcnow()
            key_info["usage_count"] += 1
            return key_info
        return None
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        if api_key in self.api_keys:
            del self.api_keys[api_key]
            return True
        return False


class RateLimiter:
    """Rate limiting implementation."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check if request is allowed and return remaining requests."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Initialize if not exists
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > hour_ago
        ]
        
        # Count requests in last minute and hour
        minute_requests = len([
            req_time for req_time in self.requests[client_id]
            if req_time > minute_ago
        ])
        
        hour_requests = len(self.requests[client_id])
        
        # Check limits
        if minute_requests >= self.config.max_requests_per_minute:
            return False, 0
        
        if hour_requests >= self.config.max_requests_per_hour:
            return False, 0
        
        # Add current request
        self.requests[client_id].append(now)
        
        # Calculate remaining requests
        remaining = min(
            self.config.max_requests_per_minute - minute_requests - 1,
            self.config.max_requests_per_hour - hour_requests - 1
        )
        
        return True, remaining


class SecurityManager:
    """Central security manager."""
    
    def __init__(self):
        self.config = SecurityConfig()
        self.api_key_manager = APIKeyManager()
        self.rate_limiter = RateLimiter(self.config)
        self.security = HTTPBearer(auto_error=False)
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use API key if present, otherwise use IP
        api_key = request.headers.get(self.config.api_key_header)
        if api_key:
            return f"api_key:{api_key}"
        
        # Get real IP from headers (considering reverse proxy)
        real_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
            request.headers.get("X-Real-IP") or
            request.client.host
        )
        
        return f"ip:{real_ip}"
    
    async def authenticate_request(
        self, 
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
    ) -> Dict:
        """Authenticate incoming request."""
        
        # Check rate limiting first
        client_id = self.get_client_id(request)
        allowed, remaining = self.rate_limiter.is_allowed(client_id)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"}
            )
        
        # Check API key authentication
        api_key = request.headers.get(self.config.api_key_header)
        if api_key:
            key_info = self.api_key_manager.validate_api_key(api_key)
            if not key_info:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )
            
            return {
                "auth_type": "api_key",
                "user_id": key_info["user_id"],
                "permissions": key_info["permissions"],
                "remaining_requests": remaining
            }
        
        # Check JWT token authentication
        if credentials and credentials.credentials:
            try:
                # This would integrate with your existing JWT validation
                # For now, just return basic info
                return {
                    "auth_type": "jwt",
                    "user_id": "jwt_user",
                    "permissions": [],
                    "remaining_requests": remaining
                }
            except jwt.InvalidTokenError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token"
                )
        
        # Allow unauthenticated requests with rate limiting
        return {
            "auth_type": "anonymous",
            "user_id": f"anonymous_{client_id}",
            "permissions": ["read"],
            "remaining_requests": remaining
        }
    
    def require_permissions(self, required_permissions: List[str]):
        """Decorator to require specific permissions."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get auth info from request context
                auth_info = kwargs.get('auth_info', {})
                user_permissions = auth_info.get('permissions', [])
                
                # Check if user has required permissions
                if not any(perm in user_permissions for perm in required_permissions):
                    if 'admin' not in user_permissions:  # Admin bypass
                        raise HTTPException(
                            status_code=403,
                            detail=f"Insufficient permissions. Required: {required_permissions}"
                        )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token."""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Hash password with salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with SHA-256
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return key.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password against hash."""
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return hmac.compare_digest(key.hex(), hashed)


def create_signed_url(url: str, secret_key: str, expires_in: int = 3600) -> str:
    """Create a signed URL that expires."""
    expiry = int(time.time()) + expires_in
    
    # Create signature
    message = f"{url}:{expiry}"
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Add signature and expiry to URL
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}signature={signature}&expires={expiry}"


def verify_signed_url(signed_url: str, secret_key: str) -> bool:
    """Verify a signed URL."""
    try:
        # Extract signature and expiry
        if "signature=" not in signed_url or "expires=" not in signed_url:
            return False
        
        parts = signed_url.split("signature=")
        url_part = parts[0].rstrip("&")
        sig_and_exp = parts[1]
        
        if "&expires=" in sig_and_exp:
            signature, expiry_str = sig_and_exp.split("&expires=")
        else:
            return False
        
        expiry = int(expiry_str)
        
        # Check if expired
        if time.time() > expiry:
            return False
        
        # Verify signature
        message = f"{url_part}:{expiry}"
        expected_signature = hmac.new(
            secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    except (ValueError, IndexError):
        return False


# Global security manager instance
security_manager = SecurityManager()
