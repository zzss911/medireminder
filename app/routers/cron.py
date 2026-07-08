"""Vercel Cron Jobs — 替代 APScheduler 定时任务

部署后在 vercel.json 的 crons 配置：
[
  { "path": "/api/cron/generate-records", "schedule": "5 0 * * *" },
  { "path": "/api/cron/send-reminders", "schedule": "* * * * *" },
  { "path": "/api/cron/check-expiry", "schedule": "0 8 * * *" }
]
"""
import logging
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request

from ..supabase_client import table
from ..services.notification_service import notification_service
from ..services.push_service import push_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cron", tags=["cron"])

# 简单的鉴权（防止外部随意调用）
CRON_SECRET = "medireminder-cron-2026"


def _check_secret(request: Request) -> bool:
    """检查 CRON 密钥"""
    header = request.headers.get("Authorization", "")
    return header == f"Bearer {CRON_SECRET}"


@router.post("/generate-records")
async def cron_generate_records(request: Request):
    """每日凌晨生成当天服药记录"""
    if not _check_secret(request):
        return {"error": "unauthorized"}

    today_str = date.today().strftime("%Y-%m-%d")
    weekday = str(date.today().weekday() + 1)

    try:
        reminders = table("reminders").select("*").eq("is_active", True).execute()
    except Exception as e:
        return {"error": str(e), "count": 0}

    created = 0
    for rem in (reminders.data or []):
        freq = rem.get("frequency", "daily")
        should_remind = freq == "daily"
        if freq == "weekly":
            days = (rem.get("days_of_week") or "").split(",")
            should_remind = weekday in days
        if not should_remind:
            continue

        # 检查是否已有今天的记录
        existing = table("medication_records").select("id").eq("user_id", rem["user_id"]).eq("medicine_id", rem["medicine_id"]).eq("scheduled_date", today_str).execute()
        if existing.data:
            continue

        try:
            table("medication_records").insert({
                "user_id": rem["user_id"],
                "medicine_id": rem["medicine_id"],
                "reminder_id": rem["id"],
                "scheduled_date": today_str,
                "scheduled_time": rem["remind_time"],
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            created += 1
        except Exception:
            pass

    return {"ok": True, "records_created": created, "date": today_str}


@router.post("/send-reminders")
async def cron_send_reminders(request: Request):
    """每分钟检查并发送推送提醒"""
    if not _check_secret(request):
        return {"error": "unauthorized"}

    today_str = date.today().strftime("%Y-%m-%d")
    now = datetime.now()
    now_str = now.strftime("%H:%M")

    try:
        records = table("medication_records").select("*").eq("scheduled_date", today_str).eq("scheduled_time", now_str).eq("status", "pending").execute()
    except Exception as e:
        return {"error": str(e)}

    sent = 0
    for rec in (records.data or []):
        try:
            med = table("medicines").select("name,specification").eq("id", rec["medicine_id"]).execute()
            med_name = med.data[0]["name"] if med.data else "药品"
            med_spec = med.data[0].get("specification", "") if med.data else ""

            body = f"该服用 {med_name} 了"
            if med_spec:
                body += f"（{med_spec}）"

            result = await push_service.send_notification(
                user_id=rec["user_id"],
                title="💊 服药提醒",
                body=body,
                tag=f"med-{rec['id']}",
                url="/"
            )
            if result.get("success", 0) > 0:
                sent += 1
        except Exception as e:
            logger.warning(f"Send reminder failed for record {rec.get('id')}: {e}")

    return {"ok": True, "pending": len(records.data or []), "sent": sent, "time": now_str}


@router.post("/check-expiry")
async def cron_check_expiry(request: Request):
    """每日检查过期药品并推送警告"""
    if not _check_secret(request):
        return {"error": "unauthorized"}

    today = date.today()
    warned = 0

    try:
        users = table("medicines").select("user_id").execute()
        user_ids = list(set(row["user_id"] for row in (users.data or [])))
    except Exception as e:
        return {"error": str(e)}

    for uid in user_ids:
        expiring = await notification_service.get_expiring_medicines(uid)
        for med in expiring:
            expiry_str = med.get("expiry_date", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                days_left = (expiry - today).days
                if days_left < 0:
                    msg = f"「{med['name']}」已经过期，请及时处理"
                elif days_left <= 7:
                    msg = f"「{med['name']}」还有 {days_left} 天过期"
                else:
                    msg = f"「{med['name']}」将在 {days_left} 天后过期"

                await push_service.send_notification(uid, "⚠️ 药品过期提醒", msg)
                warned += 1
            except Exception:
                pass

    return {"ok": True, "warned": warned, "date": today.strftime("%Y-%m-%d")}
