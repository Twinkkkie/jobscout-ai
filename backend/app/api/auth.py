from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models import CandidateProfile, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    email = payload.email.strip().lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        locale=payload.locale,
    )
    db.add(user)
    await db.flush()
    db.add(CandidateProfile(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id))
