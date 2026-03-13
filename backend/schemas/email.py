from pydantic import BaseModel, Field


class EmailRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)


class EmailVerifyRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    code: str = Field(..., min_length=6, max_length=6)
