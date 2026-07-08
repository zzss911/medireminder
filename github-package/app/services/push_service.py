"""Web Push 推送服务 — 使用 pywebpush (VAPID + aes128gcm 加密)"""
import os
import json
import base64
import logging
import tempfile
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from ..supabase_client import table

logger = logging.getLogger(__name__)

# VAPID 密钥文件路径
_VAPID_DIR_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".vapid")
try:
    os.makedirs(_VAPID_DIR_APP, exist_ok=True)
    VAPID_DIR = _VAPID_DIR_APP
except OSError:
    VAPID_DIR = os.path.join(tempfile.gettempdir(), "medireminder-vapid")
    os.makedirs(VAPID_DIR, exist_ok=True)


def _generate_vapid_keys():
    """生成 VAPID 密钥对并保存到文件（Vercel 上回退到内存）"""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()

    # 尝试持久化到文件（Vercel 可能失败，但不影响使用）
    try:
        os.makedirs(VAPID_DIR, exist_ok=True)
        with open(os.path.join(VAPID_DIR, "private_key.pem"), "w") as f:
            f.write(private_pem)
        with open(os.path.join(VAPID_DIR, "public_key.txt"), "w") as f:
            f.write(public_b64)
    except OSError:
        pass  # Vercel 只读，密钥仅保存在内存

    return private_pem, public_b64


def _load_vapid_keys():
    """加载 VAPID 密钥：优先环境变量，其次文件，最后自动生成"""
    # 1) 环境变量（Vercel 部署用，固定密钥避免每次冷启变化）
    env_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    env_public = os.environ.get("VAPID_PUBLIC_KEY", "")
    if env_private and env_public:
        private_key = env_private.replace("\\n", "\n")
        return private_key, env_public

    # 2) 本地文件缓存
    private_path = os.path.join(VAPID_DIR, "private_key.pem")
    public_path = os.path.join(VAPID_DIR, "public_key.txt")
    if os.path.exists(private_path) and os.path.exists(public_path):
        with open(private_path, "rb") as f:
            private_key = f.read().decode()
        with open(public_path, "r") as f:
            public_key = f.read().strip()
        return private_key, public_key

    # 3) 自动生成（本地开发用）
    return _generate_vapid_keys()


VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY = _load_vapid_keys()
VAPID_CLAIMS = {"sub": "mailto:admin@medireminder.app"}


class PushService:
    """Web Push 通知服务 (pywebpush)"""

    def get_vapid_public_key(self) -> str:
        """获取 VAPID 公钥（给前端 PushManager.subscribe 用）"""
        return VAPID_PUBLIC_KEY

    async def save_subscription(self, user_id: str, subscription: dict, user_agent: str = "") -> dict:
        """保存推送订阅"""
        try:
            existing = table("push_subscriptions").select("id").eq("user_id", user_id).eq("endpoint", subscription.get("endpoint", "")).execute()
            sub_data = {
                "p256dh": subscription.get("keys", {}).get("p256dh", ""),
                "auth": subscription.get("keys", {}).get("auth", ""),
                "last_used_at": datetime.utcnow().isoformat(),
                "user_agent": user_agent,
            }
            if existing.data:
                table("push_subscriptions").update(sub_data).eq("id", existing.data[0]["id"]).execute()
                return existing.data[0]
            else:
                sub_data.update({
                    "user_id": user_id,
                    "endpoint": subscription.get("endpoint", ""),
                    "created_at": datetime.utcnow().isoformat(),
                })
                result = table("push_subscriptions").insert(sub_data).execute()
                return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Save subscription failed: {e}")
            return None

    async def delete_subscription(self, user_id: str, endpoint: str) -> bool:
        try:
            result = table("push_subscriptions").delete().eq("user_id", user_id).eq("endpoint", endpoint).execute()
            return bool(result.data)
        except:
            return False

    async def get_user_subscriptions(self, user_id: str) -> list:
        try:
            result = table("push_subscriptions").select("*").eq("user_id", user_id).execute()
            return result.data or []
        except:
            return []

    async def send_notification(self, user_id: str, title: str, body: str, tag: str = "", url: str = "/") -> dict:
        """向用户的所有设备发送 Web Push 通知"""
        subscriptions = await self.get_user_subscriptions(user_id)
        if not subscriptions:
            return {"success": 0, "failed": 0, "message": "无订阅设备"}

        success = 0
        failed = 0
        import pywebpush

        for sub in subscriptions:
            try:
                subscription_info = {
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                }

                payload = json.dumps({
                    "title": title,
                    "body": body,
                    "tag": tag or f"med-{int(datetime.utcnow().timestamp())}",
                    "icon": "/static/images/icon-192.png",
                    "badge": "/static/images/icon-192.png",
                    "data": {"url": url},
                    "actions": [{"action": "open", "title": "查看"}],
                })

                pywebpush.webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                    timeout=10,
                )
                success += 1
            except Exception as e:
                logger.warning(f"Push failed to {sub.get('endpoint', '')[:50]}: {e}")
                # 如果是 410 Gone 或 404，说明订阅已失效，应该清理
                if "410" in str(e) or "404" in str(e):
                    try:
                        await self.delete_subscription(user_id, sub["endpoint"])
                    except:
                        pass
                failed += 1

        return {"success": success, "failed": failed}

    async def send_medication_reminder(self, user_id: str, medicine_name: str, dosage: str = "") -> dict:
        body = f"该服用 {medicine_name} 了"
        if dosage:
            body += f"，用量：{dosage}"
        return await self.send_notification(user_id, "💊 服药提醒", body)

    async def send_expiry_warning(self, user_id: str, medicine_name: str, days_left: int) -> dict:
        if days_left < 0:
            return await self.send_notification(user_id, "⚠️ 药品已过期", f"「{medicine_name}」已经过期，请及时处理")
        elif days_left <= 7:
            return await self.send_notification(user_id, "⏰ 药品即将过期", f"「{medicine_name}」还有 {days_left} 天过期")
        else:
            return await self.send_notification(user_id, "📋 药品过期提醒", f"「{medicine_name}」将在 {days_left} 天后过期")


push_service = PushService()
