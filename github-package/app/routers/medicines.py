"""药品管理 API - 对接 Supabase"""
import os
import uuid
import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from pydantic import BaseModel

from ..auth import require_user
from ..config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE
from ..supabase_client import table, storage
from ..services.ocr_service import ocr_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/medicines", tags=["medicines"])


class MedicineCreate(BaseModel):
    name: str
    specification: str = ""
    expiry_date: str = ""
    description: str = ""
    image_path: str = ""


class MedicineUpdate(BaseModel):
    name: str = None
    specification: str = None
    expiry_date: str = None
    description: str = None


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _check_expiry(expiry_str: str) -> bool:
    if not expiry_str:
        return False
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return expiry <= (date.today() + timedelta(days=30))
    except ValueError:
        return False


def _to_medicine_dict(row: dict) -> dict:
    return {
        "id": row.get("id", ""),
        "user_id": row.get("user_id", ""),
        "name": row.get("name", ""),
        "specification": row.get("specification", ""),
        "expiry_date": row.get("expiry_date", ""),
        "description": row.get("description", ""),
        "image_path": row.get("image_path", ""),
        "created_at": row.get("created_at", ""),
        "updated_at": row.get("updated_at", ""),
        "is_expiring_soon": _check_expiry(row.get("expiry_date", "")),
    }


@router.post("/upload-recognize")
async def upload_and_recognize(request: Request, file: UploadFile = File(...)):
    """上传药品图片并进行AI识别"""
    user_id = await require_user(request)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过10MB")

    # 保存到本地临时目录
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    local_path = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(local_path, "wb") as f:
        f.write(content)

    # AI 识别
    try:
        result = await ocr_service.recognize(local_path)
    except Exception as e:
        # 识别失败也清理临时文件
        try:
            os.unlink(local_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")

    # 上传图片到 Supabase Storage
    image_path = ""
    try:
        object_name = f"{user_id}/{filename}"
        storage().from_("medicines").upload(
            path=object_name,
            file=content,
            file_options={"content-type": f"image/{'jpeg' if ext == 'jpg' else ext}"}
        )
        image_path = storage().from_("medicines").get_public_url(object_name)
    except Exception as e:
        logger.warning(f"Supabase upload failed: {e}")

    # 清理临时图片
    try:
        os.unlink(local_path)
    except OSError:
        pass

    return {
        "name": result.get("name", ""),
        "specification": result.get("specification", ""),
        "expiry_date": result.get("expiry_date", ""),
        "description": result.get("description", ""),
        "raw_text": result.get("raw_text", ""),
        "image_path": image_path,
    }


@router.post("/upload-image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    """上传图片到 Supabase Storage 并返回 URL"""
    user_id = await require_user(request)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请选择文件")

    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "jpg"
    object_name = f"{user_id}/{uuid.uuid4().hex}.{ext}"
    content = await file.read()

    try:
        # 上传到 Supabase Storage
        result = storage().from_("medicines").upload(
            path=object_name,
            file=content,
            file_options={"content-type": f"image/{'jpeg' if ext == 'jpg' else ext}"}
        )
        # 获取公开 URL
        public_url = storage().from_("medicines").get_public_url(object_name)
        return {"image_path": public_url, "object_name": object_name}
    except Exception as e:
        # 回退到本地存储
        local_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.{ext}")
        with open(local_path, "wb") as f:
            f.write(content)
        return {"image_path": f"/uploads/medicines/{os.path.basename(local_path)}"}


@router.post("")
async def add_medicine(request: Request, data: MedicineCreate):
    """确认并新增药品"""
    user_id = await require_user(request)

    if not data.name.strip():
        raise HTTPException(status_code=400, detail="药品名称不能为空")

    try:
        result = table("medicines").insert({
            "user_id": user_id,
            "name": data.name.strip(),
            "specification": data.specification.strip(),
            "expiry_date": data.expiry_date.strip(),
            "description": data.description.strip(),
            "image_path": data.image_path.strip(),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()

        if result.data:
            return _to_medicine_dict(result.data[0])
        raise Exception("Insert returned no data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加药品失败: {str(e)}")


@router.get("")
async def list_medicines(request: Request):
    """获取药品列表"""
    user_id = await require_user(request)

    try:
        result = table("medicines").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
        medicines = [_to_medicine_dict(row) for row in (result.data or [])]
        return medicines
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取药品列表失败: {str(e)}")


@router.get("/{medicine_id}")
async def get_medicine(request: Request, medicine_id: str):
    """获取药品详情"""
    user_id = await require_user(request)

    try:
        result = table("medicines").select("*").eq("id", medicine_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="药品不存在")
        return _to_medicine_dict(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取药品失败: {str(e)}")


@router.put("/{medicine_id}")
async def update_medicine(request: Request, medicine_id: str, data: MedicineUpdate):
    """更新药品信息"""
    user_id = await require_user(request)

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    update_data["updated_at"] = datetime.utcnow().isoformat()

    try:
        result = table("medicines").update(update_data).eq("id", medicine_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="药品不存在")
        return _to_medicine_dict(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新药品失败: {str(e)}")


@router.delete("/{medicine_id}")
async def delete_medicine(request: Request, medicine_id: str):
    """删除药品"""
    user_id = await require_user(request)

    try:
        result = table("medicines").delete().eq("id", medicine_id).eq("user_id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="药品不存在")
        return {"message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除药品失败: {str(e)}")
