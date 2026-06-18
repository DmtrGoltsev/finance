from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.auth.rate_limits import InMemoryRateLimiter, RateLimitConfig
from app.config import Settings, get_settings
from app.db.session import is_production_like_environment


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
    )

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    _configure_cors(application, app_settings)
    application.state.auth_rate_limiter = InMemoryRateLimiter(RateLimitConfig.default())
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


def _configure_cors(application: FastAPI, settings: Settings) -> None:
    origins = list(settings.cors_allowed_origins)
    if not is_production_like_environment(settings.environment):
        origins.extend(settings.dev_cors_allowed_origins)

    deduped_origins = list(dict.fromkeys(origin for origin in origins if origin))
    if not deduped_origins:
        return

    application.add_middleware(
        CORSMiddleware,
        allow_origins=deduped_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
    )


app = create_app()
