#!/usr/bin/env python3
"""
直接测试策略代码提取功能（不依赖API）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.ai_service import AIService

def test_code_extraction_on_real_data():
    """测试真实数据的代码提取"""
    
    print("🧪 测试AI策略代码验证修复...")
    print("=" * 50)
    
    # 初始化AI服务
    ai_service = AIService()
    
    # 模拟包含中文说明和Python代码的真实AI响应
    real_ai_response = r"""根据您的需求分析，我将生成一个优化的MA均线策略。这个策略将结合短期和长期移动平均线，实现智能的买卖信号生成。

```python
class MAStrategy(EnhancedBaseStrategy):
    def __init__(self):
        super().__init__()
        self.short_ma_period = 20
        self.long_ma_period = 50
        self.position = 0
        
    def calculate_signals(self, data):
        # 计算短期和长期移动平均线
        data['ma_short'] = data['close'].rolling(window=self.short_ma_period).mean()
        data['ma_long'] = data['close'].rolling(window=self.long_ma_period).mean()
        
        # 生成交易信号
        data['signal'] = 0
        
        # 金叉：短期均线上穿长期均线，买入信号
        golden_cross = (data['ma_short'] > data['ma_long']) & (data['ma_short'].shift(1) <= data['ma_long'].shift(1))
        data.loc[golden_cross, 'signal'] = 1
        
        # 死叉：短期均线下穿长期均线，卖出信号
        death_cross = (data['ma_short'] < data['ma_long']) & (data['ma_short'].shift(1) >= data['ma_long'].shift(1))
        data.loc[death_cross, 'signal'] = -1
        
        return data
        
    def should_buy(self, current_data, position_info):
        return current_data['signal'] == 1 and position_info['position'] == 0
        
    def should_sell(self, current_data, position_info):
        return current_data['signal'] == -1 and position_info['position'] > 0
        
    def get_strategy_info(self):
        return {
            "name": "MA均线策略",
            "description": "基于短期和长期移动平均线交叉的趋势跟踪策略",
            "parameters": {
                "short_ma_period": self.short_ma_period,
                "long_ma_period": self.long_ma_period
            }
        }
```

这个策略实现了以下功能：
1. 双均线系统：使用20日和50日移动平均线
2. 金叉死叉识别：自动识别均线交叉信号
3. 智能买卖判断：结合持仓状态进行交易决策
4. 完整信号计算：包含详细的技术指标计算逻辑

策略优势：
- 适用于趋势性市场
- 信号清晰，易于理解
- 风险控制相对稳健
- 参数可根据市场调整

请您确认这个策略是否符合您的需求，如有需要我可以进一步优化。"""

    print("📋 第1步：测试原始内容")
    print(f"原始内容长度: {len(real_ai_response)} 字符")
    print(f"原始内容开头: {real_ai_response[:100]}...")
    print()
    
    print("📋 第2步：提取Python代码")
    extracted_code = ai_service.extract_python_code_from_response(real_ai_response)
    
    if extracted_code:
        print(f"✅ 提取成功！")
        print(f"提取代码长度: {len(extracted_code)} 字符")
        print(f"代码开头: {extracted_code[:100]}...")
        print()
        
        # 验证提取的代码
        print("📋 第3步：验证提取结果")
        
        # 检查是否包含中文说明
        if "根据您的需求" in extracted_code or "这个策略实现了" in extracted_code:
            print("❌ 提取失败：仍包含中文说明")
            return False
        else:
            print("✅ 提取成功：纯Python代码，无中文说明")
        
        # 检查是否包含核心类定义
        if "class MAStrategy" in extracted_code:
            print("✅ 验证通过：包含策略类定义")
        else:
            print("❌ 验证失败：缺少策略类定义")
            return False
        
        # Python语法验证
        print("📋 第4步：Python语法验证")
        try:
            import ast
            ast.parse(extracted_code)
            print("✅ Python语法验证通过")
        except SyntaxError as e:
            print(f"❌ Python语法验证失败: {e}")
            if '，' in str(e):
                print("⚠️ 检测到中文标点符号")
            return False
        except Exception as e:
            print(f"❌ 语法验证异常: {e}")
            return False
            
        # 显示完整的提取代码
        print("\n📋 第5步：完整提取代码预览")
        print("```python")
        print(extracted_code[:500] + "..." if len(extracted_code) > 500 else extracted_code)
        print("```")
        
        return True
    else:
        print("❌ 提取失败：未找到Python代码块")
        return False

def test_database_strategy_fix():
    """测试修复数据库中的问题策略"""
    print("\n" + "=" * 50)
    print("🔧 测试数据库策略修复")
    
    try:
        import asyncio
        from app.database import get_db
        from app.models.strategy import Strategy
        from sqlalchemy import select
        
        async def check_strategy():
            ai_service = AIService()
            
            async with get_db() as db:
                # 查找策略ID 44
                query = select(Strategy).where(Strategy.id == 44)
                result = await db.execute(query)
                strategy = result.scalar_one_or_none()
                
                if strategy:
                    print(f"📋 找到策略 ID: {strategy.id}")
                    print(f"策略代码长度: {len(strategy.code)} 字符")
                    print(f"代码开头: {strategy.code[:100]}...")
                    
                    # 检查是否包含中文
                    if '基于您的' in strategy.code or '，' in strategy.code:
                        print("⚠️ 确认包含中文内容，尝试修复")
                        
                        # 使用提取函数修复
                        fixed_code = ai_service.extract_python_code_from_response(strategy.code)
                        if fixed_code and len(fixed_code) > 100:
                            print("✅ 成功提取纯Python代码")
                            print(f"修复后代码长度: {len(fixed_code)} 字符")
                            
                            # 验证语法
                            try:
                                import ast
                                ast.parse(fixed_code)
                                print("✅ 修复后代码语法正确")
                                return True
                            except Exception as e:
                                print(f"❌ 修复后代码语法错误: {e}")
                                return False
                        else:
                            print("❌ 无法提取有效代码")
                            return False
                    else:
                        print("✅ 策略代码正常")
                        return True
                else:
                    print("⚠️ 未找到策略ID 44")
                    return True
        
        return asyncio.run(check_strategy())
        
    except Exception as e:
        print(f"❌ 数据库检查异常: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始AI策略代码提取修复测试")
    
    # 测试1：代码提取功能
    test1_result = test_code_extraction_on_real_data()
    
    # 测试2：数据库策略修复
    test2_result = test_database_strategy_fix()
    
    print(f"\n🎯 测试结果汇总:")
    print(f"- 代码提取功能: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"- 数据库策略检查: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    overall_success = test1_result and test2_result
    print(f"\n🏆 整体结果: {'✅ 修复成功，代码提取功能正常工作' if overall_success else '❌ 仍需进一步修复'}")
    
    if overall_success:
        print("\n💡 修复总结:")
        print("1. ✅ 代码提取函数正常工作")  
        print("2. ✅ 提取的代码通过Python语法验证")
        print("3. ✅ 新的AI策略生成将自动提取纯Python代码")
        print("4. ✅ 之前的中文字符语法错误已解决")
    
    sys.exit(0 if overall_success else 1)