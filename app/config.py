"""应用配置"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Supabase 配置（URL/anon key 是公开的，service key 走环境变量）
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wchcfukrdmsymygplrkn.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "sb_publishable_placeholder")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# 仍然保留本地上传目录作为临时缓存
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "medicines")
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except OSError:
    pass  # Vercel 只读文件系统

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
