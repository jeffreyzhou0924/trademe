#!/usr/bin/env python3
"""
策略生成修复效果专项验证测试
重点验证上下文丢失问题的修复效果
"""

import asyncio
import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.strategy_requirements_extractor import StrategyRequirementsExtractor


class StrategyGenerationFixValidator:
    """策略生成修复效果专项验证器"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()

    def print_header(self, title: str):
        """打印测试标题"""
        print("\n" + "=" * 80)
        print(f"🔍 {title}")
        print("=" * 80)

    def print_test(self, test_name: str):
        """打印测试名称"""
        print(f"\n🧪 {test_name}")
        print("-" * 60)

    def print_result(self, item: str, passed: bool, details: str = None):
        """打印测试结果"""
        status = "✅" if passed else "❌"
        print(f"   {status} {item}: {'通过' if passed else '失败'}")
        if details:
            print(f"      详情: {details}")
        return passed

    def create_message(self, role: str, content: str):
        """创建消息对象"""
        return type('obj', (object,), {
            'message_type': role,
            'content': content.strip(),
            'created_at': datetime.now()
        })()

    async def test_context_preservation(self):
        """测试上下文保持能力"""
        
        self.print_header("上下文保持能力测试")
        
        # 创建复杂的MACD策略对话
        conversation = [
            self.create_message('user', """
            我想创建一个MACD顶背离策略，要求如下：
            1. MACD参数：快线12，慢线26，信号线9
            2. 当价格创新高但MACD柱状图不创新高时，识别为顶背离
            3. RSI(14)要大于70作为超买确认
            4. 止损设置为3%，止盈设置为5%
            5. 时间框架使用1小时
            6. 交易对选择BTC/USDT
            """),
            
            self.create_message('assistant', """
            好的，我理解您的MACD顶背离策略需求：

            **技术指标设置：**
            - MACD(12,26,9) - 用于背离检测
            - RSI(14) - 超买确认

            **入场逻辑：**
            - 价格创新高，但MACD柱状图不创新高（顶背离）
            - RSI > 70 确认超买状态
            
            **风险管理：**
            - 止损：3%
            - 止盈：5%
            
            **交易设置：**
            - 时间框架：1小时
            - 交易对：BTC/USDT

            这是一个完整的逆势交易策略。您确认生成代码吗？
            """),
            
            self.create_message('user', "还要加上成交量确认，当成交量大于20日均量1.5倍时才入场"),
            
            self.create_message('assistant', """
            明白了，我会在策略中加入成交量过滤条件：

            **增加成交量确认：**
            - 成交量 > 20日平均成交量 × 1.5

            **完整入场条件现在是：**
            1. MACD顶背离（价格新高，MACD柱不新高）
            2. RSI(14) > 70（超买确认）
            3. 成交量 > 20日均量 × 1.5（成交量确认）

            策略逻辑已经完善，您确认生成代码吗？
            """),
            
            self.create_message('user', "确认生成代码")
        ]
        
        self.print_test("复杂对话历史中的需求提取")
        
        # 提取策略需求
        requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
        
        # 详细检查提取结果
        print("   📋 提取的策略需求详情：")
        
        # 检查技术指标
        indicators = requirements.get('indicators', {})
        print(f"      指标数量: {len(indicators)}")
        for indicator, params in indicators.items():
            print(f"      - {indicator}: {params}")
        
        # 检查风险管理
        risk_mgmt = requirements.get('risk_management', {})
        print(f"      风险管理: {risk_mgmt}")
        
        # 检查特殊逻辑
        special_logic = requirements.get('special_logic', [])
        print(f"      特殊逻辑: {special_logic}")
        
        # 检查交易参数
        timeframe = requirements.get('timeframe')
        trading_pair = requirements.get('trading_pair')
        print(f"      时间框架: {timeframe}")
        print(f"      交易对: {trading_pair}")
        
        # 验证关键需求是否被正确提取
        validations = {}
        
        # 1. MACD指标及参数
        macd_params = indicators.get('MACD', {})
        validations['MACD参数'] = self.print_result(
            "MACD指标参数",
            (macd_params.get('fast_period') == 12 and 
             macd_params.get('slow_period') == 26 and 
             macd_params.get('signal_period') == 9),
            f"提取参数: {macd_params}"
        )
        
        # 2. RSI指标及参数
        rsi_params = indicators.get('RSI', {})
        validations['RSI参数'] = self.print_result(
            "RSI指标参数",
            rsi_params.get('period') == 14,
            f"提取参数: {rsi_params}"
        )
        
        # 3. 风险管理参数
        validations['风险管理'] = self.print_result(
            "风险管理参数",
            (risk_mgmt.get('stop_loss') == 3.0 and 
             risk_mgmt.get('take_profit') == 5.0),
            f"止损: {risk_mgmt.get('stop_loss')}%, 止盈: {risk_mgmt.get('take_profit')}%"
        )
        
        # 4. 背离逻辑识别
        validations['背离逻辑'] = self.print_result(
            "顶背离逻辑识别",
            'bearish_divergence' in special_logic,
            f"识别到的特殊逻辑: {special_logic}"
        )
        
        # 5. 交易参数
        validations['交易参数'] = self.print_result(
            "交易参数识别",
            (timeframe == '1h' and trading_pair == 'BTC/USDT'),
            f"时间框架: {timeframe}, 交易对: {trading_pair}"
        )
        
        # 6. 成交量逻辑（在后续对话中添加的）
        volume_logic = any('volume' in logic.lower() for logic in special_logic + 
                          requirements.get('entry_conditions', []) + 
                          requirements.get('exit_conditions', []))
        
        validations['成交量确认'] = self.print_result(
            "成交量确认逻辑",
            volume_logic,
            f"成交量逻辑识别: {volume_logic}"
        )
        
        return validations

    async def test_prompt_generation(self):
        """测试提示词生成质量"""
        
        self.print_header("提示词生成质量测试")
        
        # 使用相同的对话历史
        conversation = [
            self.create_message('user', """
            我要创建双均线策略：
            - 短期EMA(10)，长期EMA(30)
            - 金叉做多，死叉平仓
            - 止损2%，止盈4%
            - 4小时K线，ETH/USDT
            """),
            self.create_message('assistant', "理解了您的双均线策略需求"),
            self.create_message('user', "确认生成")
        ]
        
        self.print_test("提示词生成和格式化")
        
        # 提取需求并生成提示词
        requirements = await StrategyRequirementsExtractor.extract_requirements(conversation)
        formatted_prompt = StrategyRequirementsExtractor.format_requirements_prompt(requirements)
        
        print("   📝 生成的提示词内容：")
        print("-" * 40)
        print(formatted_prompt)
        print("-" * 40)
        
        # 验证提示词质量
        prompt_checks = {}
        
        # 检查是否包含用户原始需求
        user_content = conversation[0].content
        original_need_included = any(keyword in formatted_prompt 
                                   for keyword in ['EMA', '10', '30', '金叉', '死叉'])
        
        prompt_checks['原始需求'] = self.print_result(
            "原始需求包含",
            original_need_included,
            f"提示词包含用户描述的关键词"
        )
        
        # 检查技术指标信息
        indicators = requirements.get('indicators', {})
        ema_included = 'EMA' in indicators or any('EMA' in str(v) for v in indicators.values())
        
        prompt_checks['技术指标'] = self.print_result(
            "技术指标信息",
            ema_included,
            f"EMA指标信息包含: {ema_included}"
        )
        
        # 检查风险管理信息
        risk_info = requirements.get('risk_management', {})
        risk_included = len(risk_info) > 0
        
        prompt_checks['风险管理'] = self.print_result(
            "风险管理信息",
            risk_included,
            f"风险管理参数: {risk_info}"
        )
        
        # 检查时间框架和交易对
        timeframe = requirements.get('timeframe')
        trading_pair = requirements.get('trading_pair') 
        trading_info = timeframe and trading_pair
        
        prompt_checks['交易信息'] = self.print_result(
            "交易信息完整",
            trading_info,
            f"时间框架: {timeframe}, 交易对: {trading_pair}"
        )
        
        return prompt_checks

    async def test_edge_cases(self):
        """测试边界情况处理"""
        
        self.print_header("边界情况处理测试")
        
        edge_cases = {}
        
        # 测试1: 空对话历史
        self.print_test("空对话历史处理")
        empty_requirements = await StrategyRequirementsExtractor.extract_requirements([])
        
        edge_cases['空历史'] = self.print_result(
            "空对话历史",
            isinstance(empty_requirements, dict) and len(empty_requirements.get('indicators', {})) == 0,
            f"返回空需求字典: {len(empty_requirements.get('indicators', {}))}"
        )
        
        # 测试2: 只有确认消息
        self.print_test("仅确认消息处理")
        confirm_only = [self.create_message('user', '确认生成代码')]
        confirm_requirements = await StrategyRequirementsExtractor.extract_requirements(confirm_only)
        
        edge_cases['仅确认'] = self.print_result(
            "仅确认消息",
            len(confirm_requirements.get('indicators', {})) == 0,
            f"正确识别无策略内容: {len(confirm_requirements.get('indicators', {}))}"
        )
        
        # 测试3: 非策略对话
        self.print_test("非策略对话处理")
        casual_conversation = [
            self.create_message('user', '你好，今天天气怎么样？'),
            self.create_message('assistant', '我是AI助手，专注于策略生成'),
            self.create_message('user', '好的，确认生成')
        ]
        casual_requirements = await StrategyRequirementsExtractor.extract_requirements(casual_conversation)
        
        edge_cases['非策略对话'] = self.print_result(
            "非策略对话",
            len(casual_requirements.get('indicators', {})) == 0,
            f"正确识别非策略内容: {len(casual_requirements.get('indicators', {}))}"
        )
        
        # 测试4: 大量对话历史
        self.print_test("大量对话历史处理")
        large_conversation = []
        
        # 添加50条消息，只有一部分包含策略信息
        for i in range(48):
            role = 'user' if i % 2 == 0 else 'assistant'
            content = f"这是第{i+1}条普通对话消息"
            large_conversation.append(self.create_message(role, content))
        
        # 在最后添加策略相关内容
        large_conversation.extend([
            self.create_message('user', '我想创建RSI策略，RSI(14)低于30买入，高于70卖出'),
            self.create_message('assistant', '明白，RSI策略已记录，确认生成吗？')
        ])
        
        start_time = time.time()
        large_requirements = await StrategyRequirementsExtractor.extract_requirements(large_conversation)
        processing_time = time.time() - start_time
        
        rsi_extracted = 'RSI' in large_requirements.get('indicators', {})
        performance_good = processing_time < 2.0
        
        edge_cases['大量历史'] = self.print_result(
            "大量对话历史",
            rsi_extracted and performance_good,
            f"RSI提取: {rsi_extracted}, 耗时: {processing_time:.3f}s"
        )
        
        return edge_cases

    async def run_validation(self):
        """运行完整的修复效果验证"""
        
        print("🔍 AI策略生成修复效果专项验证")
        print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 运行所有测试
        context_results = await self.test_context_preservation()
        prompt_results = await self.test_prompt_generation()
        edge_results = await self.test_edge_cases()
        
        # 汇总结果
        all_results = {**context_results, **prompt_results, **edge_results}
        
        # 确保所有值都是布尔型
        all_results = {k: bool(v) for k, v in all_results.items()}
        
        total_time = time.time() - self.start_time
        
        # 生成验证报告
        self.print_header("修复效果验证报告")
        
        print(f"📅 验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  总耗时: {total_time:.3f}秒")
        print(f"🎯 测试项目: {len(all_results)}")
        print(f"✅ 通过项目: {sum(1 for v in all_results.values() if v)}")
        print(f"❌ 失败项目: {sum(1 for v in all_results.values() if not v)}")
        print(f"📈 成功率: {sum(1 for v in all_results.values() if v)/len(all_results)*100:.1f}%")
        
        # 关键修复点验证
        print(f"\n🔧 关键修复点验证:")
        
        key_fixes = {
            '参数提取准确性': context_results.get('MACD参数', False) and context_results.get('RSI参数', False),
            '对话历史传递': context_results.get('背离逻辑', False) and context_results.get('成交量确认', False),
            '提示词生成质量': prompt_results.get('原始需求', False) and prompt_results.get('技术指标', False),
            '边界情况处理': edge_results.get('空历史', False) and edge_results.get('非策略对话', False),
            '性能稳定性': edge_results.get('大量历史', False)
        }
        
        for fix_name, passed in key_fixes.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {fix_name}: {'修复成功' if passed else '需要优化'}")
        
        # 最终结论
        overall_success = sum(key_fixes.values()) / len(key_fixes)
        
        print(f"\n🎯 修复效果总体评估:")
        
        if overall_success >= 0.8:
            print("   🎉 修复完全成功！")
            print("   ✅ 上下文丢失问题已解决")
            print("   ✅ 策略需求提取器工作正常")
            print("   ✅ 对话历史正确传递到策略生成器")
            print("   ✅ 生成的策略应该包含用户描述的所有细节")
            
            print(f"\n💡 后续建议:")
            print("   🚀 可以进行真实的AI策略生成测试")
            print("   📊 建议测试完整的策略生成到回测流程")
            print("   🔄 可以开始集成到WebSocket实时对话系统")
            
        elif overall_success >= 0.6:
            print("   ⚠️  修复部分成功")
            print("   🔧 主要功能正常，部分细节需要优化")
            
            failed_fixes = [name for name, passed in key_fixes.items() if not passed]
            print(f"   📝 需要优化的功能: {', '.join(failed_fixes)}")
            
        else:
            print("   ❌ 修复效果不理想")
            print("   🛠️  建议检查修复逻辑，重新分析问题")
        
        print(f"\n{'='*80}")
        print(f"🏁 验证完成 - 修复效果{'良好' if overall_success >= 0.8 else '需要优化'}")
        print(f"{'='*80}")
        
        return overall_success >= 0.8


async def main():
    """主验证函数"""
    validator = StrategyGenerationFixValidator()
    
    try:
        success = await validator.run_validation()
        exit_code = 0 if success else 1
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ 验证执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())