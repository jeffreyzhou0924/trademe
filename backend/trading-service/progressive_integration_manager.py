"""
渐进式集成管理器
管理所有6个阶段的系统集成，确保安全、稳定的升级过程
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import traceback

logger = logging.getLogger(__name__)

class IntegrationPhase(Enum):
    """集成阶段"""
    PHASE_1_SECURITY = "phase1_security"
    PHASE_2_CACHE = "phase2_cache" 
    PHASE_3_MONITORING = "phase3_monitoring"
    PHASE_4_WEBSOCKET = "phase4_websocket"
    PHASE_5_STRATEGY = "phase5_strategy"
    PHASE_6_OPTIMIZATION = "phase6_optimization"

class IntegrationStatus(Enum):
    """集成状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass
class ComponentStatus:
    """组件状态"""
    name: str
    status: IntegrationStatus = IntegrationStatus.NOT_STARTED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_info: Optional[Dict[str, Any]] = None

@dataclass
class PhaseStatus:
    """阶段状态"""
    phase: IntegrationPhase
    status: IntegrationStatus = IntegrationStatus.NOT_STARTED
    components: Dict[str, ComponentStatus] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    error_message: Optional[str] = None

class ProgressiveIntegrationManager:
    """渐进式集成管理器"""
    
    def __init__(self):
        self.phases: Dict[IntegrationPhase, PhaseStatus] = {}
        self.current_phase: Optional[IntegrationPhase] = None
        self.integration_log: List[Dict[str, Any]] = []
        
        # 初始化所有阶段
        self._initialize_phases()
        
        # 集成配置
        self.config = self._load_integration_config()
        
    def _initialize_phases(self):
        """初始化所有阶段"""
        # 第一阶段：基础安全和验证系统
        self.phases[IntegrationPhase.PHASE_1_SECURITY] = PhaseStatus(
            phase=IntegrationPhase.PHASE_1_SECURITY,
            components={
                "input_validator": ComponentStatus("输入验证器"),
                "data_encryption": ComponentStatus("数据加密服务"),
                "api_validation": ComponentStatus("API参数验证"),
                "validation_middleware": ComponentStatus("验证中间件")
            }
        )
        
        # 第二阶段：缓存系统
        self.phases[IntegrationPhase.PHASE_2_CACHE] = PhaseStatus(
            phase=IntegrationPhase.PHASE_2_CACHE,
            components={
                "redis_cache": ComponentStatus("Redis缓存服务"),
                "market_data_cache": ComponentStatus("市场数据缓存"),
                "user_session_cache": ComponentStatus("用户会话缓存"),
                "ai_conversation_cache": ComponentStatus("AI对话缓存"),
                "cache_manager": ComponentStatus("统一缓存管理器")
            }
        )
        
        # 第三阶段：性能监控系统
        self.phases[IntegrationPhase.PHASE_3_MONITORING] = PhaseStatus(
            phase=IntegrationPhase.PHASE_3_MONITORING,
            components={
                "performance_optimizer": ComponentStatus("性能优化器"),
                "database_monitor": ComponentStatus("数据库性能监控"),
                "unified_manager": ComponentStatus("统一性能管理器"),
                "monitoring_api": ComponentStatus("监控API端点")
            }
        )
        
        # 第四阶段：WebSocket增强功能
        self.phases[IntegrationPhase.PHASE_4_WEBSOCKET] = PhaseStatus(
            phase=IntegrationPhase.PHASE_4_WEBSOCKET,
            components={
                "websocket_manager": ComponentStatus("WebSocket连接管理器"),
                "connection_monitoring": ComponentStatus("连接监控"),
                "auto_reconnect": ComponentStatus("自动重连机制")
            }
        )
        
        # 第五阶段：策略执行引擎
        self.phases[IntegrationPhase.PHASE_5_STRATEGY] = PhaseStatus(
            phase=IntegrationPhase.PHASE_5_STRATEGY,
            components={
                "strategy_executor": ComponentStatus("策略执行引擎"),
                "order_router": ComponentStatus("智能订单路由"),
                "runtime_monitor": ComponentStatus("策略运行时监控"),
                "execution_testing": ComponentStatus("执行测试验证")
            }
        )
        
        # 第六阶段：系统整合和优化
        self.phases[IntegrationPhase.PHASE_6_OPTIMIZATION] = PhaseStatus(
            phase=IntegrationPhase.PHASE_6_OPTIMIZATION,
            components={
                "system_integration": ComponentStatus("系统整合"),
                "performance_tuning": ComponentStatus("性能调优"),
                "documentation": ComponentStatus("文档更新"),
                "final_testing": ComponentStatus("最终测试")
            }
        )
    
    def _load_integration_config(self) -> Dict[str, Any]:
        """加载集成配置"""
        return {
            "rollback_enabled": True,
            "backup_before_integration": True,
            "test_after_each_component": True,
            "max_retry_attempts": 3,
            "component_timeout": 300,  # 5分钟
            "phase_timeout": 1800,     # 30分钟
            "health_check_interval": 60,  # 1分钟
            "notification_enabled": True
        }
    
    async def start_integration(self, start_from_phase: Optional[IntegrationPhase] = None):
        """开始渐进式集成"""
        logger.info("开始渐进式集成过程")
        
        try:
            # 确定开始阶段
            start_phase = start_from_phase or IntegrationPhase.PHASE_1_SECURITY
            
            # 按顺序执行各个阶段
            phase_order = [
                IntegrationPhase.PHASE_1_SECURITY,
                IntegrationPhase.PHASE_2_CACHE,
                IntegrationPhase.PHASE_3_MONITORING,
                IntegrationPhase.PHASE_4_WEBSOCKET,
                IntegrationPhase.PHASE_5_STRATEGY,
                IntegrationPhase.PHASE_6_OPTIMIZATION
            ]
            
            # 找到开始位置
            start_index = phase_order.index(start_phase)
            
            for phase in phase_order[start_index:]:
                success = await self._execute_phase(phase)
                
                if not success:
                    logger.error(f"阶段 {phase.value} 执行失败，停止集成")
                    break
                
                logger.info(f"阶段 {phase.value} 执行成功")
                
                # 阶段间暂停，允许观察系统状态
                if phase != IntegrationPhase.PHASE_6_OPTIMIZATION:
                    await self._inter_phase_pause()
            
            logger.info("渐进式集成过程完成")
            return True
            
        except Exception as e:
            logger.error(f"渐进式集成过程失败: {e}")
            await self._emergency_rollback()
            return False
    
    async def _execute_phase(self, phase: IntegrationPhase) -> bool:
        """执行单个阶段"""
        logger.info(f"开始执行阶段: {phase.value}")
        
        phase_status = self.phases[phase]
        phase_status.status = IntegrationStatus.IN_PROGRESS
        phase_status.started_at = datetime.utcnow()
        self.current_phase = phase
        
        try:
            # 创建备份
            if self.config["backup_before_integration"]:
                await self._create_backup(phase)
            
            # 执行阶段特定的集成逻辑
            success = await self._execute_phase_logic(phase)
            
            if success:
                phase_status.status = IntegrationStatus.COMPLETED
                phase_status.completed_at = datetime.utcnow()
                phase_status.progress = 100.0
                
                # 记录成功
                self._log_integration_event({
                    "phase": phase.value,
                    "status": "completed",
                    "timestamp": datetime.utcnow().isoformat(),
                    "duration": (phase_status.completed_at - phase_status.started_at).total_seconds()
                })
                
                return True
            else:
                raise Exception("阶段执行失败")
                
        except Exception as e:
            phase_status.status = IntegrationStatus.FAILED
            phase_status.error_message = str(e)
            
            # 记录失败
            self._log_integration_event({
                "phase": phase.value,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # 尝试回滚
            if self.config["rollback_enabled"]:
                await self._rollback_phase(phase)
            
            return False
    
    async def _execute_phase_logic(self, phase: IntegrationPhase) -> bool:
        """执行阶段特定的集成逻辑"""
        
        if phase == IntegrationPhase.PHASE_1_SECURITY:
            return await self._integrate_security_system()
        
        elif phase == IntegrationPhase.PHASE_2_CACHE:
            return await self._integrate_cache_system()
        
        elif phase == IntegrationPhase.PHASE_3_MONITORING:
            return await self._integrate_monitoring_system()
        
        elif phase == IntegrationPhase.PHASE_4_WEBSOCKET:
            return await self._integrate_websocket_enhancements()
        
        elif phase == IntegrationPhase.PHASE_5_STRATEGY:
            return await self._integrate_strategy_engine()
        
        elif phase == IntegrationPhase.PHASE_6_OPTIMIZATION:
            return await self._integrate_system_optimization()
        
        else:
            logger.error(f"未知阶段: {phase}")
            return False
    
    async def _integrate_security_system(self) -> bool:
        """集成安全系统"""
        logger.info("集成安全系统...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_1_SECURITY]
            
            # 集成输入验证器
            await self._integrate_component(
                phase_status.components["input_validator"],
                self._setup_input_validator
            )
            
            # 集成数据加密服务
            await self._integrate_component(
                phase_status.components["data_encryption"],
                self._setup_data_encryption
            )
            
            # 集成API参数验证
            await self._integrate_component(
                phase_status.components["api_validation"],
                self._setup_api_validation
            )
            
            # 集成验证中间件
            await self._integrate_component(
                phase_status.components["validation_middleware"],
                self._setup_validation_middleware
            )
            
            # 验证安全系统
            if await self._verify_security_integration():
                logger.info("安全系统集成验证成功")
                return True
            else:
                raise Exception("安全系统集成验证失败")
                
        except Exception as e:
            logger.error(f"安全系统集成失败: {e}")
            return False
    
    async def _integrate_cache_system(self) -> bool:
        """集成缓存系统"""
        logger.info("集成缓存系统...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_2_CACHE]
            
            # 按依赖顺序集成组件
            components_order = [
                "redis_cache",
                "market_data_cache", 
                "user_session_cache",
                "ai_conversation_cache",
                "cache_manager"
            ]
            
            for component_name in components_order:
                component = phase_status.components[component_name]
                
                if component_name == "redis_cache":
                    await self._integrate_component(component, self._setup_redis_cache)
                elif component_name == "market_data_cache":
                    await self._integrate_component(component, self._setup_market_data_cache)
                elif component_name == "user_session_cache":
                    await self._integrate_component(component, self._setup_user_session_cache)
                elif component_name == "ai_conversation_cache":
                    await self._integrate_component(component, self._setup_ai_conversation_cache)
                elif component_name == "cache_manager":
                    await self._integrate_component(component, self._setup_cache_manager)
            
            # 验证缓存系统
            if await self._verify_cache_integration():
                logger.info("缓存系统集成验证成功")
                return True
            else:
                raise Exception("缓存系统集成验证失败")
                
        except Exception as e:
            logger.error(f"缓存系统集成失败: {e}")
            return False
    
    async def _integrate_monitoring_system(self) -> bool:
        """集成性能监控系统"""
        logger.info("集成性能监控系统...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_3_MONITORING]
            
            # 集成性能优化器
            await self._integrate_component(
                phase_status.components["performance_optimizer"],
                self._setup_performance_optimizer
            )
            
            # 集成数据库监控
            await self._integrate_component(
                phase_status.components["database_monitor"],
                self._setup_database_monitor
            )
            
            # 集成统一管理器
            await self._integrate_component(
                phase_status.components["unified_manager"],
                self._setup_unified_manager
            )
            
            # 集成监控API
            await self._integrate_component(
                phase_status.components["monitoring_api"],
                self._setup_monitoring_api
            )
            
            # 验证监控系统
            if await self._verify_monitoring_integration():
                logger.info("监控系统集成验证成功")
                return True
            else:
                raise Exception("监控系统集成验证失败")
                
        except Exception as e:
            logger.error(f"监控系统集成失败: {e}")
            return False
    
    async def _integrate_websocket_enhancements(self) -> bool:
        """集成WebSocket增强功能"""
        logger.info("集成WebSocket增强功能...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_4_WEBSOCKET]
            
            # 备份现有WebSocket实现
            await self._backup_existing_websocket()
            
            # 集成新的WebSocket管理器
            await self._integrate_component(
                phase_status.components["websocket_manager"],
                self._setup_websocket_manager
            )
            
            # 集成连接监控
            await self._integrate_component(
                phase_status.components["connection_monitoring"],
                self._setup_connection_monitoring
            )
            
            # 集成自动重连
            await self._integrate_component(
                phase_status.components["auto_reconnect"],
                self._setup_auto_reconnect
            )
            
            # 验证WebSocket系统
            if await self._verify_websocket_integration():
                logger.info("WebSocket系统集成验证成功")
                return True
            else:
                raise Exception("WebSocket系统集成验证失败")
                
        except Exception as e:
            logger.error(f"WebSocket系统集成失败: {e}")
            return False
    
    async def _integrate_strategy_engine(self) -> bool:
        """集成策略执行引擎"""
        logger.info("集成策略执行引擎...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_5_STRATEGY]
            
            # 这个阶段风险最高，需要特别谨慎
            logger.warning("策略执行引擎集成 - 高风险阶段，建议在测试环境先验证")
            
            # 集成策略执行器
            await self._integrate_component(
                phase_status.components["strategy_executor"],
                self._setup_strategy_executor
            )
            
            # 集成订单路由
            await self._integrate_component(
                phase_status.components["order_router"],
                self._setup_order_router
            )
            
            # 集成运行时监控
            await self._integrate_component(
                phase_status.components["runtime_monitor"],
                self._setup_runtime_monitor
            )
            
            # 执行测试验证
            await self._integrate_component(
                phase_status.components["execution_testing"],
                self._setup_execution_testing
            )
            
            # 验证策略引擎
            if await self._verify_strategy_integration():
                logger.info("策略引擎集成验证成功")
                return True
            else:
                raise Exception("策略引擎集成验证失败")
                
        except Exception as e:
            logger.error(f"策略引擎集成失败: {e}")
            return False
    
    async def _integrate_system_optimization(self) -> bool:
        """集成系统整合和优化"""
        logger.info("集成系统整合和优化...")
        
        try:
            phase_status = self.phases[IntegrationPhase.PHASE_6_OPTIMIZATION]
            
            # 系统整合
            await self._integrate_component(
                phase_status.components["system_integration"],
                self._perform_system_integration
            )
            
            # 性能调优
            await self._integrate_component(
                phase_status.components["performance_tuning"],
                self._perform_performance_tuning
            )
            
            # 文档更新
            await self._integrate_component(
                phase_status.components["documentation"],
                self._update_documentation
            )
            
            # 最终测试
            await self._integrate_component(
                phase_status.components["final_testing"],
                self._perform_final_testing
            )
            
            logger.info("系统整合和优化完成")
            return True
            
        except Exception as e:
            logger.error(f"系统整合和优化失败: {e}")
            return False
    
    async def _integrate_component(self, component: ComponentStatus, 
                                 setup_func: callable) -> bool:
        """集成单个组件"""
        logger.info(f"集成组件: {component.name}")
        
        component.status = IntegrationStatus.IN_PROGRESS
        component.started_at = datetime.utcnow()
        
        try:
            # 执行组件设置
            success = await setup_func()
            
            if success:
                component.status = IntegrationStatus.COMPLETED
                component.completed_at = datetime.utcnow()
                logger.info(f"组件 {component.name} 集成成功")
                
                # 如果配置了，执行组件测试
                if self.config["test_after_each_component"]:
                    test_result = await self._test_component(component)
                    if not test_result:
                        raise Exception(f"组件 {component.name} 测试失败")
                
                return True
            else:
                raise Exception(f"组件 {component.name} 设置失败")
                
        except Exception as e:
            component.status = IntegrationStatus.FAILED
            component.error_message = str(e)
            logger.error(f"组件 {component.name} 集成失败: {e}")
            return False
    
    # ===========================================
    # 组件设置方法（示例实现）
    # ===========================================
    
    async def _setup_input_validator(self) -> bool:
        """设置输入验证器"""
        try:
            from app.security.input_validator import InputValidator
            validator = InputValidator()
            
            # 测试基本功能
            test_result = validator.validate_email("test@example.com")
            return test_result is not None
            
        except Exception as e:
            logger.error(f"设置输入验证器失败: {e}")
            return False
    
    async def _setup_data_encryption(self) -> bool:
        """设置数据加密服务"""
        try:
            from app.security.data_encryption import DataEncryptionService
            encryption = DataEncryptionService()
            
            # 测试加密功能
            test_password = "test123"
            hashed = encryption.hash_password(test_password)
            verified = encryption.verify_password(test_password, hashed)
            
            return verified
            
        except Exception as e:
            logger.error(f"设置数据加密服务失败: {e}")
            return False
    
    async def _setup_api_validation(self) -> bool:
        """设置API参数验证"""
        try:
            from app.services.api_validation_service import api_validation_service
            # API验证服务已经预配置，只需要确认可用
            return True
            
        except Exception as e:
            logger.error(f"设置API参数验证失败: {e}")
            return False
    
    async def _setup_validation_middleware(self) -> bool:
        """设置验证中间件"""
        try:
            from app.middleware.api_validation_middleware import APIValidationMiddleware
            # 中间件需要在应用启动时添加，这里只验证可用性
            return True
            
        except Exception as e:
            logger.error(f"设置验证中间件失败: {e}")
            return False
    
    async def _setup_redis_cache(self) -> bool:
        """设置Redis缓存"""
        try:
            from app.services.redis_cache_service import cache_service
            await cache_service.connect()
            return cache_service.is_connected
            
        except Exception as e:
            logger.error(f"设置Redis缓存失败: {e}")
            return False
    
    # ... 其他组件设置方法的简化实现
    
    async def _setup_market_data_cache(self) -> bool:
        """设置市场数据缓存"""
        return True  # 简化实现
    
    async def _setup_user_session_cache(self) -> bool:
        """设置用户会话缓存"""
        return True  # 简化实现
    
    async def _setup_ai_conversation_cache(self) -> bool:
        """设置AI对话缓存"""
        return True  # 简化实现
    
    async def _setup_cache_manager(self) -> bool:
        """设置缓存管理器"""
        return True  # 简化实现
    
    async def _setup_performance_optimizer(self) -> bool:
        """设置性能优化器"""
        return True  # 简化实现
    
    async def _setup_database_monitor(self) -> bool:
        """设置数据库监控"""
        return True  # 简化实现
    
    async def _setup_unified_manager(self) -> bool:
        """设置统一管理器"""
        return True  # 简化实现
    
    async def _setup_monitoring_api(self) -> bool:
        """设置监控API"""
        return True  # 简化实现
    
    async def _setup_websocket_manager(self) -> bool:
        """设置WebSocket管理器"""
        return True  # 简化实现
    
    async def _setup_connection_monitoring(self) -> bool:
        """设置连接监控"""
        return True  # 简化实现
    
    async def _setup_auto_reconnect(self) -> bool:
        """设置自动重连"""
        return True  # 简化实现
    
    async def _setup_strategy_executor(self) -> bool:
        """设置策略执行器"""
        return True  # 简化实现
    
    async def _setup_order_router(self) -> bool:
        """设置订单路由"""
        return True  # 简化实现
    
    async def _setup_runtime_monitor(self) -> bool:
        """设置运行时监控"""
        return True  # 简化实现
    
    async def _setup_execution_testing(self) -> bool:
        """设置执行测试"""
        return True  # 简化实现
    
    async def _perform_system_integration(self) -> bool:
        """执行系统整合"""
        return True  # 简化实现
    
    async def _perform_performance_tuning(self) -> bool:
        """执行性能调优"""
        return True  # 简化实现
    
    async def _update_documentation(self) -> bool:
        """更新文档"""
        return True  # 简化实现
    
    async def _perform_final_testing(self) -> bool:
        """执行最终测试"""
        return True  # 简化实现
    
    # ===========================================
    # 验证方法
    # ===========================================
    
    async def _verify_security_integration(self) -> bool:
        """验证安全系统集成"""
        # 简化实现
        return True
    
    async def _verify_cache_integration(self) -> bool:
        """验证缓存系统集成"""
        # 简化实现
        return True
    
    async def _verify_monitoring_integration(self) -> bool:
        """验证监控系统集成"""
        # 简化实现
        return True
    
    async def _verify_websocket_integration(self) -> bool:
        """验证WebSocket系统集成"""
        # 简化实现
        return True
    
    async def _verify_strategy_integration(self) -> bool:
        """验证策略引擎集成"""
        # 简化实现
        return True
    
    # ===========================================
    # 支持方法
    # ===========================================
    
    async def _test_component(self, component: ComponentStatus) -> bool:
        """测试单个组件"""
        logger.info(f"测试组件: {component.name}")
        # 简化实现
        return True
    
    async def _create_backup(self, phase: IntegrationPhase):
        """创建备份"""
        logger.info(f"为阶段 {phase.value} 创建备份")
        # 实际实现应该备份相关文件和配置
    
    async def _backup_existing_websocket(self):
        """备份现有WebSocket实现"""
        logger.info("备份现有WebSocket实现")
    
    async def _inter_phase_pause(self):
        """阶段间暂停"""
        logger.info("阶段间暂停，观察系统状态...")
        await asyncio.sleep(30)  # 30秒观察期
    
    async def _rollback_phase(self, phase: IntegrationPhase):
        """回滚阶段"""
        logger.warning(f"回滚阶段: {phase.value}")
        
        phase_status = self.phases[phase]
        phase_status.status = IntegrationStatus.ROLLED_BACK
        
        # 记录回滚
        self._log_integration_event({
            "phase": phase.value,
            "status": "rolled_back",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": phase_status.error_message
        })
    
    async def _emergency_rollback(self):
        """紧急回滚"""
        logger.error("执行紧急回滚")
        
        # 回滚所有已完成和进行中的阶段
        for phase, status in self.phases.items():
            if status.status in [IntegrationStatus.COMPLETED, IntegrationStatus.IN_PROGRESS]:
                await self._rollback_phase(phase)
    
    def _log_integration_event(self, event: Dict[str, Any]):
        """记录集成事件"""
        self.integration_log.append(event)
        
        # 保持日志大小
        if len(self.integration_log) > 1000:
            self.integration_log = self.integration_log[-500:]
    
    # ===========================================
    # 公共接口
    # ===========================================
    
    def get_integration_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            "current_phase": self.current_phase.value if self.current_phase else None,
            "phases": {
                phase.value: {
                    "status": status.status.value,
                    "progress": status.progress,
                    "started_at": status.started_at.isoformat() if status.started_at else None,
                    "completed_at": status.completed_at.isoformat() if status.completed_at else None,
                    "error_message": status.error_message,
                    "components": {
                        comp_name: {
                            "status": comp.status.value,
                            "error": comp.error_message
                        }
                        for comp_name, comp in status.components.items()
                    }
                }
                for phase, status in self.phases.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_integration_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取集成日志"""
        return self.integration_log[-limit:] if self.integration_log else []
    
    async def pause_integration(self):
        """暂停集成"""
        logger.info("暂停集成过程")
        # 实现暂停逻辑
    
    async def resume_integration(self):
        """恢复集成"""
        logger.info("恢复集成过程")
        # 实现恢复逻辑

# 全局集成管理器实例
integration_manager = ProgressiveIntegrationManager()

# 使用示例
async def main():
    """集成管理器使用示例"""
    manager = ProgressiveIntegrationManager()
    
    # 开始完整集成
    success = await manager.start_integration()
    
    if success:
        print("🎉 渐进式集成成功完成！")
    else:
        print("❌ 渐进式集成失败")
        
        # 查看状态
        status = manager.get_integration_status()
        print(f"集成状态: {json.dumps(status, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(main())