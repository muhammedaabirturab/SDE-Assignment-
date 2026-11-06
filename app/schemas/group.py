from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.group_member import GroupMember
from app.schemas.common import Name


class GroupCreate(BaseModel):
    name: Name = Field(examples=["Goa Trip"])


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class MemberAdd(BaseModel):
    user_id: int = Field(gt=0, examples=[2])
    group_id: int | None = Field(
        default=None,
        gt=0,
        description="Optional; must match the group in the URL if supplied.",
    )


class MemberOut(BaseModel):
    group_id: int
    user_id: int
    name: str
    joined_at: datetime

    @classmethod
    def from_model(cls, member: GroupMember) -> "MemberOut":
        return cls(
            group_id=member.group_id,
            user_id=member.user_id,
            name=member.user.name,
            joined_at=member.joined_at,
        )
