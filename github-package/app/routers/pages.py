"""页面路由 - 服务端渲染（对接 Supabase）"""
from datetime import date, timedelta, datetime

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..auth import get_optional_user, require_user
from ..supabase_client import table
from ..templates import render

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/")
    return render("login.html", {"request": request})


@router.get("/register")
async def register_page(request: Request):
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/")
    return render("register.html", {"request": request})


@router.get("/")
async def dashboard(request: Request):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")

    user_id = user["id"]
    user_name = user["name"]

    # 获取今日待服药
    from ..services.notification_service import notification_service
    today_items = await notification_service.get_today_pending(user_id)

    pending_count = 0
    taken_count = 0
    today_medications = []
    for item in today_items:
        rec = item["record"]
        med = item["medicine"]
        dosage = item.get("dosage", "")
        today_medications.append({
            "id": rec["id"],
            "medicine_name": med["name"] if med else "未知药品",
            "medicine_spec": med["specification"] if med else "",
            "medicine_id": rec["medicine_id"],
            "scheduled_time": rec["scheduled_time"],
            "status": rec["status"],
            "dosage": dosage,
            "is_overdue": item.get("is_overdue", False),
        })
        if rec["status"] == "pending":
            pending_count += 1
        elif rec["status"] == "taken":
            taken_count += 1

    # 药品总数
    try:
        med_result = table("medicines").select("id", count="exact").eq("user_id", user_id).execute()
        total_medicines = med_result.count or 0
    except:
        total_medicines = 0

    # 活跃提醒数
    try:
        rem_result = table("reminders").select("id", count="exact").eq("user_id", user_id).eq("is_active", True).execute()
        active_reminders = rem_result.count or 0
    except:
        active_reminders = 0

    # 即将过期
    try:
        meds = table("medicines").select("name,expiry_date").eq("user_id", user_id).execute()
        today_date = date.today()
        warn_date = today_date + timedelta(days=30)
        expiring = []
        for m in (meds.data or []):
            expiry_str = m.get("expiry_date", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                if expiry <= warn_date:
                    days_left = (expiry - today_date).days
                    expiring.append({
                        "name": m["name"],
                        "expiry_date": expiry_str,
                        "days_left": days_left,
                        "expired": days_left < 0,
                    })
            except ValueError:
                continue
    except:
        expiring = []

    return render("dashboard.html", {
        "request": request,
        "user_name": user_name,
        "total_medicines": total_medicines,
        "active_reminders": active_reminders,
        "pending_count": pending_count,
        "taken_count": taken_count,
        "today_medications": today_medications,
        "expiring": expiring,
    })


@router.get("/medicines")
async def medicines_page(request: Request):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")

    try:
        result = table("medicines").select("*").eq("user_id", user["id"]).order("updated_at", desc=True).execute()
        today_date = date.today()
        warn_date = today_date + timedelta(days=30)
        med_list = []
        for m in (result.data or []):
            is_expiring = False
            days_left = None
            expiry_str = m.get("expiry_date", "")
            if expiry_str:
                try:
                    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                    if expiry <= warn_date:
                        is_expiring = True
                        days_left = (expiry - today_date).days
                except ValueError:
                    pass
            med_list.append({
                "id": m["id"],
                "name": m["name"],
                "specification": m.get("specification", ""),
                "expiry_date": expiry_str,
                "description": m.get("description", ""),
                "image_path": m.get("image_path", ""),
                "is_expiring": is_expiring,
                "days_left": days_left,
            })
        return render("medicines.html", {"request": request, "medicines": med_list})
    except Exception as e:
        return render("medicines.html", {"request": request, "medicines": []})


@router.get("/medicines/add")
async def add_medicine_page(request: Request):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return render("add_medicine.html", {"request": request})


@router.get("/medicines/{medicine_id}")
async def medicine_detail_page(request: Request, medicine_id: str):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")

    try:
        med_result = table("medicines").select("*").eq("id", medicine_id).eq("user_id", user["id"]).execute()
        if not med_result.data:
            return render("404.html", {"request": request})

        m = med_result.data[0]
        rem_result = table("reminders").select("*").eq("medicine_id", medicine_id).execute()
        rem_list = []
        for r in (rem_result.data or []):
            rem_list.append({
                "id": r["id"],
                "remind_time": r["remind_time"],
                "frequency": r["frequency"],
                "dosage": r.get("dosage", ""),
                "days_of_week": r.get("days_of_week", ""),
                "is_active": r["is_active"],
            })

        return render("medicine_detail.html", {
            "request": request,
            "medicine": {
                "id": m["id"],
                "name": m["name"],
                "specification": m.get("specification", ""),
                "expiry_date": m.get("expiry_date", ""),
                "description": m.get("description", ""),
                "image_path": m.get("image_path", ""),
            },
            "reminders": rem_list,
        })
    except Exception as e:
        return render("404.html", {"request": request})


@router.get("/history")
async def history_page(request: Request):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return render("history.html", {"request": request})


@router.get("/settings")
async def settings_page(request: Request):
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login")

    try:
        result = table("user_settings").select("expiry_warn_days,push_enabled").eq("user_id", user["id"]).execute()
        if result.data:
            row = result.data[0]
            expiry_warn_days = row.get("expiry_warn_days", 30)
            push_enabled = row.get("push_enabled", True)
        else:
            expiry_warn_days = 30
            push_enabled = True
    except:
        expiry_warn_days = 30
        push_enabled = True

    return render("settings.html", {
        "request": request,
        "expiry_warn_days": expiry_warn_days,
        "push_enabled": push_enabled,
    })
