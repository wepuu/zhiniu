# Privacy baseline

The controlled Beta minimizes stored personal data to account email, password hash, bounded session
metadata, watchlist/workspace data, legal acceptance records and operational audit state. Secrets,
plaintext lifecycle tokens, email bodies and raw natural-language parser text are not retained.

Current controls include purpose-bound access, explicit `user_id` scoping, secure cookie/CSRF
protection, session revocation, structured-log redaction and versioned legal acceptance. Access,
copy, correction and deletion requests are handled manually by authorized operators during the
initial Beta. A self-service personal-information rights center, automated export and deletion
workflow are explicitly deferred and must be designed before broader public availability.
