"""认证 API - 对接 Supabase Auth"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..supabase_client import get_supabase

router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserRegister(BaseModel):
    email: str
    password: str
    name: str


class UserLogin(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(data: UserRegister):
    """通过 Supabase Auth 注册"""
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {
                "data": {"name": data.name},
            }
        })

        if not result.user:
            raise HTTPException(status_code=400, detail="注册失败")

        resp_data = {
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "name": data.name,
            }
        }

        response = JSONResponse(content=resp_data)

        if result.session and result.session.access_token:
            response.set_cookie(
                key="sb-access-token",
                value=result.session.access_token,
                httponly=True,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
            )
            if result.session.refresh_token:
                response.set_cookie(
                    key="sb-refresh-token",
                    value=result.session.refresh_token,
                    httponly=True,
                    max_age=60 * 60 * 24 * 7,
                    samesite="lax",
                )

        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"注册失败: {str(e)}")


@router.post("/login")
async def login(data: UserLogin):
    """通过 Supabase Auth 登录"""
    supabase = get_supabase()
    try:
        result = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password,
        })

        if not result.user:
            raise HTTPException(status_code=401, detail="邮箱或密码错误")

        resp_data = {
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "name": result.user.user_metadata.get("name", ""),
            }
        }

        response = JSONResponse(content=resp_data)

        if result.session:
            response.set_cookie(
                key="sb-access-token",
                value=result.session.access_token,
                httponly=True,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
            )
            if result.session.refresh_token:
                response.set_cookie(
                    key="sb-refresh-token",
                    value=result.session.refresh_token,
                    httponly=True,
                    max_age=60 * 60 * 24 * 7,
                    samesite="lax",
                )

        return response
    except Exception as e:
        err_msg = str(e)
        if "Invalid login credentials" in err_msg:
            raise HTTPException(status_code=401, detail="邮箱或密码错误")
        raise HTTPException(status_code=400, detail=f"登录失败: {err_msg}")


@router.post("/logout")
async def logout():
    """退出登录"""
    resp = JSONResponse(content={"message": "已退出登录"})
    resp.delete_cookie("sb-access-token")
    resp.delete_cookie("sb-refresh-token")
    return resp


@router.get("/me")
async def get_me(request):
    """获取当前用户信息"""
    from ..auth import get_optional_user
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user
