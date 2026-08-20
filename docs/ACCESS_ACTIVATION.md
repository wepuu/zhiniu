# Advanced feature activation

Phase 11 provides operator-issued activation codes. It deliberately contains no payment gateway,
order, invoice, checkout, webhook, refund or public pricing capability. Customer-service and legal
processes happen outside the product; the application only validates a supplied code and records
the resulting access grant.

## Operator workflow

Inspect an account and issue a user-bound code:

```text
uv run python -m zhaoniu_api.cli inspect-user-access --user-email user@example.com
uv run python -m zhaoniu_api.cli issue-access-code --user-email user@example.com --term month --expires-in-days 7
```

`--term` accepts `month` or `year`. Validity uses calendar arithmetic with end-of-month clamping,
not a fixed number of seconds. A code is bound to one user, may be redeemed once, and stores only an
HMAC digest plus a non-secret prefix. Concurrent redemption is protected by row locks and a unique
redemption record. Retrying the same successful redemption is idempotent.

The authenticated browser calls `POST /api/v1/me/access/activate` with CSRF and Origin protection.
The response contains the newly resolved access envelope. Public HTTP routes cannot create codes.
The account email must already be verified. This applies to new redemptions and does not invalidate
an access grant issued before Phase 12.

## Production gate

Production startup refuses to enable activation unless all of the following are true:

- `ACCESS_ACTIVATION_ENABLED=true`;
- both HMAC secrets are strong, non-default and distinct;
- secure cookies and explicit allowed origins are configured; and
- `COMMERCIALIZATION_STATUS=approved` records the external legal/commercial approval.

Until that gate is satisfied, operators may validate the feature only in development or controlled
test environments. Logs and error responses must never contain plaintext codes or secrets.
