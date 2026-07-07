"""认证工具 - 对接 Supabase Auth"""
from typing import Optional
from fastapi import Request, HTTPException

from .supabase_client import get_supabase


async def get_current_user_id(request: Request) -> Optional[str]:
    """从请求中获取当前登录用户的 ID"""
    token = request.cookies.get("sb-access-token")
    if not token:
        return None
    try:
        supabase = get_supabase()
        user = supabase.auth.get_user(token)
        if user and user.user:
            return user.user.id
    except Exception:
        pass
    return None


async def require_user(request: Request) -> str:
    """要求登录，返回 user_id"""
    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


async def get_optional_user(request: Request) -> dict:
    """获取当前用户信息（可选）"""
    token = request.cookies.get("sb-access-token")
    if not token:
        return None
    try:
        supabase = get_supabase()
        user = supabase.auth.get_user(token)
        if user and user.user:
            return {
                "id": user.user.id,
                "email": user.user.email,
                "name": user.user.user_metadata.get("name", ""),
            }
    except Exception:
        pass
    return None
