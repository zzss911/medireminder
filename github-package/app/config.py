"""应用配置"""
import os
import tempfile
from dotenv import load_dotenv

# 加载 .env（仅本地开发，Vercel 用环境变量）
load_dotenv()

IS_VERCEL = os.environ.get("VERCEL") == "1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Supabase 配置（URL/anon key 是公开的，service key 走环境变量）
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wchcfukrdmsymygplrkn.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_placeholder")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# 上传目录：Vercel 用系统临时目录，本地用项目目录
if IS_VERCEL:
    UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "medireminder-uploads")
else:
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "medicines")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 允许的图片格式
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp", "gif"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# EasyOCR 语言
OCR_LANGUAGES = ["ch_sim", "en"]

# AI 识别配置（管理员通过环境变量设置）
AI_PROVIDER = os.environ.get("AI_PROVIDER", "qianwen")  # easyocr / claude / openai / qianwen
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_API_URL = os.environ.get("AI_API_URL", "")
QWEN_API_URL = os.environ.get("QWEN_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen-vl-plus")  # qwen-vl-plus / qwen-vl-max

# Cron 密钥（GitHub Actions 调用时校验）
CRON_SECRET = os.environ.get("CRON_SECRET", "")
