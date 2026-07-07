"""Zs服药提醒智能体 - 主应用入口（Supabase 版本）"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR

IS_VERCEL = os.environ.get("VERCEL") == "1"


def create_app(mount_static: bool = True) -> FastAPI:
    """创建 FastAPI 应用

    Args:
        mount_static: 是否挂载静态文件目录（Vercel 不需要，由 CDN 处理）
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if not IS_VERCEL:
            from .services.scheduler_service import start_scheduler, stop_scheduler
            start_scheduler()
        yield
        if not IS_VERCEL:
            stop_scheduler()

    app = FastAPI(
        title="Zs服药提醒智能体",
        description="AI驱动的服药提醒应用 - Supabase 版",
        version="2.1.0",
        lifespan=lifespan,
    )

    # 静态文件（本地开发用，Vercel 由 CDN 处理）
    if mount_static:
        static_dir = os.path.join(BASE_DIR, "static")
        uploads_dir = os.path.join(BASE_DIR, "uploads")
        try:
            os.makedirs(uploads_dir, exist_ok=True)
        except OSError:
            pass
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        try:
            app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
        except RuntimeError:
            pass  # Vercel 上 uploads 目录可能不存在

    # 注册路由
    from .routers import auth, medicines, reminders, records, pages, push, settings

    app.include_router(auth.router)
    app.include_router(medicines.router)
    app.include_router(reminders.router)
    app.include_router(records.router)
    app.include_router(push.router)
    app.include_router(settings.router)
    app.include_router(pages.router)

    return app


# 本地和 Vercel 都用相同的 app
app = create_app(mount_static=True)
app_no_static = app
