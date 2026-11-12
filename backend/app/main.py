"""MotorPulse 大电机风险监测平台 —— API 服务入口。"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.services.collector import get_collector, start_collector

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    init_db()
    if settings.seed_demo_on_start:
        from app.db.seed import seed_demo

        seed_demo(reset=False)
    if settings.run_collector:
        start_collector()
        logger.info("采集调度器已启动，间隔 %s 分钟", settings.poll_interval_minutes)
    yield
    collector = get_collector()
    if collector:
        collector.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="大电机温度/电流 LoRa 无线监测、对比分析与飞书告警平台",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith(settings.api_prefix):
            logger.info(
                "%s %s %s %.0fms request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
            )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        logger.exception("未处理异常 path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务内部错误，请查看日志"})

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/api/docs")

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
