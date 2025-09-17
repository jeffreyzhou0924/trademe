"""
Debug调试API - 用于开发时的图片上传和调试功能
"""

import os
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
from PIL import Image
import io
from loguru import logger

from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/debug", tags=["调试工具"])

# 配置上传目录
UPLOAD_DIR = Path("/root/trademe/uploads/debug")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的图片格式
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload-image")
async def upload_debug_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    上传调试图片
    用于开发过程中快速分享和讨论前端问题
    """
    try:
        # 验证文件格式
        if not image.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        file_ext = Path(image.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式。支持的格式: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 读取文件内容
        content = await image.read()

        # 验证文件大小
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"
            )

        # 验证是否为有效图片
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()  # 验证图片完整性
        except Exception:
            raise HTTPException(status_code=400, detail="无效的图片文件")

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        original_name = Path(image.filename).stem
        safe_filename = f"{timestamp}_{unique_id}_{original_name}{file_ext}"

        # 保存文件
        file_path = UPLOAD_DIR / safe_filename
        with open(file_path, "wb") as f:
            f.write(content)

        # 记录上传日志
        logger.info(f"调试图片上传成功: {safe_filename}, 用户: {current_user.email}, 大小: {len(content)} bytes")

        return {
            "success": True,
            "id": unique_id,
            "filename": safe_filename,
            "original_name": image.filename,
            "url": f"/api/v1/debug/image/{safe_filename}",
            "size": len(content),
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": current_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传调试图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/image/{filename}")
async def get_debug_image(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取调试图片
    返回保存的图片文件
    """
    try:
        file_path = UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="图片不存在")

        # 安全检查：确保文件在允许的目录内
        if not str(file_path.resolve()).startswith(str(UPLOAD_DIR.resolve())):
            raise HTTPException(status_code=403, detail="访问被拒绝")

        return FileResponse(
            path=file_path,
            media_type="image/*",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取调试图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/images")
async def list_debug_images(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    列出所有调试图片
    """
    try:
        images = []

        for file_path in UPLOAD_DIR.glob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ALLOWED_EXTENSIONS:
                stat = file_path.stat()
                images.append({
                    "filename": file_path.name,
                    "url": f"/api/v1/debug/image/{file_path.name}",
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # 按修改时间倒序排列
        images.sort(key=lambda x: x["modified_at"], reverse=True)

        return {
            "success": True,
            "images": images,
            "total": len(images)
        }

    except Exception as e:
        logger.error(f"列出调试图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.delete("/image/{filename}")
async def delete_debug_image(
    filename: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    删除调试图片
    """
    try:
        file_path = UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="图片不存在")

        # 安全检查
        if not str(file_path.resolve()).startswith(str(UPLOAD_DIR.resolve())):
            raise HTTPException(status_code=403, detail="访问被拒绝")

        file_path.unlink()

        logger.info(f"调试图片删除成功: {filename}, 用户: {current_user.email}")

        return {
            "success": True,
            "message": f"图片 {filename} 删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除调试图片失败: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/info")
async def debug_info(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取调试信息
    """
    return {
        "upload_dir": str(UPLOAD_DIR),
        "allowed_extensions": list(ALLOWED_EXTENSIONS),
        "max_file_size": MAX_FILE_SIZE,
        "max_file_size_mb": MAX_FILE_SIZE // 1024 // 1024,
        "user": current_user.email
    }