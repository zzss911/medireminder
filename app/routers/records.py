"""服药记录 API - 对接 Supabase"""
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from ..auth import require_user
from ..supabase_client import table
from ..services.notification_service import notification_service

router = APIRouter(prefix="/api/records", tags=["records"])


class RecordUpdate(BaseModel):
    status: str
    actual_time: str = None
    note: str = None


@router.get("/today")
async def get_today_records(request: Request):
    user_id = await require_user(request)
    items = await notification_service.get_today_pending(user_id)
    return items


@router.get("")
async def get_records(request: Request, date_filter: str = Query(None, alias="date")):
    user_id = await require_user(request)

    try:
        q = table("medication_records").select("*").eq("user_id", user_id)
        if date_filter:
            q = q.eq("scheduled_date", date_filter)
        q = q.order("created_at", desc=True)
        result = q.execute()

        records = []
        for row in (result.data or []):
            med = table("medicines").select("name,specification").eq("id", row["medicine_id"]).execute()
            records.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "medicine_id": row["medicine_id"],
                "reminder_id": row.get("reminder_id"),
                "scheduled_date": row["scheduled_date"],
                "scheduled_time": row["scheduled_time"],
                "status": row["status"],
                "actual_time": row.get("actual_time", ""),
                "note": row.get("note", ""),
                "created_at": row.get("created_at", ""),
                "medicine_name": med.data[0]["name"] if med.data else "",
                "medicine_spec": med.data[0]["specification"] if med.data else "",
            })
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取记录失败: {str(e)}")


@router.post("/{record_id}/action")
async def record_action(request: Request, record_id: str, data: RecordUpdate):
    user_id = await require_user(request)

    if data.status not in ["taken", "delayed", "skipped"]:
        raise HTTPException(status_code=400, detail="状态必须是 taken/delayed/skipped")

    actual_time = data.actual_time or datetime.now().strftime("%H:%M")

    try:
        result = table("medication_records").update({
            "status": data.status,
            "actual_time": actual_time,
            "note": data.note or "",
        }).eq("id", record_id).eq("user_id", user_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="记录不存在")

        return {
            "id": record_id,
            "status": data.status,
            "actual_time": actual_time,
            "message": "记录已更新",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新记录失败: {str(e)}")
