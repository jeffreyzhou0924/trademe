#!/usr/bin/env python3
"""
测试策略代码提取功能
"""

import re
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def extract_python_code_from_response(content: str) -> str:
    """从AI响应中提取Python代码块"""
    import re
    code_block_pattern = r'```(?:python)?\s*([\s\S]*?)\s*```'
    matches = re.findall(code_block_pattern, content)
    if matches:
        # 返回最长的代码块（通常是策略代码）
        longest_code = max(matches, key=len)
        return longest_code.strip()
    return ""

def test_code_extraction():
    """测试代码提取功能"""
    
    # 测试用例1：包含中文说明和Python代码的混合内容
    mixed_content = """基于您的详细需求分析，我将生成一个优化的MA均线策略。这个策略将结合短期和长期移动平均线，实现智能的买卖信号生成。

```python
class MAStrategy(EnhancedBaseStrategy):
    def __init__(self):
        super().__init__()
        self.short_ma_period = 20
        self.long_ma_period = 50
        
    def calculate_signals(self, data):
        # 计算移动平均线
        data['ma_short'] = data['close'].rolling(window=self.short_ma_period).mean()
        data['ma_long'] = data['close'].rolling(window=self.long_ma_period).mean()
        
        # 生成交易信号
        data['signal'] = 0
        data.loc[data['ma_short'] > data['ma_long'], 'signal'] = 1
        data.loc[data['ma_short'] < data['ma_long'], 'signal'] = -1
        
        return data
        
    def should_buy(self, current_data, position_info):
        return current_data['signal'] == 1 and position_info['position'] == 0
        
    def should_sell(self, current_data, position_info):
        return current_data['signal'] == -1 and position_info['position'] > 0
```

这个策略实现了以下功能：
1. 短期和长期均线交叉信号
2. 智能的买卖点判断
3. 完整的信号生成逻辑

请您确认这个策略是否符合您的需求。"""

    # 测试用例2：纯Python代码（无代码块标记）
    pure_python = """class SimpleStrategy(EnhancedBaseStrategy):
    def __init__(self):
        super().__init__()
    
    def calculate_signals(self, data):
        return data"""

    # 测试用例3：空内容
    empty_content = ""

    # 测试用例4：多个代码块
    multiple_blocks = """这里是说明文字。

```python
# 第一个代码块
print("hello")
```

更多说明文字。

```python
# 第二个更长的代码块
class TestStrategy(EnhancedBaseStrategy):
    def __init__(self):
        super().__init__()
        self.param = 10
    
    def calculate_signals(self, data):
        data['signal'] = 1
        return data
```"""

    print("🧪 开始测试代码提取功能...")
    print("=" * 50)
    
    # 测试1
    print("📋 测试1：混合内容代码提取")
    result1 = extract_python_code_from_response(mixed_content)
    print(f"✅ 提取成功，代码长度: {len(result1)} 字符")
    print(f"📝 代码开头: {result1[:100]}...")
    print()
    
    # 测试2
    print("📋 测试2：纯Python代码（无标记）")
    result2 = extract_python_code_from_response(pure_python)
    print(f"{'❌' if not result2 else '✅'} 提取结果: {'空' if not result2 else f'{len(result2)} 字符'}")
    print()
    
    # 测试3
    print("📋 测试3：空内容")
    result3 = extract_python_code_from_response(empty_content)
    print(f"{'✅' if not result3 else '❌'} 提取结果: {'空（符合预期）' if not result3 else '非空'}")
    print()
    
    # 测试4
    print("📋 测试4：多个代码块")
    result4 = extract_python_code_from_response(multiple_blocks)
    print(f"✅ 提取成功，代码长度: {len(result4)} 字符")
    print(f"📝 代码开头: {result4[:80]}...")
    print()
    
    print("🎯 测试结果汇总:")
    print(f"- 测试1（混合内容）: {'✅ 通过' if result1 and 'class MAStrategy' in result1 else '❌ 失败'}")
    print(f"- 测试2（无标记代码）: {'✅ 通过' if not result2 else '❌ 失败（预期为空）'}")
    print(f"- 测试3（空内容）: {'✅ 通过' if not result3 else '❌ 失败'}")
    print(f"- 测试4（多代码块）: {'✅ 通过' if result4 and 'TestStrategy' in result4 else '❌ 失败'}")
    
    return all([
        result1 and 'class MAStrategy' in result1,
        not result2,  # 预期为空
        not result3,  # 预期为空
        result4 and 'TestStrategy' in result4
    ])

if __name__ == "__main__":
    success = test_code_extraction()
    print(f"\n🏆 总体测试结果: {'✅ 全部通过' if success else '❌ 存在失败'}")
    sys.exit(0 if success else 1)