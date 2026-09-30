from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from pydantic import ValidationError

from .models import CreateIntent, PaymentIntent, ProviderNotification
from .repository import IdempotencyConflict, IntentRepository
from .signature import matches

WEBHOOK_SECRET_ENV = "PROVIDER_WEBHOOK_SECRET"

app = FastAPI(title="Payment intents demo", version="1.0.0")
_repository = IntentRepository()


def repository() -> IntentRepository:
    return _repository


def webhook_secret() -> str:
    return os.environ.get(WEBHOOK_SECRET_ENV, "demo-webhook-secret")


@app.post("/payment-intents", response_model=PaymentIntent)
def create_intent(
    payload: CreateIntent,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    repo: IntentRepository = Depends(repository),
) -> PaymentIntent:
    try:
        intent, created = repo.create(idempotency_key, payload)
    except IdempotencyConflict:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key was already used with a different payload.",
        )

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return intent


@app.get("/payment-intents/{intent_id}", response_model=PaymentIntent)
def get_intent(intent_id: str, repo: IntentRepository = Depends(repository)) -> PaymentIntent:
    intent = repo.get(intent_id)
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found.")
    return intent


@app.post("/webhooks/provider")
async def provider_webhook(
    request: Request,
    x_signature: str = Header(alias="X-Signature", default=""),
    repo: IntentRepository = Depends(repository),
    secret: str = Depends(webhook_secret),
) -> dict[str, str]:
    raw = await request.body()
    if not matches(raw, x_signature, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    try:
        notification = ProviderNotification.model_validate_json(raw)
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.errors())

    outcome = repo.apply_notification(notification)
    if outcome is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intent not found.")

    return {"outcome": outcome.value}
