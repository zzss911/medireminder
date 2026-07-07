"""用户设置 API（面向普通用户）"""
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from ..auth import require_user
from ..supabase_client import table

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    push_enabled: bool = True
    expiry_warn_days: int = 30


@router.get("")
async def get_settings(request: Request):
    user_id = await require_user(request)
    try:
        result = table("user_settings").select("*").eq("user_id", user_id).execute()
        if result.data:
            row = result.data[0]
            return {
                "push_enabled": row.get("push_enabled", True),
                "expiry_warn_days": row.get("expiry_warn_days", 30),
            }
    except:
        pass
    return {"push_enabled": True, "expiry_warn_days": 30}


@router.put("")
async def update_settings(request: Request, data: SettingsUpdate):
    user_id = await require_user(request)
    try:
        update_data = {
            "push_enabled": data.push_enabled,
            "expiry_warn_days": data.expiry_warn_days,
            "updated_at": datetime.utcnow().isoformat(),
        }
        existing = table("user_settings").select("id").eq("user_id", user_id).execute()
        if existing.data:
            table("user_settings").update(update_data).eq("user_id", user_id).execute()
        else:
            table("user_settings").insert({"user_id": user_id, **update_data}).execute()
        return {"message": "设置已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
