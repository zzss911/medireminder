"""Push 订阅 API - 对接 Supabase"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime

from ..auth import require_user
from ..supabase_client import table
from ..services.push_service import push_service

router = APIRouter(prefix="/api/push", tags=["push"])


class PushSubscriptionData(BaseModel):
    endpoint: str
    keys: dict


@router.get("/vapid-public-key")
async def get_vapid_public_key(request: Request):
    user_id = await require_user(request)
    key = push_service.get_vapid_public_key()
    return {"publicKey": key}


@router.post("/subscribe")
async def subscribe(request: Request, data: PushSubscriptionData):
    user_id = await require_user(request)
    user_agent = request.headers.get("user-agent", "")

    try:
        # 检查已存在的订阅
        existing = table("push_subscriptions").select("id").eq("user_id", user_id).eq("endpoint", data.endpoint).execute()
        if existing.data:
            table("push_subscriptions").update({
                "p256dh": data.keys.get("p256dh", ""),
                "auth": data.keys.get("auth", ""),
                "user_agent": user_agent,
                "last_used_at": datetime.utcnow().isoformat(),
            }).eq("id", existing.data[0]["id"]).execute()
            return {"message": "订阅已更新", "id": existing.data[0]["id"]}
        else:
            result = table("push_subscriptions").insert({
                "user_id": user_id,
                "endpoint": data.endpoint,
                "p256dh": data.keys.get("p256dh", ""),
                "auth": data.keys.get("auth", ""),
                "user_agent": user_agent,
                "created_at": datetime.utcnow().isoformat(),
                "last_used_at": datetime.utcnow().isoformat(),
            }).execute()
            return {"message": "订阅成功", "id": result.data[0]["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"订阅失败: {str(e)}")


@router.post("/unsubscribe")
async def unsubscribe(request: Request):
    user_id = await require_user(request)
    body = await request.json()
    endpoint = body.get("endpoint", "")

    try:
        result = table("push_subscriptions").delete().eq("user_id", user_id).eq("endpoint", endpoint).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="未找到订阅")
        return {"message": "已取消订阅"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消订阅失败: {str(e)}")


@router.post("/test")
async def test_push(request: Request):
    user_id = await require_user(request)
    result = await push_service.send_notification(
        user_id=user_id,
        title="💊 Zs服药提醒",
        body="这是一条测试推送通知！",
        tag="test",
    )
    return result
