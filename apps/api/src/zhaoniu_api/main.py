import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from zhaoniu_api.access_control.routes import router as access_control_router
from zhaoniu_api.ai_explanations.routes import router as ai_explanation_router
from zhaoniu_api.auth.webhook_routes import router as webhook_router
from zhaoniu_api.automation.routes import router as automation_router
from zhaoniu_api.company_timeline.routes import router as company_timeline_router
from zhaoniu_api.comparisons.routes import router as comparison_router
from zhaoniu_api.config import get_settings
from zhaoniu_api.corporate_events.routes import router as corporate_event_router
from zhaoniu_api.coverage.routes import router as coverage_router
from zhaoniu_api.invite_beta.routes import admin_router as invite_beta_admin_router
from zhaoniu_api.invite_beta.routes import me_router as invite_beta_me_router
from zhaoniu_api.operations_console.routes import router as operations_console_router
from zhaoniu_api.production_release.routes import router as production_release_router
from zhaoniu_api.provider_acceptance.routes import router as provider_acceptance_router
from zhaoniu_api.research_feed.routes import router as research_feed_router
from zhaoniu_api.routes import router
from zhaoniu_api.screening.routes import router as screening_router
from zhaoniu_api.system import router as system_router


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_runtime_security()
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
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.trusted_host_list))
    app.include_router(router)
    app.include_router(corporate_event_router)
    app.include_router(company_timeline_router)
    app.include_router(research_feed_router)
    app.include_router(screening_router)
    app.include_router(comparison_router)
    app.include_router(access_control_router)
    app.include_router(ai_explanation_router)
    app.include_router(coverage_router)
    app.include_router(operations_console_router)
    app.include_router(invite_beta_admin_router)
    app.include_router(invite_beta_me_router)
    app.include_router(provider_acceptance_router)
    app.include_router(production_release_router)
    app.include_router(automation_router)
    app.include_router(webhook_router)
    app.include_router(system_router)

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
        if (
            request.url.path.startswith(
                ("/api/v1/me", "/api/v1/watchlists", "/api/v1/admin", "/api/v1/comparisons")
            )
            or private_screen
        ):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Cookie, Origin"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.middleware("http")
    async def request_observability(request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id", "")[:80] or str(uuid4())
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("zhaoniu.request").info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "route": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                },
                ensure_ascii=False,
            )
        )
        return response

    return app


app = create_app()
