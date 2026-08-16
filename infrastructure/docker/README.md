# Containerization

Phase 0 runs PostgreSQL/pgvector and Redis in Compose while web, API, and worker run locally. Add small production Dockerfiles here only when the deployment target is known; do not bake local secrets into images.
