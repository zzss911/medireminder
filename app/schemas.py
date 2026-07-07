"""Pydantic Schemas"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ========== Auth ==========
class UserRegister(BaseModel):
    email: str
    password: str
    name: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ========== Medicine ==========
class MedicineCreate(BaseModel):
    name: str
    specification: str = ""
    expiry_date: str = ""
    description: str = ""
    image_path: str = ""


class MedicineUpdate(BaseModel):
    name: Optional[str] = None
    specification: Optional[str] = None
    expiry_date: Optional[str] = None
    description: Optional[str] = None


class MedicineResponse(BaseModel):
    id: str
    user_id: str
    name: str
    specification: str
    expiry_date: str
    description: str
    image_path: str
    created_at: datetime
    updated_at: datetime
    is_expiring_soon: bool = False  # 是否即将过期（30天内）

    class Config:
        from_attributes = True


class OCRResult(BaseModel):
    name: str
    specification: str
    expiry_date: str
    description: str
    raw_text: str


# ========== Reminder ==========
class ReminderCreate(BaseModel):
    medicine_id: str
    remind_time: str          # "08:30"
    frequency: str = "daily"  # daily/weekly/custom
    dosage: str = "1片"
    days_of_week: str = ""    # "1,3,5"


class ReminderUpdate(BaseModel):
    remind_time: Optional[str] = None
    frequency: Optional[str] = None
    dosage: Optional[str] = None
    days_of_week: Optional[str] = None
    is_active: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: str
    user_id: str
    medicine_id: str
    remind_time: str
    frequency: str
    dosage: str
    days_of_week: str
    is_active: bool
    created_at: datetime
    medicine_name: str = ""
    medicine_spec: str = ""

    class Config:
        from_attributes = True


# ========== Record ==========
class RecordCreate(BaseModel):
    medicine_id: str
    reminder_id: Optional[str] = None
    scheduled_date: str
    scheduled_time: str
    status: str = "pending"  # taken/delayed/skipped/pending
    actual_time: str = ""
    note: str = ""


class RecordUpdate(BaseModel):
    status: str               # taken/delayed/skipped
    actual_time: Optional[str] = None
    note: Optional[str] = None


class RecordResponse(BaseModel):
    id: str
    user_id: str
    medicine_id: str
    reminder_id: Optional[str] = None
    scheduled_date: str
    scheduled_time: str
    status: str
    actual_time: str
    note: str
    created_at: datetime
    medicine_name: str = ""
    medicine_spec: str = ""

    class Config:
        from_attributes = True


class TodayMedication(BaseModel):
    record: RecordResponse
    medicine: MedicineResponse
    reminder: Optional[ReminderResponse] = None


# ========== Dashboard ==========
class DashboardData(BaseModel):
    total_medicines: int
    active_reminders: int
    today_pending: int
    today_taken: int
    today_medications: list
    expiring_medicines: list
