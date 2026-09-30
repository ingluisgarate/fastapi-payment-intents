from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IntentStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    refused = "refused"


class CreateIntent(BaseModel):
    reference: str = Field(min_length=1, max_length=64)
    amount_in_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class PaymentIntent(BaseModel):
    id: str
    reference: str
    amount_in_cents: int
    currency: str
    status: IntentStatus
    refusal_code: str | None = None


class ProviderNotification(BaseModel):
    event_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    status: IntentStatus
    refusal_code: str | None = None
