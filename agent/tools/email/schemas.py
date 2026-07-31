"""Validated inputs for email tool actions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class GetUnreadParameters(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)


class MessageIdParameters(BaseModel):
    message_id: str = Field(min_length=1, max_length=1024)


class SearchParameters(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=25)


class SendEmailParameters(BaseModel):
    to: list[str] = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=200_000)
    content_type: Literal["Text", "HTML"] = "Text"
    save_to_sent_items: bool = True

    @field_validator("to")
    @classmethod
    def validate_recipients(cls, recipients: list[str]) -> list[str]:
        cleaned = [recipient.strip() for recipient in recipients]
        if any("@" not in recipient or " " in recipient for recipient in cleaned):
            raise ValueError("Each recipient must be a valid email address.")
        return cleaned


class ReplyEmailParameters(BaseModel):
    message_id: str = Field(min_length=1, max_length=1024)
    comment: str = Field(min_length=1, max_length=200_000)


class DownloadAttachmentParameters(BaseModel):
    message_id: str = Field(min_length=1, max_length=1024)
    attachment_id: str = Field(min_length=1, max_length=1024)

