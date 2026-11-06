from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.group import Group
from app.models.group_member import GroupMember
from app.schemas.group import GroupCreate
from app.services.user_service import get_user_or_404
from app.utils.db import commit_or_raise


def create_group(db: Session, payload: GroupCreate) -> Group:
    group = Group(name=payload.name)
    db.add(group)
    commit_or_raise(db)
    db.refresh(group)
    return group


def get_group_or_404(db: Session, group_id: int, *, lock: bool = False) -> Group:
    """Fetch a group. ``lock=True`` takes a row lock (``SELECT ... FOR UPDATE``).

    Writers that derive their result from the group's current ledger (new
    expenses and repayments) lock the group first, so two concurrent requests
    for the same group are serialised instead of racing each other.
    """
    statement = select(Group).where(Group.id == group_id)
    if lock:
        statement = statement.with_for_update()
    group = db.scalar(statement)
    if group is None:
        raise NotFoundError(f"Group {group_id} not found")
    return group


def get_member_ids(db: Session, group_id: int) -> set[int]:
    return set(db.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group_id)))


def add_member(db: Session, group_id: int, user_id: int, body_group_id: int | None) -> GroupMember:
    if body_group_id is not None and body_group_id != group_id:
        raise BusinessRuleError("'group_id' in the body does not match the group in the URL")
    get_group_or_404(db, group_id)
    get_user_or_404(db, user_id)
    if user_id in get_member_ids(db, group_id):
        raise ConflictError(f"User {user_id} is already a member of group {group_id}")
    member = GroupMember(group_id=group_id, user_id=user_id)
    db.add(member)
    # The unique (group_id, user_id) constraint also protects against races.
    commit_or_raise(db)
    db.refresh(member)
    return member


def list_members(db: Session, group_id: int) -> list[GroupMember]:
    get_group_or_404(db, group_id)
    statement = (
        select(GroupMember).where(GroupMember.group_id == group_id).order_by(GroupMember.user_id)
    )
    return list(db.scalars(statement))
