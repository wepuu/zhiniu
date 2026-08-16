# API Application Rules

- Routes depend on application ports, not concrete database or market-data implementations.
- Every request and response uses an explicit Pydantic v2 model.
- Enforce `user_id` at every boundary for user-owned resources; never accept identity from a request body.
- Provider output must be normalized before it reaches canonical models or repositories.
- Financial calculations remain deterministic and separately tested.
- Do not call an LLM SDK outside the `LLMGateway` boundary.
- Schema changes require a migration in `infrastructure/migrations`.
- Keep request handlers short; dispatch expensive or retryable work to Celery.
- Run Ruff, MyPy, and Pytest after changes.
