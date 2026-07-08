"""Cron 定时任务 — 由 GitHub Actions 外部调用触发

调用方需携带 Authorization: Bearer <CRON_SECRET>
CRON_SECRET 通过环境变量配置
"""
import os
import logging
from datetime import datetime, date, timedelta
from fastapi import APIRouter, HTTPException, Request

from ..supabase_client import table
from ..services.notification_service import notification_service
from ..services.push_service import push_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cron", tags=["cron"])

CRON_SECRET = os.environ.get("CRON_SECRET", "")

# 提醒扫描窗口（分钟）：查找 scheduled_time 在当前时间 ± 范围内且未推送的记录
REMINDER_WINDOW_MINUTES = 5


def _check_secret(request: Request):
    """校验 CRON_SECRET — GitHub Actions 调用时携带"""
    if not CRON_SECRET:
        return  # 未配置则不校验
    header = request.headers.get("Authorization", "")
    if header != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/generate-records")
async def cron_generate_records(request: Request):
    """每日凌晨生成当天服药记录"""
    _check_secret(request)

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

        # 检查是否已有今天的记录（不含已取消/延后的）
        existing = (
            table("medication_records")
            .select("id")
            .eq("user_id", rem["user_id"])
            .eq("medicine_id", rem["medicine_id"])
            .eq("scheduled_date", today_str)
            .execute()
        )
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
    """扫描最近 N 分钟内的待提醒记录并推送（防重复）"""
    _check_secret(request)

    today_str = date.today().strftime("%Y-%m-%d")
    now = datetime.utcnow()

    # 生成时间窗口：当前时刻 ± REMINDER_WINDOW_MINUTES 的所有分钟
    time_slots = []
    for offset in range(-REMINDER_WINDOW_MINUTES, REMINDER_WINDOW_MINUTES + 1):
        t = now + timedelta(minutes=offset)
        time_slots.append(t.strftime("%H:%M"))

    sent = 0
    total_pending = 0

    for t in time_slots:
        try:
            records = (
                table("medication_records")
                .select("*")
                .eq("scheduled_date", today_str)
                .eq("scheduled_time", t)
                .eq("status", "pending")
                .execute()
            )
        except Exception:
            continue

        for rec in (records.data or []):
            total_pending += 1

            # 防重复：检查是否 5 分钟内已推送过（用 actual_time + note 做简易标记）
            notified = rec.get("note") or ""
            if "auto_notified:" in notified:
                try:
                    last_time = datetime.fromisoformat(notified.split("auto_notified:")[1].strip())
                    if (now - last_time).total_seconds() < 300:  # 5分钟内
                        continue
                except Exception:
                    pass

            try:
                med = (
                    table("medicines")
                    .select("name,specification")
                    .eq("id", rec["medicine_id"])
                    .execute()
                )
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
                    url="/",
                )

                # 标记已推送（写 note 字段防重复）
                sent_count = result.get("success", 0)
                if sent_count > 0:
                    sent += 1
                    try:
                        table("medication_records").update({
                            "note": f"auto_notified:{now.isoformat()}",
                        }).eq("id", rec["id"]).execute()
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Send reminder failed for record {rec.get('id')}: {e}")

    return {
        "ok": True,
        "pending": total_pending,
        "sent": sent,
        "window_minutes": REMINDER_WINDOW_MINUTES,
        "time": now.strftime("%H:%M"),
    }


@router.post("/check-expiry")
async def cron_check_expiry(request: Request):
    """每日检查过期药品并推送警告"""
    _check_secret(request)

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
