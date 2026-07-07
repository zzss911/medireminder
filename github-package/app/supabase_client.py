"""Supabase 客户端 - 统一管理数据库、认证、存储"""
import os
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from .config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)

# 全局客户端实例
_supabase: Optional[Client] = None
_admin_client: Optional[Client] = None


def get_supabase() -> Client:
    """获取 Supabase 客户端（使用 anon key，遵守 RLS）"""
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase


def get_admin_client() -> Client:
    """获取 Supabase 管理客户端（使用 service_role key，绕过 RLS）"""
    global _admin_client
    if _admin_client is None:
        key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
        _admin_client = create_client(SUPABASE_URL, key)
    return _admin_client


# ====== 简便操作函数 ======

def db():
    """获取数据库操作对象"""
    return get_admin_client()


def table(name: str):
    """获取表操作对象"""
    return db().table(name)


def storage():
    """获取存储操作对象"""
    return db().storage


# ====== 数据库 ======

async def db_execute(query_builder):
    """执行 Supabase 查询，处理同步/异步"""
    try:
        return query_builder.execute()
    except Exception as e:
        logger.error(f"DB execute error: {e}")
        raise


def db_select(table_name: str, columns: str = "*"):
    return table(table_name).select(columns)


def db_insert(table_name: str, data: dict):
    return table(table_name).insert(data)


def db_update(table_name: str, data: dict, match: dict = None):
    q = table(table_name).update(data)
    if match:
        for k, v in match.items():
            q = q.eq(k, v)
    return q


def db_delete(table_name: str, match: dict = None):
    q = table(table_name).delete()
    if match:
        for k, v in match.items():
            q = q.eq(k, v)
    return q


# ====== 数据迁移 SQL ======

CREATE_TABLES_SQL = """
-- 药品表
CREATE TABLE IF NOT EXISTS public.medicines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    specification TEXT DEFAULT '',
    expiry_date TEXT DEFAULT '',
    description TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 提醒表
CREATE TABLE IF NOT EXISTS public.reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    medicine_id UUID NOT NULL REFERENCES public.medicines(id) ON DELETE CASCADE,
    remind_time TEXT NOT NULL,
    frequency TEXT DEFAULT 'daily',
    dosage TEXT DEFAULT '',
    days_of_week TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 服药记录表
CREATE TABLE IF NOT EXISTS public.medication_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    medicine_id UUID NOT NULL REFERENCES public.medicines(id) ON DELETE CASCADE,
    reminder_id UUID REFERENCES public.reminders(id) ON DELETE SET NULL,
    scheduled_date TEXT NOT NULL,
    scheduled_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    actual_time TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 推送订阅表
CREATE TABLE IF NOT EXISTS public.push_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);

-- 用户设置表（仅面向用户的功能）
CREATE TABLE IF NOT EXISTS public.user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    push_enabled BOOLEAN DEFAULT TRUE,
    expiry_warn_days INTEGER DEFAULT 30,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS 策略：用户只能访问自己的数据
ALTER TABLE public.medicines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medication_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Users can manage own medicines" ON public.medicines
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can manage own reminders" ON public.reminders
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can manage own records" ON public.medication_records
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can manage own push subscriptions" ON public.push_subscriptions
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY IF NOT EXISTS "Users can manage own settings" ON public.user_settings
    FOR ALL USING (auth.uid() = user_id);
"""


async def run_migration():
    """执行数据库迁移（需要在 Supabase SQL Editor 中运行上述 SQL）"""
    logger.info("Note: Run the SQL in Supabase SQL Editor to create tables")
    pass
