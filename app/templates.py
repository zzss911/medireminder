"""模板引擎全局实例"""
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from fastapi.responses import HTMLResponse

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    auto_reload=True,
    cache_size=400,
)


def render(name: str, context: dict = None) -> HTMLResponse:
    """渲染Jinja2模板并返回HTMLResponse"""
    ctx = dict(context) if context else {}
    template = env.get_template(name)
    content = template.render(ctx)
    return HTMLResponse(content=content)
