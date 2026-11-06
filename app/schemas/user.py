from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Name


class UserCreate(BaseModel):
    name: Name = Field(examples=["Mohit"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
