"""后台定时任务调度器 - 对接 Supabase"""
import logging
from datetime import datetime, date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..supabase_client import table
from .notification_service import notification_service
from .push_service import push_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _generate_all_today_records():
    """为所有用户生成今日服药记录"""
    logger.info("Running: generate_all_today_records")
    try:
        # 查询所有有活跃提醒的用户
        result = table("reminders").select("user_id").eq("is_active", True).execute()
        user_ids = set()
        for r in (result.data or []):
            user_ids.add(r["user_id"])

        for uid in user_ids:
            try:
                await notification_service.generate_today_records(uid)
            except Exception as e:
                logger.error(f"Failed to generate records for user {uid}: {e}")

        logger.info(f"Daily records generated for {len(user_ids)} users")
    except Exception as e:
        logger.error(f"generate_all_today_records failed: {e}")


async def _check_expiring_medicines():
    """检查过期药品并推送通知"""
    logger.info("Running: check_expiring_medicines")
    today = date.today()

    try:
        result = table("medicines").select("id,user_id,name,expiry_date").execute()
        user_meds = {}
        for m in (result.data or []):
            expiry_str = m.get("expiry_date", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                days_left = (expiry - today).days
                if days_left in (7, 3, 1, 0) or days_left < 0:
                    uid = m["user_id"]
                    if uid not in user_meds:
                        user_meds[uid] = []
                    user_meds[uid].append((m["name"], days_left))
            except ValueError:
                continue

        for uid, meds in user_meds.items():
            for name, days_left in meds:
                try:
                    await push_service.send_expiry_warning(uid, name, days_left)
                    logger.info(f"Sent expiry warning to {uid} for {name} ({days_left}d)")
                except Exception as e:
                    logger.error(f"Failed to send expiry warning: {e}")
    except Exception as e:
        logger.error(f"_check_expiring_medicines failed: {e}")


async def _send_reminder_notifications():
    """检查当前时间是否有需要推送的提醒"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    weekday = str(now.weekday() + 1)

    try:
        reminders = table("reminders").select("*").eq("is_active", True).eq("remind_time", current_time).execute()

        for reminder in (reminders.data or []):
            should_remind = reminder.get("frequency", "daily") == "daily"
            freq = reminder.get("frequency", "daily")
            if freq == "weekly":
                days = reminder.get("days_of_week", "").split(",")
                if weekday in days:
                    should_remind = True

            if not should_remind:
                continue

            med = table("medicines").select("name").eq("id", reminder["medicine_id"]).execute()
            if not med.data:
                continue

            try:
                await push_service.send_medication_reminder(
                    reminder["user_id"],
                    med.data[0]["name"],
                    reminder.get("dosage", ""),
                )
                logger.info(f"Sent reminder to {reminder['user_id']} for {med.data[0]['name']}")
            except Exception as e:
                logger.error(f"Failed to send reminder: {e}")
    except Exception as e:
        logger.error(f"_send_reminder_notifications failed: {e}")


def start_scheduler():
    scheduler.add_job(
        _generate_all_today_records,
        CronTrigger(hour=0, minute=5),
        id="generate_daily_records",
        name="生成每日服药记录",
    )
    scheduler.add_job(
        _check_expiring_medicines,
        CronTrigger(hour=8, minute=0),
        id="check_expiring",
        name="检查过期药品",
    )
    scheduler.add_job(
        _send_reminder_notifications,
        CronTrigger(minute="*"),
        id="send_reminders",
        name="发送服药提醒",
    )
    scheduler.add_job(
        _generate_all_today_records,
        CronTrigger(hour=3, minute=0),
        id="generate_daily_records_backup",
        name="生成每日服药记录(备用)",
    )
    scheduler.start()
    logger.info("Scheduler started with 4 jobs")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
