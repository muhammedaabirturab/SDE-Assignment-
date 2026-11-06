from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.group import GroupCreate, GroupOut, MemberAdd, MemberOut
from app.services import group_service

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post(
    "", response_model=GroupOut, status_code=status.HTTP_201_CREATED, summary="Create a group"
)
def create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    return group_service.create_group(db, payload)


@router.post(
    "/{group_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user to a group",
)
def add_member(group_id: int, payload: MemberAdd, db: Session = Depends(get_db)):
    """404 if the group or user does not exist, 409 if the user is already a member."""
    member = group_service.add_member(db, group_id, payload.user_id, payload.group_id)
    return MemberOut.from_model(member)


@router.get("/{group_id}/members", response_model=list[MemberOut], summary="List group members")
def list_members(group_id: int, db: Session = Depends(get_db)):
    return [MemberOut.from_model(m) for m in group_service.list_members(db, group_id)]
