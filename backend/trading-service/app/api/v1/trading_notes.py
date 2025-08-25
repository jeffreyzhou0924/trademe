"""
交易心得API端点
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import Optional, List
import json
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.trading_note import TradingNote, TradingNoteLike, TradingNoteComment, NoteCategory
from app.schemas.trading_note import (
    TradingNoteCreate, TradingNoteUpdate, TradingNoteResponse, 
    TradingNoteListResponse, TradingNoteFilters, TradingNoteStats,
    CommentCreate, CommentResponse
)
from loguru import logger

router = APIRouter(prefix="/trading-notes", tags=["交易心得"])


@router.get("/", response_model=TradingNoteListResponse)
async def get_trading_notes(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[NoteCategory] = Query(None, description="分类筛选"),
    symbol: Optional[str] = Query(None, description="交易对筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    tags: Optional[str] = Query(None, description="标签，逗号分隔"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易心得列表"""
    try:
        # 构建查询条件
        conditions = [TradingNote.user_id == current_user.id]
        
        if category:
            conditions.append(TradingNote.category == category)
        
        if symbol:
            conditions.append(TradingNote.symbol.ilike(f"%{symbol}%"))
        
        if search:
            search_condition = or_(
                TradingNote.title.ilike(f"%{search}%"),
                TradingNote.content.ilike(f"%{search}%")
            )
            conditions.append(search_condition)
        
        if start_date:
            conditions.append(TradingNote.created_at >= start_date)
        
        if end_date:
            conditions.append(TradingNote.created_at <= end_date)
        
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            for tag in tag_list:
                conditions.append(TradingNote.tags.ilike(f"%{tag}%"))
        
        # 计算总数
        count_query = select(func.count(TradingNote.id)).where(and_(*conditions))
        count_result = await db.execute(count_query)
        total = count_result.scalar()
        
        # 分页查询
        offset = (page - 1) * page_size
        query = (
            select(TradingNote)
            .where(and_(*conditions))
            .order_by(desc(TradingNote.created_at))
            .offset(offset)
            .limit(page_size)
        )
        
        result = await db.execute(query)
        notes = result.scalars().all()
        
        # 转换为响应模型
        note_responses = []
        for note in notes:
            tags_list = []
            if note.tags:
                try:
                    tags_list = json.loads(note.tags)
                except:
                    tags_list = []
            
            # 检查当前用户是否点赞
            like_query = select(TradingNoteLike).where(
                and_(
                    TradingNoteLike.note_id == note.id,
                    TradingNoteLike.user_id == current_user.id
                )
            )
            like_result = await db.execute(like_query)
            is_liked = like_result.scalar() is not None
            
            note_response = TradingNoteResponse(
                id=note.id,
                title=note.title,
                content=note.content,
                category=note.category,
                symbol=note.symbol,
                entry_price=note.entry_price,
                exit_price=note.exit_price,
                stop_loss=note.stop_loss,
                take_profit=note.take_profit,
                position_size=note.position_size,
                result=note.result,
                tags=tags_list,
                likes_count=note.likes_count,
                comments_count=note.comments_count,
                is_public=note.is_public,
                is_liked=is_liked,
                created_at=note.created_at,
                updated_at=note.updated_at
            )
            note_responses.append(note_response)
        
        total_pages = (total + page_size - 1) // page_size
        
        return TradingNoteListResponse(
            notes=note_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"获取交易心得列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取交易心得列表失败")


