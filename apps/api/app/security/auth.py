"""Bearer-token auth for the API.

The browser never talks to FastAPI directly. The Next.js server (which owns the
Auth.js session cookie) mints a short-lived HS256 token per request:
  iss=aks-web, aud=aks-api, sub=<users.id>, exp<=10 minutes
User sync (sign-in) uses a token with scope=internal instead of a user id.
Admin rights are looked up in the database on every request; tokens carry no roles.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User, utcnow

ISSUER = "aks-web"
AUDIENCE = "aks-api"
MAX_TOKEN_AGE_SECONDS = 600


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    scope: str
    raw: dict[str, Any]


def _secret() -> str:
    secret = get_settings().api_jwt_secret
    if not secret or len(secret) < 16:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API_JWT_SECRET is not configured")
    return secret


def decode_token(token: str) -> TokenClaims:
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub"]},
            leeway=10,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    if int(claims["exp"]) - int(claims["iat"]) > MAX_TOKEN_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token lifetime too long")
    return TokenClaims(sub=str(claims["sub"]), scope=str(claims.get("scope", "user")), raw=claims)


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def _load_user(db: Session, claims: TokenClaims) -> User:
    if claims.scope != "user":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User token required")
    try:
        user_id = uuid.UUID(claims.sub)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid subject") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer(request)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sign in required", headers={"WWW-Authenticate": "Bearer"}
        )
    user = _load_user(db, decode_token(token))
    now = utcnow()
    if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() > 300:
        user.last_seen_at = now
        db.commit()
    request.state.user_id = str(user.id)
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = _bearer(request)
    if not token:
        return None
    try:
        return _load_user(db, decode_token(token))
    except HTTPException:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_internal(request: Request) -> TokenClaims:
    token = _bearer(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Internal token required")
    claims = decode_token(token)
    if claims.scope != "internal":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Internal scope required")
    return claims


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DB = Annotated[Session, Depends(get_db)]
