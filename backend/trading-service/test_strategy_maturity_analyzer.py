"""
策略成熟度分析器测试脚本
测试不同成熟度级别的策略输入，验证评分算法的准确性
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/root/trademe/backend/trading-service')

from app.services.strategy_maturity_analyzer import StrategyMaturityAnalyzer


async def test_maturity_analyzer():
    """测试策略成熟度分析器"""
    
    analyzer = StrategyMaturityAnalyzer()
    
    # 测试用例1: 初步想法 (预期分数: 0-30)
    test_case_1 = [
        {"role": "user", "content": "我想做个交易策略"},
        {"role": "user", "content": "能帮我赚钱吗"}
    ]
    
    # 测试用例2: 基础框架 (预期分数: 31-50)  
    test_case_2 = [
        {"role": "user", "content": "我想用RSI指标做个反转策略"},
        {"role": "user", "content": "当RSI超买的时候卖出，超卖的时候买入"},
        {"role": "user", "content": "用1小时的时间周期"}
    ]
    
    # 测试用例3: 相对完善 (预期分数: 51-70)
    test_case_3 = [
        {"role": "user", "content": "我要创建一个双均线交叉策略"},
        {"role": "user", "content": "使用10日均线和20日均线，当短期均线上穿长期均线时买入"},
        {"role": "user", "content": "当短期均线下穿长期均线时卖出"},
        {"role": "user", "content": "设置2%的止损，3%的止盈"},
        {"role": "user", "content": "适用于1小时K线图，主要交易BTCUSDT"}
    ]
    
    # 测试用例4: 成熟可用 (预期分数: 71-85)
    test_case_4 = [
        {"role": "user", "content": "我需要一个MACD+RSI组合策略"},
        {"role": "user", "content": "买入条件：MACD金叉且RSI从超卖区域回升到50以上"},
        {"role": "user", "content": "卖出条件：MACD死叉或RSI超买到70以上"},
        {"role": "user", "content": "MACD参数：快线12，慢线26，信号线9"},
        {"role": "user", "content": "RSI参数：周期14，超买70，超卖30"},
        {"role": "user", "content": "风险管理：单笔风险2%，止损1.5%，止盈盈亏比1:2"},
        {"role": "user", "content": "仓位管理：每次使用账户资金的10%"},
        {"role": "user", "content": "适用于15分钟图，趋势市场效果更好"},
        {"role": "user", "content": "期望年化收益15-25%，最大回撤控制在10%以内"}
    ]
    
    # 测试用例5: 完美策略 (预期分数: 86-100)
    test_case_5 = [
        {"role": "user", "content": "设计一个多时间框架趋势跟踪策略"},
        {"role": "user", "content": "主图表：1小时，确认大趋势方向"},
        {"role": "user", "content": "入场图表：15分钟，寻找精确入场点"},
        {"role": "user", "content": "技术指标组合：EMA21+EMA55确定趋势，RSI14避免极端位置入场"},
        {"role": "user", "content": "买入信号：1h EMA21上穿EMA55，15m价格回踩EMA21获得支撑，RSI>30且<70"},
        {"role": "user", "content": "卖出信号：价格跌破EMA21，或RSI超买后出现背离"},
        {"role": "user", "content": "风险控制：止损设置为入场价格的2%，动态止盈采用EMA21作为止盈线"},
        {"role": "user", "content": "仓位管理：凯利公式计算，单笔风险1.5%，最大总仓位30%"},
        {"role": "user", "content": "适用市场：BTC、ETH等主流币种，趋势明显的市场环境"},
        {"role": "user", "content": "过滤条件：避开重大新闻发布时间，成交量低于20日均量50%时不交易"},
        {"role": "user", "content": "回测验证：使用过去2年数据，期望夏普率>1.5，年化收益20%+，最大回撤<12%"},
        {"role": "user", "content": "优化方向：可调整EMA周期参数，RSI阈值，止损止盈比例"}
    ]
    
    test_cases = [
        ("初步想法", test_case_1),
        ("基础框架", test_case_2),
        ("相对完善", test_case_3),
        ("成熟可用", test_case_4),
        ("完美策略", test_case_5)
    ]
    
    print("🧪 策略成熟度分析器测试开始\n")
    print("=" * 80)
    
    for case_name, conversation in test_cases:
        print(f"\n📊 测试用例: {case_name}")
        print("-" * 50)
        
        # 分析最后一条消息作为当前消息
        current_message = conversation[-1]["content"]
        history = conversation[:-1]
        
        # 执行分析
        result = await analyzer.analyze_strategy_maturity(history, current_message)
        
        # 输出结果
        print(f"📈 总分: {result['total_score']:.1f}/100")
        print(f"🎯 成熟度等级: {result['maturity_level']}")
        print(f"✅ 可生成代码: {result['ready_for_generation']}")
        print(f"🔄 需用户确认: {result['requires_confirmation']}")
        
        print(f"\n📋 各维度得分:")
        for dimension, score in result['dimension_scores'].items():
            dimension_name = {
                'strategy_logic_clarity': '策略逻辑清晰度',
                'parameters_completeness': '参数完整性',
                'risk_management': '风险管理',
                'market_context': '市场环境',
                'validation_readiness': '验证就绪度'
            }.get(dimension, dimension)
            
            max_score = analyzer.maturity_criteria[dimension]['weight']
            print(f"  • {dimension_name}: {score:.1f}/{max_score}")
        
        print(f"\n🔍 识别的策略信息:")
        strategy_info = result['strategy_info']
        if strategy_info.get('strategy_type'):
            print(f"  • 策略类型: {strategy_info['strategy_type']}")
        if strategy_info.get('indicators'):
            print(f"  • 技术指标: {', '.join(strategy_info['indicators'])}")
        if strategy_info.get('timeframe'):
            print(f"  • 时间周期: {strategy_info['timeframe']}")
        if strategy_info.get('entry_conditions'):
            print(f"  • 买入条件: {len(strategy_info['entry_conditions'])}个")
        if strategy_info.get('exit_conditions'):
            print(f"  • 卖出条件: {len(strategy_info['exit_conditions'])}个")
        
        if result.get('missing_elements'):
            print(f"\n❌ 缺失要素: {', '.join(result['missing_elements'])}")
        
        if result.get('improvement_suggestions'):
            print(f"\n💡 改进建议:")
            for suggestion in result['improvement_suggestions'][:3]:
                priority_icon = {
                    'critical': '🔴',
                    'high': '🟡', 
                    'medium': '🟢'
                }.get(suggestion['priority'], '⚪')
                print(f"  {priority_icon} {suggestion['suggestion']}")
        
        print("\n" + "=" * 80)
    
    print("\n✅ 所有测试用例完成！")


async def test_edge_cases():
    """测试边界情况"""
    
    analyzer = StrategyMaturityAnalyzer()
    
    print("\n🔬 边界情况测试:")
    print("-" * 50)
    
    # 测试空输入
    result1 = await analyzer.analyze_strategy_maturity([], "")
    print(f"空输入测试: 得分 {result1['total_score']:.1f}, 等级 {result1['maturity_level']}")
    
    # 测试纯数字输入
    result2 = await analyzer.analyze_strategy_maturity([], "12345 67890")
    print(f"数字输入测试: 得分 {result2['total_score']:.1f}, 等级 {result2['maturity_level']}")
    
    # 测试无关内容
    result3 = await analyzer.analyze_strategy_maturity([], "今天天气很好，我想吃火锅")
    print(f"无关内容测试: 得分 {result3['total_score']:.1f}, 等级 {result3['maturity_level']}")
    
    # 测试技术词汇堆积
    technical_spam = "RSI MACD MA EMA BOLL KDJ 买入 卖出 止损 止盈 趋势 反转"
    result4 = await analyzer.analyze_strategy_maturity([], technical_spam)
    print(f"技术词汇堆积测试: 得分 {result4['total_score']:.1f}, 等级 {result4['maturity_level']}")


if __name__ == "__main__":
    asyncio.run(test_maturity_analyzer())
    asyncio.run(test_edge_cases())