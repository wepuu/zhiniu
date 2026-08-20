from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from zhaoniu_api.config import get_settings
from zhaoniu_api.corporate_events.routes import router as corporate_event_router
from zhaoniu_api.research_feed.routes import router as research_feed_router
from zhaoniu_api.routes import router
from zhaoniu_api.screening.routes import router as screening_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Zhaoniu API",
        version="0.1.0",
        description="Versioned API for an evidence-led A-share research SaaS.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origin_allowlist),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(corporate_event_router)
    app.include_router(research_feed_router)
    app.include_router(screening_router)

    @app.middleware("http")
    async def private_cache_control(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        public_screen_paths = {
            "/api/v1/screens/catalog",
            "/api/v1/screens/coverage",
            "/api/v1/screens/coverage/estimate",
            "/api/v1/screens/validate",
        }
        private_screen = request.url.path.startswith("/api/v1/screens") and (
            request.url.path not in public_screen_paths
        )
        if request.url.path.startswith(("/api/v1/me", "/api/v1/watchlists")) or private_screen:
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Cookie, Origin"
        return response

    return app


app = create_app()
