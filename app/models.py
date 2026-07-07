"""数据模型"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum

from .database import Base


def generate_uuid():
    return str(uuid.uuid4())


class ReminderFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class RecordStatus(str, enum.Enum):
    PENDING = "pending"
    TAKEN = "taken"
    DELAYED = "delayed"
    SKIPPED = "skipped"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    medicines = relationship("Medicine", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    records = relationship("MedicationRecord", back_populates="user", cascade="all, delete-orphan")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    specification = Column(String(255), default="")      # 规格，如 "10mg*30片"
    expiry_date = Column(String(20), default="")         # 有效期，如 "2026-12-31"
    description = Column(Text, default="")               # 说明文字
    image_path = Column(String(500), default="")         # 药品图片路径
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="medicines")
    reminders = relationship("Reminder", back_populates="medicine", cascade="all, delete-orphan")
    records = relationship("MedicationRecord", back_populates="medicine", cascade="all, delete-orphan")


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    medicine_id = Column(String(36), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)
    remind_time = Column(String(10), nullable=False)          # "08:30" 格式
    frequency = Column(String(20), default=ReminderFrequency.DAILY.value)
    dosage = Column(String(100), default="")                   # 用量，如 "1片"
    days_of_week = Column(String(50), default="")              # 周几服药，如 "1,3,5" (周一周三周五)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="reminders")
    medicine = relationship("Medicine", back_populates="reminders")
    records = relationship("MedicationRecord", back_populates="reminder", cascade="all, delete-orphan")


class MedicationRecord(Base):
    __tablename__ = "medication_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    medicine_id = Column(String(36), ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)
    reminder_id = Column(String(36), ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True)
    scheduled_date = Column(String(10), nullable=False)       # "2026-07-06"
    scheduled_time = Column(String(10), nullable=False)        # "08:30"
    status = Column(String(20), default=RecordStatus.PENDING.value)
    actual_time = Column(String(10), default="")               # 实际服药时间
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="records")
    medicine = relationship("Medicine", back_populates="records")
    reminder = relationship("Reminder", back_populates="records")


class PushSubscription(Base):
    """Web Push 订阅信息"""
    __tablename__ = "push_subscriptions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    user_agent = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)


class UserSetting(Base):
    """用户设置"""
    __tablename__ = "user_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    ai_provider = Column(String(50), default="easyocr")    # easyocr / claude / openai
    ai_api_key = Column(String(500), default="")
    ai_api_url = Column(String(500), default="")
    push_enabled = Column(Boolean, default=True)
    expiry_warn_days = Column(Integer, default=30)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
