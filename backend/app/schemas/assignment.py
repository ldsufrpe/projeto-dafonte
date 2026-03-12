from pydantic import BaseModel


class OperatorOut(BaseModel):
    id: int
    username: str
    full_name: str | None
    is_active: bool
    condominium_ids: list[int]

    model_config = {"from_attributes": True}


class AssignRequest(BaseModel):
    user_id: int | None  # None = remove assignment


class AssignmentOut(BaseModel):
    condominium_id: int
    operator: OperatorOut | None
