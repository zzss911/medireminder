"""推送通知服务 - 对接 Supabase"""
from datetime import datetime, date, timedelta

from ..supabase_client import table


class NotificationService:

    async def _get_user_expiry_warn_days(self, user_id: str) -> int:
        """读取用户设置的过期提醒天数"""
        try:
            result = table("user_settings").select("expiry_warn_days").eq("user_id", user_id).execute()
            if result.data:
                return result.data[0].get("expiry_warn_days", 30)
        except Exception:
            pass
        return 30

    async def get_expiring_medicines(self, user_id: str) -> list:
        """获取即将过期的药品列表"""
        try:
            result = table("medicines").select("*").eq("user_id", user_id).execute()
            today_date = date.today()
            warn_days = await self._get_user_expiry_warn_days(user_id)
            warn_date = today_date + timedelta(days=warn_days)
            expiring = []

            for m in (result.data or []):
                expiry_str = m.get("expiry_date", "")
                if not expiry_str:
                    continue
                try:
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                    if expiry <= warn_date:
                        expiring.append(m)
                except ValueError:
                    continue
            return expiring
        except Exception:
            return []

    async def generate_today_records(self, user_id: str) -> list:
        """为今天生成待服药记录"""
        today_str = date.today().strftime("%Y-%m-%d")
        weekday = str(date.today().weekday() + 1)

        try:
            reminders = table("reminders").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        except Exception:
            return []

        created_records = []
        for reminder in (reminders.data or []):
            should_remind = False
            freq = reminder.get("frequency", "daily")
            if freq == "daily":
                should_remind = True
            elif freq == "weekly":
                days = reminder.get("days_of_week", "").split(",")
                if weekday in days:
                    should_remind = True

            if not should_remind:
                continue

            # 检查是否已有今天的记录
            try:
                existing = table("medication_records").select("id").eq("user_id", user_id).eq("medicine_id", reminder["medicine_id"]).eq("scheduled_date", today_str).execute()
                if existing.data:
                    continue
            except:
                pass

            # 创建记录
            try:
                result = table("medication_records").insert({
                    "user_id": user_id,
                    "medicine_id": reminder["medicine_id"],
                    "reminder_id": reminder["id"],
                    "scheduled_date": today_str,
                    "scheduled_time": reminder["remind_time"],
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat(),
                }).execute()
                if result.data:
                    created_records.append(result.data[0])
            except Exception as e:
                print(f"Failed to create record: {e}")

        return created_records

    async def get_today_pending(self, user_id: str) -> list:
        """获取今日待服药列表"""
        await self.generate_today_records(user_id)

        today_str = date.today().strftime("%Y-%m-%d")
        try:
            records = table("medication_records").select("*").eq("user_id", user_id).eq("scheduled_date", today_str).order("scheduled_time").execute()
        except:
            return []

        enriched = []
        for rec in (records.data or []):
            med = None
            try:
                med_result = table("medicines").select("*").eq("id", rec["medicine_id"]).execute()
                if med_result.data:
                    med = med_result.data[0]
            except:
                pass

            dosage = ""
            if rec.get("reminder_id"):
                try:
                    rem_result = table("reminders").select("dosage").eq("id", rec["reminder_id"]).execute()
                    if rem_result.data:
                        dosage = rem_result.data[0].get("dosage", "")
                except:
                    pass

            enriched.append({
                "record": rec,
                "medicine": med,
                "dosage": dosage,
                "is_overdue": self._is_overdue(rec["scheduled_time"]),
            })

        return enriched

    def _is_overdue(self, scheduled_time: str) -> bool:
        now = datetime.now()
        try:
            h, m = map(int, scheduled_time.split(":"))
            scheduled = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return now > scheduled
        except:
            return False


notification_service = NotificationService()
