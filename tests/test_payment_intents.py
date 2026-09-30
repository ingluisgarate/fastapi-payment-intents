from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app, repository
from app.repository import IntentRepository
from app.signature import sign

SECRET = "demo-webhook-secret"


@pytest.fixture()
def client() -> TestClient:
    fresh = IntentRepository()
    app.dependency_overrides[repository] = lambda: fresh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create(client: TestClient, key: str = "key-0001-abcd", amount: int = 250000):
    return client.post(
        "/payment-intents",
        json={"reference": "order-100", "amount_in_cents": amount, "currency": "usd"},
        headers={"Idempotency-Key": key},
    )


def notify(client: TestClient, body: dict, secret: str = SECRET):
    raw = json.dumps(body).encode()
    return client.post(
        "/webhooks/provider",
        content=raw,
        headers={"X-Signature": sign(raw, secret), "Content-Type": "application/json"},
    )


def test_creates_a_pending_intent_and_normalizes_currency(client: TestClient) -> None:
    response = create(client)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["currency"] == "USD"
    assert body["id"].startswith("pi_")


def test_replays_the_same_idempotency_key_without_creating_a_second_intent(client: TestClient) -> None:
    first = create(client)
    second = create(client)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_rejects_the_same_key_with_a_different_amount(client: TestClient) -> None:
    create(client)
    conflict = create(client, amount=1)

    assert conflict.status_code == 422


def test_rejects_a_webhook_with_a_bad_signature(client: TestClient) -> None:
    intent_id = create(client).json()["id"]

    response = notify(client, {"event_id": "evt-1", "intent_id": intent_id, "status": "approved"}, secret="wrong")

    assert response.status_code == 401
    assert client.get(f"/payment-intents/{intent_id}").json()["status"] == "pending"


def test_records_a_refusal_with_its_code(client: TestClient) -> None:
    intent_id = create(client).json()["id"]

    response = notify(
        client,
        {"event_id": "evt-1", "intent_id": intent_id, "status": "refused", "refusal_code": "card_declined"},
    )

    assert response.json() == {"outcome": "applied"}
    stored = client.get(f"/payment-intents/{intent_id}").json()
    assert stored["status"] == "refused"
    assert stored["refusal_code"] == "card_declined"


def test_does_not_downgrade_an_approved_intent_and_ignores_duplicate_events(client: TestClient) -> None:
    intent_id = create(client).json()["id"]
    approved = {"event_id": "evt-1", "intent_id": intent_id, "status": "approved"}
    refused = {"event_id": "evt-2", "intent_id": intent_id, "status": "refused", "refusal_code": "late"}

    assert notify(client, approved).json() == {"outcome": "applied"}
    assert notify(client, approved).json() == {"outcome": "duplicate"}
    assert notify(client, refused).json() == {"outcome": "kept_approved"}
    assert client.get(f"/payment-intents/{intent_id}").json()["status"] == "approved"
