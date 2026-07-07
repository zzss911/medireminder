"""AI 识别服务 - 可插拔多后端架构

支持后端:
1. EasyOCR - 本地离线 OCR（默认）
2. Claude Vision - Anthropic Claude 多模态 API
3. OpenAI Vision - OpenAI GPT-4 Vision API
4. Qianwen Vision - 通义千问 Qwen-VL 多模态
"""

import re
import json
import base64
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.config import OCR_LANGUAGES, AI_PROVIDER, AI_API_KEY, AI_API_URL, QWEN_API_URL, QWEN_MODEL

logger = logging.getLogger(__name__)


class AIBackend(ABC):
    """AI 识别后端抽象基类"""

    @abstractmethod
    async def recognize(self, image_path: str) -> dict:
        """识别图片，返回 {'name', 'specification', 'expiry_date', 'description', 'raw_text'}"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查后端是否可用"""
        pass


class EasyOCRBackend(AIBackend):
    """EasyOCR 本地离线识别"""

    def __init__(self):
        self._reader = None

    @property
    def reader(self):
        if self._reader is None:
            try:
                import easyocr
                logger.info("Loading EasyOCR model...")
                self._reader = easyocr.Reader(OCR_LANGUAGES, gpu=False)
            except ImportError:
                logger.warning("EasyOCR not installed, OCR disabled")
                self._reader = False  # 标记为不可用
        return self._reader

    def is_available(self) -> bool:
        try:
            return self.reader is not None and self.reader is not False
        except:
            return False

    def is_available(self) -> bool:
        try:
            return self.reader is not None and self.reader is not False
        except:
            return False

    async def recognize(self, image_path: str) -> dict:
        try:
            results = self.reader.readtext(image_path, detail=0)

            if not results:
                return {
                    "name": "", "specification": "", "expiry_date": "",
                    "description": "", "raw_text": "未能识别出文字，请手动输入"
                }

            raw_text = "\n".join(results)
            parsed = self._parse_medicine_info(results, raw_text)

            return {
                "name": parsed.get("name", ""),
                "specification": parsed.get("specification", ""),
                "expiry_date": parsed.get("expiry_date", ""),
                "description": parsed.get("description", ""),
                "raw_text": raw_text,
                "backend": "easyocr",
            }
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return {
                "name": "", "specification": "", "expiry_date": "",
                "description": "", "raw_text": f"识别出错: {str(e)}", "backend": "easyocr",
            }

    def _parse_medicine_info(self, text_lines: list, raw_text: str) -> dict:
        result = {"name": "", "specification": "", "expiry_date": "", "description": raw_text}

        expiry = self._extract_expiry_date(raw_text)
        if expiry:
            result["expiry_date"] = expiry

        spec = self._extract_specification(raw_text)
        if spec:
            result["specification"] = spec

        name = self._extract_name(text_lines, raw_text)
        if name:
            result["name"] = name

        return result

    def _extract_expiry_date(self, text: str) -> str:
        patterns = [
            r'有效期[至到:：]?\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)',
            r'EXP[^:：]*[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)\s*(?:到期|过期|有效)',
            r'(\d{4}\.\d{2}\.\d{2})',
            r'有效期\s*[:：]?\s*(\d{4}年\d{1,2}月)',
            r'(\d{4}[/-]\d{2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._normalize_date(match.group(1))
        return ""

    def _extract_specification(self, text: str) -> str:
        patterns = [
            r'(\d+(?:\.\d+)?\s*(?:mg|g|ml|μg|mcg|IU|单位)(?:\s*[/×xX]\s*\d+\s*(?:片|粒|支|瓶|袋))?)',
            r'规格\s*[:：]?\s*([^\n，。,\.]{2,20})',
            r'(\d+\s*(?:片|粒|支|瓶|袋|包))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_name(self, lines: list, raw_text: str) -> str:
        drug_patterns = [
            r'([\u4e00-\u9fff]{2,10}(?:片|胶囊|颗粒|口服液|注射液|滴眼液|软膏|喷雾|糖浆|冲剂|丸|散|膏))',
            r'([\u4e00-\u9fff]{2,8}(?:霉素|西林|沙星|洛尔|地平|普利|他汀|拉唑|替丁|泮))',
        ]
        for pattern in drug_patterns:
            match = re.search(pattern, raw_text)
            if match:
                return match.group(1)

        for line in lines:
            cleaned = line.strip()
            if 3 <= len(cleaned) <= 30 and not re.match(r'^[\d\s\./\-:：]+$', cleaned):
                return cleaned
        return ""

    def _normalize_date(self, date_str: str) -> str:
        date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "")
        date_str = date_str.replace("/", "-").replace(".", ".")
        date_str = re.sub(r'\s+', '', date_str).replace(".", "-")
        parts = date_str.split("-")
        if len(parts) == 2:
            date_str = f"{date_str}-01"
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return date_str


class VisionAPIBackend(AIBackend):
    """通用 Vision API 后端 - 支持 Claude / OpenAI"""

    SYSTEM_PROMPT = """你是一个专业的药品识别助手。请分析这张药品包装/药盒/药瓶的照片，提取以下信息，以JSON格式返回：

{
  "name": "药品通用名称（中文商品名或通用名）",
  "specification": "药品规格，如 10mg*30片、0.3g*24粒、100ml/瓶",
  "expiry_date": "有效期，格式 YYYY-MM-DD，如未找到留空字符串",
  "description": "药品说明文字摘要，包括适应症、用法用量等关键信息"
}

注意：
- 只返回JSON，不要任何其他文字
- 如果某项信息未找到，对应字段留空字符串
- 仔细识别有效期，通常标注为"有效期至"、"EXP"等"""

    def __init__(self, api_key: str = "", api_url: str = "", provider: str = "claude"):
        self.api_key = api_key
        self.api_url = api_url
        self.provider = provider

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def recognize(self, image_path: str) -> dict:
        if not self.api_key:
            return {"name": "", "specification": "", "expiry_date": "",
                    "description": "", "raw_text": "未配置AI API密钥", "backend": self.provider}

        try:
            # 读取并编码图片
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            ext = image_path.rsplit(".", 1)[-1].lower()
            mime_type = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp") else "image/jpeg"

            if self.provider == "claude":
                return await self._call_claude(image_data, mime_type)
            elif self.provider == "openai":
                return await self._call_openai(image_data, mime_type)
            elif self.provider == "qianwen":
                return await self._call_qianwen(image_data, mime_type)
            else:
                return {"name": "", "specification": "", "expiry_date": "",
                        "description": "", "raw_text": f"未知AI提供商: {self.provider}",
                        "backend": self.provider}

        except Exception as e:
            logger.error(f"Vision API error: {e}")
            return {"name": "", "specification": "", "expiry_date": "",
                    "description": "", "raw_text": f"AI识别出错: {str(e)}", "backend": self.provider}

    async def _call_claude(self, image_b64: str, mime_type: str) -> dict:
        """调用 Claude Vision API"""
        import httpx

        url = self.api_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_b64,
                    }},
                    {"type": "text", "text": self.SYSTEM_PROMPT},
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]

        return self._parse_json_response(text)

    async def _call_openai(self, image_b64: str, mime_type: str) -> dict:
        """调用 OpenAI Vision API"""
        import httpx

        url = self.api_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4o",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}"
                    }},
                    {"type": "text", "text": self.SYSTEM_PROMPT},
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]

        return self._parse_json_response(text)

    async def _call_qianwen(self, image_b64: str, mime_type: str) -> dict:
        """调用通义千问 Qwen-VL 视觉模型（兼容 OpenAI 格式）"""
        import httpx

        url = self.api_url or f"{QWEN_API_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": QWEN_MODEL,
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}"
                    }},
                    {"type": "text", "text": self.SYSTEM_PROMPT},
                ]
            }]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            # 把 HTTP 错误正文也带回
            if resp.status_code >= 400:
                err_body = resp.text[:300]
                return {"name": "", "specification": "", "expiry_date": "",
                        "description": "", "raw_text": f"HTTP {resp.status_code}: {err_body}",
                        "backend": self.provider, "error": f"HTTP {resp.status_code}"}
            data = resp.json()
            # 千问错误返回格式: {"error": {"code": "...", "message": "..."}}
            if "error" in data and "choices" not in data:
                err_msg = data["error"].get("message", "未知错误")
                err_code = data["error"].get("code", "")
                return {"name": "", "specification": "", "expiry_date": "",
                        "description": "", "raw_text": f"[{err_code}] {err_msg}",
                        "backend": self.provider, "error": err_msg}
            text = data["choices"][0]["message"]["content"]

        return self._parse_json_response(text)

    def _parse_json_response(self, text: str) -> dict:
        """解析 AI 返回的 JSON"""
        raw_text = text
        # 清理可能的 markdown 代码块标记
        text = re.sub(r'```(?:json)?\s*', '', text).strip()
        text = re.sub(r'```\s*$', '', text).strip()

        try:
            parsed = json.loads(text)
            return {
                "name": parsed.get("name", ""),
                "specification": parsed.get("specification", ""),
                "expiry_date": parsed.get("expiry_date", ""),
                "description": parsed.get("description", ""),
                "raw_text": raw_text,
                "backend": self.provider,
            }
        except json.JSONDecodeError:
            return {
                "name": "", "specification": "", "expiry_date": "",
                "description": "", "raw_text": raw_text,
                "backend": self.provider,
            }


