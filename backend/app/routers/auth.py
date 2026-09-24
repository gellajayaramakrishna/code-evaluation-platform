from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.limiter import limiter
from app.models import User
from app.schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token)
@limiter.limit("10/minute")
def register(request: Request, body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == body.username) | (User.email == body.email)).first():
        raise HTTPException(400, "Username or email already taken")
    user = User(
        username=body.username.strip(),
        email=body.email.strip().lower(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.username, {"admin": user.is_admin})
    return Token(access_token=token, username=user.username, is_admin=user.is_admin)


@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")
    token = create_access_token(user.username, {"admin": user.is_admin})
    return Token(access_token=token, username=user.username, is_admin=user.is_admin)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
