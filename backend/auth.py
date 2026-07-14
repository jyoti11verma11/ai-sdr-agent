"""JWT + bcrypt authentication utilities + role-based access control."""
import os
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Iterable
from motor.motor_asyncio import AsyncIOMotorDatabase

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "168"))

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try: return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception: return False


def create_access_token(user_id: str, email: str, workspace_id: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email,
        "wid": workspace_id, "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try: return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError: raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError: raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    return {
        "id": payload["sub"],
        "email": payload["email"],
        "workspace_id": payload.get("wid") or payload["sub"],
        "role": payload.get("role") or "admin",
    }


def require_role(*allowed: str):
    """FastAPI dependency factory: enforce that current user has one of allowed roles."""
    async def _dep(current=Depends(get_current_user)) -> dict:
        if current["role"] not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role in {list(allowed)}")
        return current
    return _dep
