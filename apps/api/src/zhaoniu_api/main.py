from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zhaoniu_api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zhaoniu API",
        version="0.1.0",
        description="Versioned API for an evidence-led A-share research SaaS.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
