"""
@file: app/middleware/auth.py
@description: API认证中间件 - JWT + API Key双重认证
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-04-08
@updated: 2026-04-08
@status: active
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: middleware,auth,security,python,core
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Set

import jwt
from app.config import settings
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthConfig:
    """从全局 settings 动态读取配置，避免硬编码敏感信息"""

    @property
    def AUTH_ENABLED(self) -> bool:
        return settings.auth_enabled

    @property
    def JWT_SECRET_KEY(self) -> str:
        return settings.jwt_secret_key

    @property
    def JWT_ALGORITHM(self) -> str:
        return settings.jwt_algorithm

    @property
    def JWT_EXPIRATION_HOURS(self) -> int:
        return settings.jwt_expiration_hours

    API_KEY_HEADER: str = "X-API-Key"
    AUTHORIZATION_HEADER: str = "Authorization"

    SKIP_AUTH_PATHS: Set[str] = {
        "/v1/ping",
        "/v1/health",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    SKIP_AUTH_PREFIXES: List[str] = [
        "/docs",
        "/openapi",
        "/redoc",
    ]

    @property
    def VALID_API_KEYS(self) -> Set[str]:
        """从 settings.api_keys 动态解析，逗号分隔"""
        return {k.strip() for k in settings.api_keys.split(",") if k.strip()}


auth_config = AuthConfig()
security = HTTPBearer(auto_error=False)


def generate_jwt_token(user_id: str, expires_hours: int = None) -> str:
    """
    生成JWT令牌

    Args:
        user_id: 用户ID
        expires_hours: 过期时间（小时）

    Returns:
        JWT令牌字符串
    """
    expires_hours = expires_hours or auth_config.JWT_EXPIRATION_HOURS
    expiration = datetime.utcnow() + timedelta(hours=expires_hours)

    payload = {
        "user_id": user_id,
        "exp": expiration,
        "iat": datetime.utcnow(),
        "iss": "yyc3-gateway",
    }

    token = jwt.encode(
        payload, auth_config.JWT_SECRET_KEY, algorithm=auth_config.JWT_ALGORITHM
    )

    return token


def verify_jwt_token(token: str) -> Optional[dict]:
    """
    验证JWT令牌

    Args:
        token: JWT令牌字符串

    Returns:
        解码后的payload，验证失败返回None
    """
    try:
        payload = jwt.decode(
            token,
            auth_config.JWT_SECRET_KEY,
            algorithms=[auth_config.JWT_ALGORITHM],
            issuer="yyc3-gateway",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def verify_api_key(api_key: str) -> bool:
    """
    验证API Key

    Args:
        api_key: API Key字符串

    Returns:
        验证结果
    """
    return api_key in auth_config.VALID_API_KEYS


def hash_api_key(api_key: str) -> str:
    """
    哈希API Key（用于存储）

    Args:
        api_key: 原始API Key

    Returns:
        哈希后的API Key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件 - 支持JWT和API Key双重认证

    认证方式：
    1. JWT Token: Authorization: Bearer <token>
    2. API Key: X-API-Key: <api_key>

    优先级：JWT > API Key
    """

    async def dispatch(self, request: Request, call_next):
        if not auth_config.AUTH_ENABLED:
            return await call_next(request)

        path = request.url.path

        if self._should_skip_auth(path):
            return await call_next(request)

        has_credentials, auth_result = await self._authenticate(request)

        if not has_credentials:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "message": "Missing authentication credentials",
                    "detail": "Please provide either a valid JWT token or API key",
                },
            )

        if not auth_result:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Forbidden",
                    "message": "Invalid authentication credentials",
                    "detail": "The provided JWT token or API key is invalid or expired",
                },
            )

        request.state.user = auth_result

        response = await call_next(request)

        return response

    def _should_skip_auth(self, path: str) -> bool:
        """
        判断是否跳过认证

        Args:
            path: 请求路径

        Returns:
            是否跳过认证
        """
        if path in auth_config.SKIP_AUTH_PATHS:
            return True

        for prefix in auth_config.SKIP_AUTH_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    async def _authenticate(self, request: Request) -> tuple[bool, Optional[dict]]:
        """
        执行认证

        Args:
            request: FastAPI请求对象

        Returns:
            (是否有认证信息, 认证结果)
        """
        jwt_token = self._extract_jwt_token(request)
        if jwt_token:
            payload = verify_jwt_token(jwt_token)
            if payload:
                return (
                    True,
                    {
                        "type": "jwt",
                        "user_id": payload.get("user_id"),
                        "exp": payload.get("exp"),
                    },
                )
            else:
                return (True, None)

        api_key = self._extract_api_key(request)
        if api_key:
            if verify_api_key(api_key):
                return (
                    True,
                    {
                        "type": "api_key",
                        "key_hash": hash_api_key(api_key),
                    },
                )
            else:
                return (True, None)

        return (False, None)

    def _extract_jwt_token(self, request: Request) -> Optional[str]:
        """
        从请求中提取JWT令牌

        Args:
            request: FastAPI请求对象

        Returns:
            JWT令牌字符串，未找到返回None
        """
        authorization = request.headers.get(auth_config.AUTHORIZATION_HEADER)

        if not authorization:
            return None

        parts = authorization.split()

        if len(parts) != 2:
            return None

        scheme, token = parts

        if scheme.lower() != "bearer":
            return None

        return token

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        从请求中提取API Key

        Args:
            request: FastAPI请求对象

        Returns:
            API Key字符串，未找到返回None
        """
        return request.headers.get(auth_config.API_KEY_HEADER)


def create_auth_dependency():
    """
    创建FastAPI认证依赖

    用法：
        @app.get("/protected")
        async def protected_route(user: dict = Depends(create_auth_dependency())):
            return {"user": user}
    """

    async def auth_dependency(request: Request):
        if hasattr(request.state, "user"):
            return request.state.user

        if not auth_config.AUTH_ENABLED:
            return {"type": "disabled"}

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    return auth_dependency


auth_required = create_auth_dependency()


__all__ = [
    "AuthMiddleware",
    "AuthConfig",
    "auth_config",
    "generate_jwt_token",
    "verify_jwt_token",
    "verify_api_key",
    "hash_api_key",
    "auth_required",
]
