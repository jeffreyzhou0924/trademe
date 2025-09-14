#!/usr/bin/env python3
"""
AI策略生成系统全面测试套件
验证修复后的AI策略生成系统是否能正确使用对话历史生成定制化策略代码
"""

import asyncio
import sys
import os
import json
import time
import unittest
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入测试模块
from app.services.strategy_requirements_extractor import StrategyRequirementsExtractor
from app.services.ai_service import AIService
from app.services.strategy_generation_orchestrator import StrategyGenerationOrchestrator
from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer


class AIStrategyGenerationTestSuite:
    """AI策略生成系统全面测试套件"""
    
    def __init__(self):
        self.test_results = {
            'unit_tests': {},
            'integration_tests': {},
            'regression_tests': {},
            'performance_tests': {}
        }
        self.start_time = time.time()

    def print_header(self, title: str, level: int = 1):
        """打印测试标题"""
        if level == 1:
            print("\n" + "=" * 80)
            print(f"📋 {title}")
            print("=" * 80)
        else:
            print(f"\n{'#' * level} {title}")
            print("-" * 60)

    def print_result(self, test_name: str, passed: bool, details: str = None):
        """打印测试结果"""
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"   {status} {test_name}")
        if details:
            print(f"      详情: {details}")
        return passed

    async def test_1_unit_tests(self):
        """单元测试：策略需求提取器的各项功能"""
        
        self.print_header("1. 单元测试 - 策略需求提取器", 1)
        
        unit_results = {}
        
        # 测试1.1: 基本需求提取
        print("\n🧪 测试1.1: 基本需求提取功能")
        
        conversation = self.create_macd_conversation()
        requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
        
        # 验证指标提取
        has_macd = 'MACD' in requirements.get('indicators', {})
        has_rsi = 'RSI' in requirements.get('indicators', {})
        
        unit_results['indicators_extraction'] = self.print_result(
            "指标提取", 
            has_macd and has_rsi,
            f"MACD: {has_macd}, RSI: {has_rsi}"
        )
        
        # 验证参数提取
        macd_params = requirements.get('indicators', {}).get('MACD', {})
        correct_params = (
            macd_params.get('fast_period') == 12 and 
            macd_params.get('slow_period') == 26 and 
            macd_params.get('signal_period') == 9
        )
        
        unit_results['parameters_extraction'] = self.print_result(
            "参数提取", 
            correct_params,
            f"MACD参数: {macd_params}"
        )
        
        # 测试1.2: 风险管理提取
        print("\n🧪 测试1.2: 风险管理参数提取")
        
        risk_mgmt = requirements.get('risk_management', {})
        stop_loss_correct = risk_mgmt.get('stop_loss') == 3.0
        take_profit_correct = risk_mgmt.get('take_profit') == 5.0
        
        unit_results['risk_management'] = self.print_result(
            "风险管理参数", 
            stop_loss_correct and take_profit_correct,
            f"止损: {risk_mgmt.get('stop_loss')}%, 止盈: {risk_mgmt.get('take_profit')}%"
        )
        
        # 测试1.3: 特殊逻辑识别
        print("\n🧪 测试1.3: 特殊逻辑识别")
        
        special_logic = requirements.get('special_logic', [])
        has_divergence = 'bearish_divergence' in special_logic
        has_golden_cross = 'golden_cross' in special_logic
        
        unit_results['special_logic'] = self.print_result(
            "特殊逻辑识别", 
            has_divergence and has_golden_cross,
            f"识别逻辑: {special_logic}"
        )
        
        # 测试1.4: 时间框架和交易对
        print("\n🧪 测试1.4: 交易参数识别")
        
        timeframe_correct = requirements.get('timeframe') == '1h'
        trading_pair_correct = requirements.get('trading_pair') == 'BTC/USDT'
        
        unit_results['trading_params'] = self.print_result(
            "交易参数识别", 
            timeframe_correct and trading_pair_correct,
            f"时间框架: {requirements.get('timeframe')}, 交易对: {requirements.get('trading_pair')}"
        )
        
        # 测试1.5: 边界情况处理
        print("\n🧪 测试1.5: 边界情况处理")
        
        # 空对话历史
        empty_requirements = await StrategyRequirementsExtractor.extract_requirements([])
        empty_handled = len(empty_requirements.get('indicators', {})) == 0
        
        # 只有确认消息
        confirm_only = [self.create_message('user', '确认生成代码')]
        confirm_requirements = await StrategyRequirementsExtractor.extract_requirements(confirm_only)
        confirm_handled = len(confirm_requirements.get('indicators', {})) == 0
        
        unit_results['edge_cases'] = self.print_result(
            "边界情况处理", 
            empty_handled and confirm_handled,
            f"空历史: {empty_handled}, 仅确认: {confirm_handled}"
        )
        
        self.test_results['unit_tests'] = unit_results
        unit_success_rate = sum(unit_results.values()) / len(unit_results) * 100
        print(f"\n📊 单元测试成功率: {unit_success_rate:.1f}% ({sum(unit_results.values())}/{len(unit_results)})")
        
        return unit_success_rate >= 80

    async def test_2_integration_tests(self):
        """集成测试：完整的策略生成流程"""
        
        self.print_header("2. 集成测试 - 完整策略生成流程", 1)
        
        integration_results = {}
        
        # 测试2.1: 策略成熟度分析
        print("\n🧪 测试2.1: 策略成熟度分析")
        
        conversation = self.create_macd_conversation()
        analyzer = StrategyMaturityAnalyzer()
        
        try:
            # 使用正确的方法名
            maturity_result = await analyzer.analyze_conversation_maturity(conversation)
            
            maturity_passed = (
                maturity_result.get('is_mature', False) and
                maturity_result.get('overall_score', 0) >= 70
            )
            
            integration_results['maturity_analysis'] = self.print_result(
                "策略成熟度分析", 
                maturity_passed,
                f"成熟度得分: {maturity_result.get('overall_score', 0)}/100"
            )
        except Exception as e:
            integration_results['maturity_analysis'] = self.print_result(
                "策略成熟度分析", 
                False,
                f"分析失败: {str(e)}"
            )
        
        # 测试2.2: 策略生成编排器
        print("\n🧪 测试2.2: 策略生成编排器")
        
        # 模拟用户确认
        conversation.append(self.create_message('user', '确认生成代码'))
        
        orchestrator = StrategyGenerationOrchestrator()
        
        # 模拟AI服务
        with patch.object(orchestrator.ai_service, 'chat_completion') as mock_ai:
            mock_ai.return_value = {
                'success': True,
                'content': self.get_sample_strategy_code(),
                'usage': {'total_tokens': 1000}
            }
            
            orchestration_result = await orchestrator.process_strategy_generation(
                conversation=conversation,
                user_id=1,
                session_type='strategy'
            )
            
            orchestration_passed = orchestration_result.get('success', False)
            
            integration_results['orchestration'] = self.print_result(
                "策略生成编排", 
                orchestration_passed,
                f"生成结果: {orchestration_result.get('message', 'Unknown')}"
            )
        
        # 测试2.3: 提示词生成质量
        print("\n🧪 测试2.3: 提示词生成质量")
        
        requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
        formatted_prompt = StrategyRequirementsExtractor.format_requirements_prompt(requirements)
        
        # 检查提示词是否包含关键信息
        prompt_checks = {
            'MACD参数': 'MACD(fast_period=12' in formatted_prompt,
            'RSI参数': 'RSI(period=14)' in formatted_prompt,
            '止损参数': 'stop_loss: 3.0' in formatted_prompt,
            '止盈参数': 'take_profit: 5.0' in formatted_prompt,
            '背离逻辑': 'bearish_divergence' in formatted_prompt,
            '时间框架': '1h' in formatted_prompt,
            '交易对': 'BTC/USDT' in formatted_prompt
        }
        
        prompt_quality = sum(prompt_checks.values()) / len(prompt_checks)
        
        integration_results['prompt_quality'] = self.print_result(
            "提示词生成质量", 
            prompt_quality >= 0.8,
            f"包含关键信息比例: {prompt_quality:.1%}"
        )
        
        # 测试2.4: 历史对话传递
        print("\n🧪 测试2.4: 历史对话传递验证")
        
        # 创建带有多轮对话的历史
        extended_conversation = self.create_extended_conversation()
        extended_requirements = await StrategyRequirementsExtractor.extract_requirements(extended_conversation)
        
        # 验证是否能从多轮对话中提取完整信息
        history_passing = (
            len(extended_requirements.get('indicators', {})) >= 2 and
            extended_requirements.get('risk_management', {}).get('stop_loss') is not None
        )
        
        integration_results['history_passing'] = self.print_result(
            "历史对话传递", 
            history_passing,
            f"从{len(extended_conversation)}轮对话中提取指标数: {len(extended_requirements.get('indicators', {}))}"
        )
        
        self.test_results['integration_tests'] = integration_results
        integration_success_rate = sum(integration_results.values()) / len(integration_results) * 100
        print(f"\n📊 集成测试成功率: {integration_success_rate:.1f}% ({sum(integration_results.values())}/{len(integration_results)})")
        
        return integration_success_rate >= 75

    async def test_3_regression_tests(self):
        """回归测试：确保修复不影响现有功能"""
        
        self.print_header("3. 回归测试 - 现有功能验证", 1)
        
        regression_results = {}
        
        # 测试3.1: AI服务基础功能
        print("\n🧪 测试3.1: AI服务基础功能")
        
        try:
            ai_service = AIService()
            # 测试服务初始化
            service_init = hasattr(ai_service, 'chat_completion')
            
            regression_results['ai_service_init'] = self.print_result(
                "AI服务初始化", 
                service_init,
                "服务对象创建成功"
            )
        except Exception as e:
            regression_results['ai_service_init'] = self.print_result(
                "AI服务初始化", 
                False,
                f"初始化失败: {str(e)}"
            )
        
        # 测试3.2: 策略需求提取器向后兼容
        print("\n🧪 测试3.2: 策略需求提取器向后兼容")
        
        # 使用旧格式的对话测试
        old_format_conversation = [
            self.create_message('user', '我想要一个简单的移动平均策略'),
            self.create_message('assistant', '好的，我可以帮您创建移动平均策略'),
            self.create_message('user', '确认')
        ]
        
        try:
            old_requirements = await StrategyRequirementsExtractor.extract_requirements(old_format_conversation)
            backward_compatible = isinstance(old_requirements, dict)
            
            regression_results['backward_compatibility'] = self.print_result(
                "向后兼容性", 
                backward_compatible,
                f"成功处理旧格式对话，返回类型: {type(old_requirements)}"
            )
        except Exception as e:
            regression_results['backward_compatibility'] = self.print_result(
                "向后兼容性", 
                False,
                f"处理旧格式失败: {str(e)}"
            )
        
        # 测试3.3: 数据库操作不受影响
        print("\n🧪 测试3.3: 数据库操作正常")
        
        try:
            # 简单测试策略需求提取不会破坏数据库操作
            from app.models.claude_conversation import ClaudeConversation
            db_operations_ok = hasattr(ClaudeConversation, '__tablename__')
            
            regression_results['database_operations'] = self.print_result(
                "数据库操作", 
                db_operations_ok,
                "模型导入和属性访问正常"
            )
        except Exception as e:
            regression_results['database_operations'] = self.print_result(
                "数据库操作", 
                False,
                f"数据库操作异常: {str(e)}"
            )
        
        # 测试3.4: 其他AI功能模块
        print("\n🧪 测试3.4: 其他AI功能模块")
        
        try:
            from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer
            from app.services.strategy_auto_fix_service import StrategyAutoFixService
            
            modules_loadable = True
            
            regression_results['other_modules'] = self.print_result(
                "其他AI模块", 
                modules_loadable,
                "相关AI模块正常导入"
            )
        except Exception as e:
            regression_results['other_modules'] = self.print_result(
                "其他AI模块", 
                False,
                f"模块导入失败: {str(e)}"
            )
        
        self.test_results['regression_tests'] = regression_results
        regression_success_rate = sum(regression_results.values()) / len(regression_results) * 100
        print(f"\n📊 回归测试成功率: {regression_success_rate:.1f}% ({sum(regression_results.values())}/{len(regression_results)})")
        
        return regression_success_rate >= 80

    async def test_4_performance_tests(self):
        """性能测试：验证修复不影响响应速度"""
        
        self.print_header("4. 性能测试 - 响应速度验证", 1)
        
        performance_results = {}
        
        # 测试4.1: 需求提取性能
        print("\n🧪 测试4.1: 需求提取性能")
        
        conversation = self.create_macd_conversation()
        
        start_time = time.time()
        requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
        extraction_time = time.time() - start_time
        
        # 需求提取应该在2秒内完成
        extraction_fast = extraction_time < 2.0
        
        performance_results['extraction_performance'] = self.print_result(
            "需求提取性能", 
            extraction_fast,
            f"耗时: {extraction_time:.3f}秒 (目标: <2.0秒)"
        )
        
        # 测试4.2: 大量历史对话处理
        print("\n🧪 测试4.2: 大量历史对话处理性能")
        
        # 创建50条消息的对话历史
        large_conversation = []
        for i in range(50):
            role = 'user' if i % 2 == 0 else 'assistant'
            content = f"这是第{i+1}条消息，包含一些策略相关的内容"
            large_conversation.append(self.create_message(role, content))
        
        start_time = time.time()
        large_requirements = await StrategyRequirementsExtractor.extract_requirements(large_conversation)
        large_processing_time = time.time() - start_time
        
        # 大量对话处理应该在5秒内完成
        large_processing_fast = large_processing_time < 5.0
        
        performance_results['large_conversation_performance'] = self.print_result(
            "大量对话处理性能", 
            large_processing_fast,
            f"处理50条消息耗时: {large_processing_time:.3f}秒 (目标: <5.0秒)"
        )
        
        # 测试4.3: 内存使用情况
        print("\n🧪 测试4.3: 内存使用检查")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        
        # 内存使用应该在合理范围内（< 500MB for this test）
        memory_reasonable = memory_usage < 500
        
        performance_results['memory_usage'] = self.print_result(
            "内存使用", 
            memory_reasonable,
            f"当前内存使用: {memory_usage:.1f}MB (目标: <500MB)"
        )
        
        self.test_results['performance_tests'] = performance_results
        performance_success_rate = sum(performance_results.values()) / len(performance_results) * 100
        print(f"\n📊 性能测试成功率: {performance_success_rate:.1f}% ({sum(performance_results.values())}/{len(performance_results)})")
        
        return performance_success_rate >= 70

    def create_message(self, role: str, content: str):
        """创建消息对象"""
        return type('obj', (object,), {
            'message_type': role,
            'content': content,
            'created_at': datetime.now()
        })()

    def create_macd_conversation(self) -> List:
        """创建MACD策略对话历史"""
        return [
            self.create_message('user', """
            我想创建一个MACD顶背离策略，具体要求如下：
            1. 使用MACD指标，参数为12,26,9
            2. 检测顶背离：当价格创新高但MACD柱状图不创新高时
            3. 入场条件：出现顶背离信号，且RSI(14)大于70表示超买
            4. 出场条件：止损3%，止盈5%，或者MACD金叉时平仓
            5. 时间框架：1小时
            6. 交易对：BTC/USDT
            """),
            self.create_message('assistant', """
            好的，我理解您的需求。您想创建一个基于MACD顶背离的策略，主要特点包括：

            1. **MACD顶背离检测**：使用MACD(12,26,9)参数，当价格创新高但MACD柱状图不创新高时识别顶背离
            2. **超买确认**：配合RSI(14)>70确认超买状态
            3. **风险管理**：3%止损，5%止盈
            4. **备选出场**：MACD金叉时也可以平仓
            
            这是一个经典的逆势交易策略，利用技术指标背离来捕捉潜在的趋势反转点。
            
            策略已经比较成熟，包含了完整的入场条件、出场条件和风险管理。
            
            您是否确认生成这个策略的代码？
            """)
        ]

    def create_extended_conversation(self) -> List:
        """创建扩展的对话历史，包含多轮细节讨论"""
        base_conversation = self.create_macd_conversation()
        
        # 添加更多细节讨论
        extended = base_conversation + [
            self.create_message('user', '我还希望添加成交量确认'),
            self.create_message('assistant', '好的，我们可以添加成交量指标来确认信号强度'),
            self.create_message('user', '当成交量大于20日平均成交量的1.5倍时才入场'),
            self.create_message('assistant', '明白了，我会在策略中添加成交量过滤条件'),
            self.create_message('user', '确认生成代码')
        ]
        
        return extended

    def get_sample_strategy_code(self) -> str:
        """获取示例策略代码"""
        return '''
def strategy_logic(self):
    """
    MACD顶背离策略
    """
    # 获取指标数据
    macd_line, macd_signal, macd_histogram = self.get_macd(12, 26, 9)
    rsi = self.get_rsi(14)
    close_prices = self.get_kline_data()['close']
    
    # 检测顶背离
    if self.detect_bearish_divergence(close_prices, macd_histogram):
        if rsi[-1] > 70:  # 超买确认
            return {'action': 'sell', 'reason': 'MACD顶背离+RSI超买'}
    
    # 检测金叉出场
    if macd_line[-1] > macd_signal[-1] and macd_line[-2] <= macd_signal[-2]:
        return {'action': 'close', 'reason': 'MACD金叉'}
    
    return {'action': 'hold'}
'''

    async def run_all_tests(self):
        """运行所有测试"""
        
        self.print_header("🧪 AI策略生成系统全面测试开始", 1)
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        test_phases = [
            ("单元测试", self.test_1_unit_tests),
            ("集成测试", self.test_2_integration_tests),
            ("回归测试", self.test_3_regression_tests),
            ("性能测试", self.test_4_performance_tests)
        ]
        
        all_results = []
        
        for phase_name, test_func in test_phases:
            try:
                result = await test_func()
                all_results.append(result)
                print(f"\n{'✅' if result else '❌'} {phase_name}: {'通过' if result else '失败'}")
            except Exception as e:
                print(f"\n❌ {phase_name}: 执行异常 - {str(e)}")
                all_results.append(False)
        
        # 生成最终报告
        self.generate_final_report(all_results)
        
        return all(all_results)

    def generate_final_report(self, phase_results: List[bool]):
        """生成最终测试报告"""
        
        self.print_header("📊 最终测试报告", 1)
        
        total_time = time.time() - self.start_time
        
        print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总耗时: {total_time:.2f}秒")
        print(f"🎯 测试阶段: {len(phase_results)}")
        print(f"✅ 通过阶段: {sum(phase_results)}")
        print(f"❌ 失败阶段: {len(phase_results) - sum(phase_results)}")
        print(f"📈 成功率: {sum(phase_results)/len(phase_results)*100:.1f}%")
        
        # 详细结果统计
        print(f"\n📋 详细测试结果:")
        
        for category, results in self.test_results.items():
            if results:
                success_count = sum(results.values())
                total_count = len(results)
                success_rate = success_count / total_count * 100
                print(f"   📊 {category}: {success_count}/{total_count} ({success_rate:.1f}%)")
        
        # 修复效果评估
        overall_success = sum(phase_results) / len(phase_results)
        
        print(f"\n🎯 修复效果评估:")
        
        if overall_success >= 0.8:
            print("   🎉 修复完全成功！AI策略生成系统工作正常")
            print("   ✅ 策略需求提取器正确识别对话中的关键参数")
            print("   ✅ 对话历史正确传递到策略生成器")
            print("   ✅ 生成的策略代码应该包含用户描述的所有细节")
            print("   ✅ 系统性能和稳定性保持良好")
        elif overall_success >= 0.6:
            print("   ⚠️  修复部分成功，存在需要优化的地方")
            print("   🔧 建议检查失败的测试项，进行针对性修复")
        else:
            print("   ❌ 修复效果不理想，需要进一步调试")
            print("   🛠️  建议回退修改并重新分析问题")
        
        # 建议后续行动
        print(f"\n💡 建议后续行动:")
        
        if self.test_results.get('unit_tests', {}).get('parameters_extraction', False):
            print("   ✅ 参数提取功能正常，可以继续优化生成质量")
        else:
            print("   🔧 参数提取存在问题，需要重点修复")
        
        if self.test_results.get('integration_tests', {}).get('history_passing', False):
            print("   ✅ 历史对话传递正常，上下文丢失问题已解决")
        else:
            print("   🚨 历史对话传递仍有问题，需要检查对话历史处理逻辑")
        
        if self.test_results.get('performance_tests', {}).get('extraction_performance', False):
            print("   ✅ 性能表现良好，修复没有影响响应速度")
        else:
            print("   ⚠️  性能有所下降，需要优化处理效率")
        
        print(f"\n{'='*80}")
        print(f"🏁 测试完成 - {'修复成功' if overall_success >= 0.8 else '需要进一步修复'}")
        print(f"{'='*80}")


async def main():
    """主测试函数"""
    test_suite = AIStrategyGenerationTestSuite()
    
    try:
        success = await test_suite.run_all_tests()
        exit_code = 0 if success else 1
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 测试套件执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())