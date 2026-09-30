# fastapi-payment-intents

A small FastAPI service for payment intents. Written from scratch as a portfolio sample.

- `POST /payment-intents` requires an `Idempotency-Key`. The same key with the same body returns the same intent with `200`. The same key with a different body is a `422`.
- `POST /webhooks/provider` verifies an HMAC-SHA256 signature over the raw body before parsing it.
- A provider event is applied once. A refusal that arrives after an approval does not downgrade the intent.

## Run

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
source .venv/bin/activate   # macOS or Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Test

```bash
pytest -q
```

## Webhook example

```bash
BODY='{"event_id":"evt-1","intent_id":"pi_abc","status":"refused","refusal_code":"card_declined"}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac demo-webhook-secret | cut -d' ' -f2)"
curl -X POST http://127.0.0.1:8000/webhooks/provider -H "X-Signature: $SIG" -H "Content-Type: application/json" -d "$BODY"
```

Set `PROVIDER_WEBHOOK_SECRET` to change the secret.
