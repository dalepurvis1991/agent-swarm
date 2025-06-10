from pydantic import BaseModel, Field, EmailStr


class EmailPayload(BaseModel):
    subject: str = Field(..., min_length=1)
    from_: EmailStr = Field(..., alias="from")
    body: str = Field(..., min_length=1) 