class OCRService:
    """OCR 识别服务 - 使用全局环境变量配置"""

    def __init__(self):
        self._easyocr = EasyOCRBackend()
        self._vision_backend = None

    async def recognize(self, image_path: str) -> dict:
        """根据全局配置选择后端进行识别"""
        global_provider = AI_PROVIDER
        global_api_key = AI_API_KEY

        if global_provider == "easyocr" or not global_api_key:
            return await self._easyocr.recognize(image_path)

        # 使用指定的 Vision API
        if self._vision_backend is None or self._vision_backend.provider != global_provider:
            api_url = AI_API_URL
            if global_provider == "qianwen" and not api_url:
                api_url = QWEN_API_URL
            self._vision_backend = VisionAPIBackend(
                api_key=global_api_key,
                api_url=api_url,
                provider=global_provider,
            )

        try:
            result = await self._vision_backend.recognize(image_path)
            if result.get("name"):
                return result
            # 识别失败，附带错误信息
            if "error" in result:
                raise Exception(f"AI 识别失败: {result['error']}")
            raise Exception(f"AI 返回空结果: {result.get('raw_text', '')[:200]}")
        except Exception as e:
            logger.warning(f"Vision API failed: {e}")
            # 不再静默回退到 EasyOCR（Vercel 上没装），把错误抛给上层
            raise

    async def _call_qianwen_with_key_check(self, image_path: str) -> dict:
        """便利方法 - 用于直接调用的临时调试"""
        if not AI_API_KEY:
            raise Exception("未配置千问 API Key (AI_API_KEY 环境变量)")
        return await self._vision_backend.recognize(image_path)


ocr_service = OCRService()

