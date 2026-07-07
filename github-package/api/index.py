"""Vercel Serverless 入口 - 导入 FastAPI 应用"""
import os
import sys

# 把项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 标记为 Vercel 环境
os.environ.setdefault("VERCEL", "1")

# 导入应用（不使用静态文件挂载，Vercel CDN 处理静态资源）
from app.main import app_no_static as app
