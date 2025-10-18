from pydantic import BaseModel, ConfigDict


class SkillBase(BaseModel):
    name: str


class SkillCreate(SkillBase):
    pass


class SkillRead(SkillBase):
    id: int
    model_config = ConfigDict(from_attributes=True)