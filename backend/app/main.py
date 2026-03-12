import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
import structlog

from app.core.logger import setup_logging
setup_logging()

from app.api.assignments import router as assignments_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.dashboard import router as dashboard_router
from app.api.erp import router as erp_router
from app.api.evidence import router as evidence_router
from app.api.finance import router as finance_router
from app.api.history import router as history_router
from app.api.home import router as home_router
from app.api.onboarding import router as onboarding_router
from app.api.health import router as health_router
from app.api.product import router as product_router
from app.api.stock import router as stock_router

from app.core.config import settings

logger = structlog.get_logger("fontegest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    from app.core.database import AsyncSessionLocal
    from app.core.scheduler import start_scheduler, stop_scheduler
    from app.core.seed import run_seed

    async with AsyncSessionLocal() as session:
        await run_seed(session)

    start_scheduler()
    logger.info("🚀 FonteGest API ready (ERP_MODE=%s)", settings.ERP_MODE)

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(title="FonteGest API", version="0.1.0", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", method=request.method, url=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"type": "about:blank", "title": "Internal Server Error", "status": 500, "detail": "An unexpected error occurred."}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"type": "about:blank", "title": "HTTP Error", "status": exc.status_code, "detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"type": "about:blank", "title": "Validation Error", "status": 422, "detail": exc.errors()}
    )

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(assignments_router, prefix="/api")
app.include_router(erp_router, prefix="/api")
app.include_router(home_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(stock_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(product_router, prefix="/api")
app.include_router(finance_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(history_router, prefix="/api")


# SQLAdmin back-office
from app.admin.setup import create_admin  # noqa: E402
from app.admin.views import (  # noqa: E402
    CondominiumAdmin,
    OperatorAssignmentAdmin,
    ProductAdmin,
    ProductPriceAdmin,
    UserAdmin,
)

admin = create_admin(app)
admin.add_view(UserAdmin)
admin.add_view(CondominiumAdmin)
admin.add_view(OperatorAssignmentAdmin)
admin.add_view(ProductAdmin)
admin.add_view(ProductPriceAdmin)
