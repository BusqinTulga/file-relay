from pydantic import BaseModel, ConfigDict, Field


class LoginData(BaseModel):
    password: str


class IDData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: int


class IDsData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ids: list[int] = Field(min_length=1, max_length=100)
