from typing import Any

from pydantic import BaseModel


class ResumeCreate(BaseModel):
    parsed_data: dict[str, Any]


class ResumeUpdate(BaseModel):
    parsed_data: dict[str, Any]


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    parsed_data: dict[str, Any]

    class Config:
        from_attributes = True
