# =============================================================================
# FGA CRM - Email & EmailTemplate Schemas
# =============================================================================

import re

from pydantic import BaseModel, Field, field_validator

# ---------- Variables de template ----------

TEMPLATE_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

KNOWN_VARIABLES = {
    "first_name", "last_name", "full_name", "email",
    "company_name", "title", "sender_name", "sender_email",
}


# ---------- Email Send ----------


class EmailSendRequest(BaseModel):
    to_email: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)
    contact_id: str | None = Field(None, max_length=36)
    company_id: str | None = Field(None, max_length=36)
    deal_id: str | None = Field(None, max_length=36)
    template_id: str | None = Field(None, max_length=36)

    @field_validator("to_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        from email_validator import EmailNotValidError, validate_email

        try:
            result = validate_email(v, check_deliverability=False)
            return result.normalized
        except EmailNotValidError as e:
            raise ValueError(f"Email invalide: {e}") from e


class EmailSendResponse(BaseModel):
    success: bool
    activity_id: str
    message_id: str | None = None
    sent_at: str


# ---------- Email Templates ----------


class EmailTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1, max_length=50000)


class EmailTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    subject: str | None = Field(None, min_length=1, max_length=500)
    body: str | None = Field(None, min_length=1, max_length=50000)


class EmailTemplateResponse(BaseModel):
    id: str
    name: str
    subject: str
    body: str
    variables: list[str]
    owner_id: str
    created_at: str


class EmailTemplateListResponse(BaseModel):
    items: list[EmailTemplateResponse]
    total: int
    page: int
    size: int
    pages: int