@router.post("/", response_model=TradingNoteResponse)
async def create_trading_note(
    note_data: TradingNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建交易心得"""
    try:
        # 转换标签为JSON字符串
        tags_json = json.dumps(note_data.tags) if note_data.tags else None
        
        # 创建心得记录
        new_note = TradingNote(
            user_id=current_user.id,
            title=note_data.title,
            content=note_data.content,
            category=note_data.category,
            symbol=note_data.symbol,
            entry_price=note_data.entry_price,
            exit_price=note_data.exit_price,
            stop_loss=note_data.stop_loss,
            take_profit=note_data.take_profit,
            position_size=note_data.position_size,
            result=note_data.result,
            tags=tags_json,
            is_public=note_data.is_public
        )
        
        db.add(new_note)
        await db.commit()
        await db.refresh(new_note)
        
        logger.info(f"用户 {current_user.id} 创建了交易心得: {new_note.title}")
        
        return TradingNoteResponse(
            id=new_note.id,
            title=new_note.title,
            content=new_note.content,
            category=new_note.category,
            symbol=new_note.symbol,
            entry_price=new_note.entry_price,
            exit_price=new_note.exit_price,
            stop_loss=new_note.stop_loss,
            take_profit=new_note.take_profit,
            position_size=new_note.position_size,
            result=new_note.result,
            tags=note_data.tags or [],
            likes_count=0,
            comments_count=0,
            is_public=new_note.is_public,
            is_liked=False,
            created_at=new_note.created_at,
            updated_at=new_note.updated_at
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(f"创建交易心得失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建交易心得失败")


@router.get("/{note_id}", response_model=TradingNoteResponse)
async def get_trading_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个交易心得详情"""
    try:
        query = select(TradingNote).where(
            and_(
                TradingNote.id == note_id,
                TradingNote.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        note = result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="交易心得不存在")
        
        # 解析标签
        tags_list = []
        if note.tags:
            try:
                tags_list = json.loads(note.tags)
            except:
                tags_list = []
        
        # 检查是否点赞
        like_query = select(TradingNoteLike).where(
            and_(
                TradingNoteLike.note_id == note.id,
                TradingNoteLike.user_id == current_user.id
            )
        )
        like_result = await db.execute(like_query)
        is_liked = like_result.scalar() is not None
        
        return TradingNoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            category=note.category,
            symbol=note.symbol,
            entry_price=note.entry_price,
            exit_price=note.exit_price,
            stop_loss=note.stop_loss,
            take_profit=note.take_profit,
            position_size=note.position_size,
            result=note.result,
            tags=tags_list,
            likes_count=note.likes_count,
            comments_count=note.comments_count,
            is_public=note.is_public,
            is_liked=is_liked,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易心得详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取交易心得详情失败")


@router.put("/{note_id}", response_model=TradingNoteResponse)
async def update_trading_note(
    note_id: int,
    note_data: TradingNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新交易心得"""
    try:
        # 查找心得记录
        query = select(TradingNote).where(
            and_(
                TradingNote.id == note_id,
                TradingNote.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        note = result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="交易心得不存在")
        
        # 更新字段
        update_data = note_data.model_dump(exclude_unset=True)
        
        if "tags" in update_data:
            update_data["tags"] = json.dumps(update_data["tags"])
        
        for field, value in update_data.items():
            setattr(note, field, value)
        
        note.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(note)
        
        logger.info(f"用户 {current_user.id} 更新了交易心得 {note_id}")
        
        # 返回更新后的数据
        tags_list = []
        if note.tags:
            try:
                tags_list = json.loads(note.tags)
            except:
                tags_list = []
        
        return TradingNoteResponse(
            id=note.id,
            title=note.title,
            content=note.content,
            category=note.category,
            symbol=note.symbol,
            entry_price=note.entry_price,
            exit_price=note.exit_price,
            stop_loss=note.stop_loss,
            take_profit=note.take_profit,
            position_size=note.position_size,
            result=note.result,
            tags=tags_list,
            likes_count=note.likes_count,
            comments_count=note.comments_count,
            is_public=note.is_public,
            created_at=note.created_at,
            updated_at=note.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新交易心得失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新交易心得失败")


@router.delete("/{note_id}")
async def delete_trading_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除交易心得"""
    try:
        # 查找心得记录
        query = select(TradingNote).where(
            and_(
                TradingNote.id == note_id,
                TradingNote.user_id == current_user.id
            )
        )
        result = await db.execute(query)
        note = result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="交易心得不存在")
        
        # 删除相关的点赞和评论
        await db.execute(
            select(TradingNoteLike).where(TradingNoteLike.note_id == note_id)
        )
        await db.execute(
            select(TradingNoteComment).where(TradingNoteComment.note_id == note_id)
        )
        
        # 删除心得记录
        await db.delete(note)
        await db.commit()
        
        logger.info(f"用户 {current_user.id} 删除了交易心得 {note_id}")
        
        return {"message": "交易心得删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除交易心得失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除交易心得失败")


@router.post("/{note_id}/like")
async def toggle_like(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """点赞/取消点赞"""
    try:
        # 检查心得是否存在
        note_query = select(TradingNote).where(TradingNote.id == note_id)
        note_result = await db.execute(note_query)
        note = note_result.scalar_one_or_none()
        
        if not note:
            raise HTTPException(status_code=404, detail="交易心得不存在")
        
        # 检查是否已经点赞
        like_query = select(TradingNoteLike).where(
            and_(
                TradingNoteLike.note_id == note_id,
                TradingNoteLike.user_id == current_user.id
            )
        )
        like_result = await db.execute(like_query)
        existing_like = like_result.scalar_one_or_none()
        
        if existing_like:
            # 取消点赞
            await db.delete(existing_like)
            note.likes_count = max(0, note.likes_count - 1)
            action = "取消点赞"
            is_liked = False
        else:
            # 添加点赞
            new_like = TradingNoteLike(
                note_id=note_id,
                user_id=current_user.id
            )
            db.add(new_like)
            note.likes_count += 1
            action = "点赞"
            is_liked = True
        
        await db.commit()
        
        return {
            "message": f"{action}成功",
            "likes_count": note.likes_count,
            "is_liked": is_liked
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"点赞操作失败: {str(e)}")
        raise HTTPException(status_code=500, detail="点赞操作失败")


@router.get("/stats/summary", response_model=TradingNoteStats)
async def get_trading_notes_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取交易心得统计信息"""
    try:
        # 统计总数
        total_query = select(func.count(TradingNote.id)).where(
            TradingNote.user_id == current_user.id
        )
        total_result = await db.execute(total_query)
        total_notes = total_result.scalar()
        
        # 按分类统计
        category_query = select(
            TradingNote.category,
            func.count(TradingNote.id)
        ).where(
            TradingNote.user_id == current_user.id
        ).group_by(TradingNote.category)
        
        category_result = await db.execute(category_query)
        category_stats = dict(category_result.fetchall())
        
        # 模拟存储使用情况（实际应该根据内容大小计算）
        storage_used = total_notes * 0.1  # 假设每个心得平均0.1GB
        
        # 根据会员等级确定存储限制
        if current_user.membership_level == "premium":
            storage_limit = 5.0  # 5GB
        elif current_user.membership_level == "professional":
            storage_limit = 20.0  # 20GB
        else:
            storage_limit = 1.0  # 1GB
        
        return TradingNoteStats(
            total_notes=total_notes,
            notes_by_category=category_stats,
            storage_used=storage_used,
            storage_limit=storage_limit
        )
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取统计信息失败")


@router.post("/ai-analysis")
async def analyze_trading_notes_with_ai(
    note_ids: Optional[List[int]] = Query(None, description="要分析的心得ID列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI分析交易心得"""
    try:
        # 导入AI服务
        from app.services.ai_service import AIService
        
        # 查询要分析的心得
        if note_ids and len(note_ids) > 0:
            query = select(TradingNote).where(
                and_(
                    TradingNote.user_id == current_user.id,
                    TradingNote.id.in_(note_ids)
                )
            )
        else:
            # 如果没有指定，分析最近的10个心得
            query = (
                select(TradingNote)
                .where(TradingNote.user_id == current_user.id)
                .order_by(desc(TradingNote.created_at))
                .limit(10)
            )
        
        result = await db.execute(query)
        notes = result.scalars().all()
        
        if not notes:
            raise HTTPException(status_code=404, detail="未找到要分析的交易心得")
        
        # 准备分析数据
        analysis_data = []
        for note in notes:
            tags_list = []
            if note.tags:
                try:
                    tags_list = json.loads(note.tags)
                except:
                    tags_list = []
            
            note_data = {
                "title": note.title,
                "content": note.content,
                "category": note.category,
                "symbol": note.symbol,
                "entry_price": note.entry_price,
                "exit_price": note.exit_price,
                "stop_loss": note.stop_loss,
                "take_profit": note.take_profit,
                "position_size": note.position_size,
                "result": note.result,
                "tags": tags_list,
                "created_at": note.created_at.strftime("%Y-%m-%d")
            }
            analysis_data.append(note_data)
        
        # 构建分析提示
        analysis_prompt = f"""
作为专业的交易分析师，请分析以下用户的{len(analysis_data)}条交易心得记录，并提供深入的分析和建议：

交易记录：
{json.dumps(analysis_data, ensure_ascii=False, indent=2)}

请从以下几个方面进行分析：

1. **交易模式分析**：
   - 识别用户的主要交易策略和偏好
   - 分析交易频率和时间分布
   - 评估风险偏好和仓位管理

2. **盈亏能力评估**：
   - 基于记录的交易结果，评估盈亏比
   - 分析成功交易和失败交易的特征
   - 识别可能的改进点

3. **技术分析能力**：
   - 评估用户的技术分析水平
   - 分析止损和止盈设置的合理性
   - 识别分析中的优势和不足

4. **心理和纪律性**：
   - 从记录内容判断交易心理状态
   - 评估执行纪律性
   - 识别情绪化交易的迹象

5. **改进建议**：
   - 针对性的改进建议
   - 学习重点推荐
   - 风险管理优化建议

请用中文回答，语言专业但易懂，大约800-1200字。
        """
        
        # 调用AI分析
        ai_response = await AIService.chat_completion(
            message=analysis_prompt,
            user_id=current_user.id,
            conversation_id="trading_notes_analysis",
            db=db
        )
        
        return {
            "message": "AI分析完成",
            "analyzed_notes_count": len(analysis_data),
            "analysis": ai_response,
            "analysis_type": "comprehensive_trading_analysis"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI分析交易心得失败: {str(e)}")
        raise HTTPException(status_code=500, detail="AI分析失败")