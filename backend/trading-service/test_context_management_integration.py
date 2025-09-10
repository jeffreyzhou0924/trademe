#!/usr/bin/env python3
"""
上下文管理服务集成测试脚本
测试所有4个上下文管理服务的协同工作效果
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any
import os
import sys

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.database import AsyncSessionLocal
from app.services.simplified_ai_service import UnifiedProxyAIService
from app.services.dynamic_context_manager import DynamicContextManager
from app.services.context_summarizer_service import ContextSummarizerService
from app.services.session_recovery_service import SessionRecoveryService
from app.services.cross_session_knowledge_accumulator import CrossSessionKnowledgeAccumulator


class ContextManagementIntegrationTest:
    """上下文管理服务集成测试"""
    
    def __init__(self):
        self.ai_service = UnifiedProxyAIService()
        self.dynamic_context_manager = DynamicContextManager()
        self.context_summarizer = ContextSummarizerService()
        self.session_recovery = SessionRecoveryService()
        self.knowledge_accumulator = CrossSessionKnowledgeAccumulator()
        
    async def test_full_context_ecosystem(self) -> Dict[str, Any]:
        """测试完整的上下文管理生态系统"""
        print("🧪 开始上下文管理生态系统集成测试")
        
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_success": False
        }
        
        async with AsyncSessionLocal() as db:
            test_user_id = 9  # 使用publictest用户
            test_session_id = str(uuid.uuid4())
            
            try:
                # 1. 测试动态上下文管理器
                print("\n1️⃣ 测试动态上下文管理器")
                context_result = await self._test_dynamic_context_manager(
                    db, test_user_id, test_session_id
                )
                test_results["tests"]["dynamic_context"] = context_result
                
                # 2. 测试上下文摘要服务
                print("\n2️⃣ 测试上下文摘要服务")
                summary_result = await self._test_context_summarizer(
                    db, test_user_id, test_session_id
                )
                test_results["tests"]["context_summarizer"] = summary_result
                
                # 3. 测试会话恢复服务
                print("\n3️⃣ 测试会话恢复服务")
                recovery_result = await self._test_session_recovery(
                    db, test_user_id
                )
                test_results["tests"]["session_recovery"] = recovery_result
                
                # 4. 测试跨会话知识积累
                print("\n4️⃣ 测试跨会话知识积累")
                knowledge_result = await self._test_knowledge_accumulator(
                    db, test_user_id
                )
                test_results["tests"]["knowledge_accumulator"] = knowledge_result
                
                # 5. 测试完整集成的AI对话
                print("\n5️⃣ 测试完整集成的AI对话")
                integration_result = await self._test_full_ai_integration(
                    db, test_user_id, test_session_id
                )
                test_results["tests"]["full_integration"] = integration_result
                
                # 计算总体成功率
                success_count = sum(1 for test in test_results["tests"].values() if test.get("success", False))
                total_tests = len(test_results["tests"])
                success_rate = success_count / total_tests
                
                test_results["overall_success"] = success_rate >= 0.8  # 80%成功率
                test_results["success_rate"] = success_rate
                test_results["passed_tests"] = success_count
                test_results["total_tests"] = total_tests
                
                print(f"\n🎯 测试完成: {success_count}/{total_tests} 通过 (成功率: {success_rate:.2%})")
                
            except Exception as e:
                print(f"❌ 集成测试失败: {e}")
                test_results["error"] = str(e)
                
        return test_results
    
    async def _test_dynamic_context_manager(self, db, user_id: int, session_id: str) -> Dict[str, Any]:
        """测试动态上下文管理器"""
        try:
            # 测试最优上下文窗口计算（包含内部的重要性评分）
            test_message = "请帮我创建一个MACD策略，参数设置为快线12，慢线26，信号线9"
            context_config = await self.dynamic_context_manager.calculate_optimal_context_window(
                db, user_id, session_id, test_message
            )
            print(f"  ✅ 最优窗口大小: {context_config['optimal_window_size']}")
            print(f"  ✅ 上下文策略: {context_config['context_strategy']}")
            
            # 测试优化上下文获取
            optimized_context = await self.dynamic_context_manager.get_optimized_context(
                db, user_id, session_id, test_message
            )
            print(f"  ✅ 优化上下文条目: {len(optimized_context)}")
            
            return {
                "success": True,
                "window_size": context_config['optimal_window_size'],
                "strategy": context_config['context_strategy'],
                "context_entries": len(optimized_context)
            }
            
        except Exception as e:
            print(f"  ❌ 动态上下文管理器测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_context_summarizer(self, db, user_id: int, session_id: str) -> Dict[str, Any]:
        """测试上下文摘要服务"""
        try:
            # 测试上下文健康度维护
            health_result = await self.context_summarizer.maintain_context_health(
                db, user_id, session_id
            )
            print(f"  ✅ 上下文健康度维护: {health_result}")
            
            # 测试摘要生成能力（使用正确的方法签名）
            summary = await self.context_summarizer.generate_context_summary(
                db, user_id, session_id
            )
            
            if summary:
                print(f"  ✅ 生成摘要: {summary[:100]}...")
                summary_generated = True
            else:
                print("  ℹ️ 无需生成摘要（对话数量不足）")
                summary_generated = False
            
            return {
                "success": True,
                "health_maintained": health_result is not None,
                "summary_generated": summary_generated
            }
            
        except Exception as e:
            print(f"  ❌ 上下文摘要服务测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_session_recovery(self, db, user_id: int) -> Dict[str, Any]:
        """测试会话恢复服务"""
        try:
            # 检测中断会话
            interrupted_sessions = await self.session_recovery.detect_interrupted_sessions(
                db, user_id
            )
            print(f"  ✅ 检测到中断会话: {len(interrupted_sessions)}个")
            
            # 如果有中断会话，尝试恢复第一个（使用正确的参数名）
            recovery_success = False
            if interrupted_sessions:
                recovery_result = await self.session_recovery.recover_session(
                    db, user_id, interrupted_sessions[0]["session_id"], recovery_strategy="auto"
                )
                recovery_success = recovery_result["success"]
                print(f"  ✅ 会话恢复: {recovery_success}")
                print(f"  ✅ 恢复方法: {recovery_result.get('recovery_method', 'unknown')}")
            else:
                print("  ✅ 无需恢复会话")
                recovery_success = True
            
            return {
                "success": True,
                "interrupted_sessions": len(interrupted_sessions),
                "recovery_success": recovery_success
            }
            
        except Exception as e:
            print(f"  ❌ 会话恢复服务测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_knowledge_accumulator(self, db, user_id: int) -> Dict[str, Any]:
        """测试跨会话知识积累"""
        try:
            # 分析用户学习模式
            learning_patterns = await self.knowledge_accumulator.analyze_user_learning_patterns(
                db, user_id
            )
            print(f"  ✅ 学习模式分析: {learning_patterns.get('analysis_summary', '完成')}")
            
            # 获取个性化上下文增强
            test_message = "测试消息用于上下文增强"
            context_enhancement = await self.knowledge_accumulator.get_personalized_context_enhancement(
                db, user_id, "strategy", test_message  # session_type, current_message
            )
            print(f"  ✅ 上下文增强: {len(context_enhancement.get('recommendations', []))}条建议")
            
            # 评估用户专业度（通过分析结果）
            expertise_level = learning_patterns.get('user_profile', {}).get('expertise_level', 'unknown')
            technical_interests = learning_patterns.get('user_profile', {}).get('technical_interests', [])
            
            print(f"  ✅ 专业度评估: {expertise_level}")
            print(f"  ✅ 技术兴趣: {len(technical_interests)}项")
            
            return {
                "success": True,
                "expertise_level": expertise_level,
                "technical_interests": len(technical_interests),
                "learning_analysis": "completed",
                "context_recommendations": len(context_enhancement.get('recommendations', []))
            }
            
        except Exception as e:
            print(f"  ❌ 跨会话知识积累测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_full_ai_integration(self, db, user_id: int, session_id: str) -> Dict[str, Any]:
        """测试完整集成的AI对话"""
        try:
            # 使用集成了所有上下文管理服务的AI对话方法
            test_message = "我想创建一个基于RSI指标的交易策略，当RSI小于30时买入，大于70时卖出"
            
            # 注意：这里不会实际调用Claude API，只测试上下文管理集成
            response = await self.ai_service.chat_completion_with_context(
                message=test_message,
                user_id=user_id,
                session_id=session_id,
                ai_mode="developer",
                db=db,
                stream=False
            )
            
            # 验证响应包含上下文信息
            context_info = response.get("context_info", {})
            print(f"  ✅ 上下文窗口: {context_info.get('window_size', 'N/A')}")
            print(f"  ✅ 上下文策略: {context_info.get('strategy', 'N/A')}")
            print(f"  ✅ 用户专业度: {context_info.get('user_expertise', 'N/A')}")
            print(f"  ✅ 恢复会话数: {context_info.get('recovered_sessions', 0)}")
            
            return {
                "success": True,
                "response_received": True,
                "context_enhanced": len(context_info) > 0,
                "window_size": context_info.get('window_size'),
                "user_expertise": context_info.get('user_expertise')
            }
            
        except Exception as e:
            print(f"  ❌ 完整AI集成测试失败: {e}")
            return {"success": False, "error": str(e)}


async def main():
    """主测试函数"""
    print("🚀 启动上下文管理服务集成测试")
    print("=" * 60)
    
    tester = ContextManagementIntegrationTest()
    results = await tester.test_full_context_ecosystem()
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    if results["overall_success"]:
        print(f"✅ 集成测试成功! 成功率: {results['success_rate']:.2%}")
    else:
        print(f"❌ 集成测试失败! 成功率: {results['success_rate']:.2%}")
    
    print(f"\n通过测试: {results['passed_tests']}/{results['total_tests']}")
    
    print("\n详细结果:")
    for test_name, test_result in results["tests"].items():
        status = "✅" if test_result.get("success", False) else "❌"
        print(f"  {status} {test_name}: {test_result.get('error', 'OK')}")
    
    # 保存测试结果
    with open("/root/trademe/backend/trading-service/context_integration_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 测试结果已保存到: context_integration_test_results.json")


if __name__ == "__main__":
    # 设置数据库环境
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////root/trademe/data/trademe.db"
    
    # 运行测试
    asyncio.run(main())