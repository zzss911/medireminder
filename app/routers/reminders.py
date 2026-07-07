"""提醒 API - 对接 Supabase"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime

from ..auth import require_user
from ..supabase_client import table

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    medicine_id: str
    remind_time: str
    frequency: str = "daily"
    dosage: str = "1片"
    days_of_week: str = ""


class ReminderUpdate(BaseModel):
    remind_time: str = None
    frequency: str = None
    dosage: str = None
    days_of_week: str = None
    is_active: bool = None


@router.post("")
async def create_reminder(request: Request, data: ReminderCreate):
    user_id = await require_user(request)

    try:
        # 验证药品存在
        med = table("medicines").select("id,name,specification").eq("id", data.medicine_id).eq("user_id", user_id).execute()
        if not med.data:
            raise HTTPException(status_code=404, detail="药品不存在")

        result = table("reminders").insert({
            "user_id": user_id,
            "medicine_id": data.medicine_id,
            "remind_time": data.remind_time,
            "frequency": data.frequency,
            "dosage": data.dosage,
            "days_of_week": data.days_of_week,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        if result.data:
            row = result.data[0]
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "medicine_id": row["medicine_id"],
                "remind_time": row["remind_time"],
                "frequency": row["frequency"],
                "dosage": row["dosage"],
                "days_of_week": row["days_of_week"],
                "is_active": row["is_active"],
                "medicine_name": med.data[0].get("name", ""),
                "medicine_spec": med.data[0].get("specification", ""),
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建提醒失败: {str(e)}")


@router.get("")
async def list_reminders(request: Request):
    user_id = await require_user(request)

    try:
        result = table("reminders").select("*").eq("user_id", user_id).order("remind_time").execute()
        reminders = []
        for row in (result.data or []):
            med = table("medicines").select("name,specification").eq("id", row["medicine_id"]).execute()
            med_name = med.data[0]["name"] if med.data else ""
            med_spec = med.data[0]["specification"] if med.data else ""
            reminders.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "medicine_id": row["medicine_id"],
                "remind_time": row["remind_time"],
                "frequency": row["frequency"],
                "dosage": row["dosage"],
                "days_of_week": row["days_of_week"],
                "is_active": row["is_active"],
                "created_at": row.get("created_at", ""),
                "medicine_name": med_name,
                "medicine_spec": med_spec,
            })
        return reminders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提醒列表失败: {str(e)}")


@router.put("/{reminder_id}")
async def update_reminder(request: Request, reminder_id: str, data: ReminderUpdate):
    user_id = await require_user(request)

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    try:
        result = table("reminders").update(update_data).eq("id", reminder_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="提醒不存在")
        row = result.data[0]
        med = table("medicines").select("name,specification").eq("id", row["medicine_id"]).execute()
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "medicine_id": row["medicine_id"],
            "remind_time": row["remind_time"],
            "frequency": row["frequency"],
            "dosage": row["dosage"],
            "days_of_week": row["days_of_week"],
            "is_active": row["is_active"],
            "medicine_name": med.data[0]["name"] if med.data else "",
            "medicine_spec": med.data[0]["specification"] if med.data else "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新提醒失败: {str(e)}")


@router.delete("/{reminder_id}")
async def delete_reminder(request: Request, reminder_id: str):
    user_id = await require_user(request)

    try:
        result = table("reminders").delete().eq("id", reminder_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="提醒不存在")
        return {"message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除提醒失败: {str(e)}")
