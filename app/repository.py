from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum

from .models import CreateIntent, IntentStatus, PaymentIntent, ProviderNotification


class NotificationOutcome(str, Enum):
    applied = "applied"
    duplicate = "duplicate"
    kept_approved = "kept_approved"


@dataclass
class IdempotencyConflict(Exception):
    key: str


@dataclass
class IntentRepository:
    intents: dict[str, PaymentIntent] = field(default_factory=dict)
    idempotency: dict[str, tuple[str, str]] = field(default_factory=dict)
    seen_events: set[str] = field(default_factory=set)

    def create(self, key: str, payload: CreateIntent) -> tuple[PaymentIntent, bool]:
        fingerprint = self._fingerprint(payload)
        stored = self.idempotency.get(key)

        if stored is not None:
            stored_fingerprint, intent_id = stored
            if stored_fingerprint != fingerprint:
                raise IdempotencyConflict(key)
            return self.intents[intent_id], False

        intent = PaymentIntent(
            id=f"pi_{uuid.uuid4().hex[:12]}",
            reference=payload.reference,
            amount_in_cents=payload.amount_in_cents,
            currency=payload.currency.upper(),
            status=IntentStatus.pending,
        )
        self.intents[intent.id] = intent
        self.idempotency[key] = (fingerprint, intent.id)
        return intent, True

    def get(self, intent_id: str) -> PaymentIntent | None:
        return self.intents.get(intent_id)

    def apply_notification(self, notification: ProviderNotification) -> NotificationOutcome | None:
        intent = self.intents.get(notification.intent_id)
        if intent is None:
            return None

        if notification.event_id in self.seen_events:
            return NotificationOutcome.duplicate
        self.seen_events.add(notification.event_id)

        if intent.status == IntentStatus.approved and notification.status == IntentStatus.refused:
            return NotificationOutcome.kept_approved

        refusal = notification.refusal_code if notification.status == IntentStatus.refused else None
        self.intents[intent.id] = intent.model_copy(
            update={"status": notification.status, "refusal_code": refusal}
        )
        return NotificationOutcome.applied

    @staticmethod
    def _fingerprint(payload: CreateIntent) -> str:
        raw = f"{payload.reference}|{payload.amount_in_cents}|{payload.currency.upper()}"
        return hashlib.sha256(raw.encode()).hexdigest()
