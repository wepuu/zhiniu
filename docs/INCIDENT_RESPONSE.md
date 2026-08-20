# Incident response

1. Record start time, environment, request IDs and affected capability; do not paste secrets or
   customer data into tickets.
2. Stop the unsafe capability first: disable activation, LLM generation or registration as scoped;
   avoid taking the whole research API offline when isolation is possible.
3. Inspect `/readyz`, structured API logs, Celery state and the relevant queryable run records.
4. Preserve evidence. Do not mutate immutable research outputs or provider-payload lineage.
5. Recover PostgreSQL only from a checksum-verified backup into an isolated database first.
6. Document cause, user impact, recovery, data corrections and preventative tests before closure.

Credential or token exposure requires rotation and session revocation. A suspected financial-data
lineage error requires suspending affected research presentation until deterministic artifacts are
rebuilt and verified.
