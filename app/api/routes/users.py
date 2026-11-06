from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.user import UserCreate, UserOut
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Create a user"
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a user. Names are unique (case-insensitive) and 1-100 characters."""
    return user_service.create_user(db, payload)


@router.get("", response_model=list[UserOut], summary="List all users")
def list_users(db: Session = Depends(get_db)):
    """Return every registered user (an empty list when there are none)."""
    return user_service.list_users(db)
