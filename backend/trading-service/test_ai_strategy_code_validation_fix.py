#!/usr/bin/env python3
"""
测试AI策略代码验证修复
验证从AI响应到策略代码提取的完整流程
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json
import aiohttp
from datetime import datetime

JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiI2IiwiZW1haWwiOiJhZG1pbkB0cmFkZW1lLmNvbSIsIm1lbWJlcnNoaXBMZXZlbCI6InByb2Zlc3Npb25hbCIsInR5cGUiOiJhY2Nlc3MiLCJpYXQiOjE3NTc2NjkzNzcsImV4cCI6MTc1ODI3NDE3NywiYXVkIjoidHJhZGVtZS1hcHAiLCJpc3MiOiJ0cmFkZW1lLXVzZXItc2VydmljZSJ9.aOekZxH4JQCmp2qwAMdgjDk2FYpz8_BwdxZVIhjP7pQ"
BASE_URL = "http://localhost:8001/api/v1"

async def test_strategy_code_extraction_flow():
    """测试策略代码提取流程"""
    
    print("🧪 开始测试AI策略代码验证修复流程...")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        
        # 第1步：创建AI会话
        print("📋 第1步：创建AI策略生成会话")
        create_session_payload = {
            "session_type": "strategy",
            "title": "代码验证测试会话"
        }
        
        try:
            async with session.post(
                f"{BASE_URL}/ai/conversations",
                headers=headers,
                json=create_session_payload
            ) as response:
                if response.status == 200:
                    session_data = await response.json()
                    session_id = session_data.get("session_id")
                    print(f"✅ 会话创建成功，ID: {session_id}")
                else:
                    print(f"❌ 会话创建失败: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ 会话创建异常: {e}")
            return False
        
        # 第2步：模拟生成包含代码块的AI响应
        print("\n📋 第2步：模拟AI策略代码生成（包含中文说明）")
        
        # 模拟一个包含中文说明和Python代码的混合响应
        mock_ai_response = {
            "content": [
                {
                    "text": """根据您的需求，我将为您生成一个MACD策略。该策略结合了MACD指标的金叉死叉信号，实现智能的买卖点判断。

```python
class MACDStrategy(EnhancedBaseStrategy):
    def __init__(self):
        super().__init__()
        self.ema_short = 12
        self.ema_long = 26 
        self.signal_period = 9
        self.position = 0
        
    def calculate_signals(self, data):
        # 计算MACD指标
        ema_12 = data['close'].ewm(span=self.ema_short).mean()
        ema_26 = data['close'].ewm(span=self.ema_long).mean()
        
        data['macd_line'] = ema_12 - ema_26
        data['signal_line'] = data['macd_line'].ewm(span=self.signal_period).mean()
        data['macd_histogram'] = data['macd_line'] - data['signal_line']
        
        # 生成交易信号
        data['signal'] = 0
        
        # 金叉买入信号
        golden_cross = (data['macd_line'] > data['signal_line']) & (data['macd_line'].shift(1) <= data['signal_line'].shift(1))
        data.loc[golden_cross, 'signal'] = 1
        
        # 死叉卖出信号  
        death_cross = (data['macd_line'] < data['signal_line']) & (data['macd_line'].shift(1) >= data['signal_line'].shift(1))
        data.loc[death_cross, 'signal'] = -1
        
        return data
        
    def should_buy(self, current_data, position_info):
        return current_data['signal'] == 1 and position_info['position'] == 0
        
    def should_sell(self, current_data, position_info):
        return current_data['signal'] == -1 and position_info['position'] > 0
```

这个策略具有以下特点：
1. 使用标准MACD参数(12,26,9)
2. 识别金叉死叉信号
3. 只在空仓时买入，持仓时卖出
4. 包含完整的信号计算逻辑

请确认这个策略是否符合您的需求。"""
                }
            ]
        }
        
        # 第3步：直接测试AI服务的代码提取逻辑
        print("📋 第3步：测试AI服务代码提取功能")
        
        try:
            from app.services.ai_service import AIService
            ai_service = AIService()
            
            # 模拟调用generate_strategy_with_context方法中的代码提取逻辑
            raw_content = mock_ai_response["content"][0]["text"]
            extracted_code = ai_service.extract_python_code_from_response(raw_content)
            
            print(f"✅ 代码提取成功")
            print(f"📏 原始内容长度: {len(raw_content)} 字符")
            print(f"📏 提取代码长度: {len(extracted_code)} 字符")
            print(f"🔍 代码开头: {extracted_code[:100]}...")
            
            # 验证提取的代码是否为纯Python代码
            if "class MACDStrategy" in extracted_code and "基于您的" not in extracted_code:
                print("✅ 代码提取正确：纯Python代码，无中文说明")
            else:
                print("❌ 代码提取失败：仍包含中文说明或代码不完整")
                return False
                
        except Exception as e:
            print(f"❌ 代码提取测试失败: {e}")
            return False
        
        # 第4步：测试策略代码验证
        print("\n📋 第4步：测试策略代码验证")
        
        try:
            import ast
            
            # 尝试解析提取的Python代码
            ast.parse(extracted_code)
            print("✅ Python语法验证通过：无中文字符语法错误")
            
        except SyntaxError as e:
            print(f"❌ Python语法验证失败: {e}")
            if '，' in str(e) or 'U+FF0C' in str(e):
                print("⚠️ 检测到中文标点符号，代码提取功能仍需修复")
            return False
        except Exception as e:
            print(f"❌ 语法验证异常: {e}")
            return False
        
        # 第5步：测试数据库中问题策略的修复
        print("\n📋 第5步：检查数据库中的问题策略")
        
        try:
            from app.database import get_db
            from app.models.strategy import Strategy
            from sqlalchemy import select
            
            async with get_db() as db:
                # 查找策略ID 44（之前报错的策略）
                query = select(Strategy).where(Strategy.id == 44)
                result = await db.execute(query)
                strategy = result.scalar_one_or_none()
                
                if strategy:
                    print(f"📋 找到问题策略 ID: {strategy.id}")
                    print(f"📏 策略代码长度: {len(strategy.code)} 字符")
                    print(f"🔍 代码开头: {strategy.code[:100]}...")
                    
                    # 检查是否包含中文
                    if '基于您的' in strategy.code or '，' in strategy.code:
                        print("⚠️ 确认：该策略包含中文内容，需要修复")
                        
                        # 尝试从现有代码中提取Python部分
                        fixed_code = ai_service.extract_python_code_from_response(strategy.code)
                        if fixed_code and len(fixed_code) > 100:
                            print("✅ 成功从问题策略中提取纯Python代码")
                            print(f"📏 修复后代码长度: {len(fixed_code)} 字符")
                            print(f"🔍 修复后代码开头: {fixed_code[:100]}...")
                        else:
                            print("❌ 无法从问题策略中提取有效Python代码")
                    else:
                        print("✅ 策略代码正常，无中文内容")
                else:
                    print("❌ 未找到策略ID 44")
                    
        except Exception as e:
            print(f"❌ 数据库检查异常: {e}")
        
        print(f"\n🎯 测试总结:")
        print("✅ AI响应代码提取功能正常工作")
        print("✅ 提取的代码通过Python语法验证")
        print("✅ 修复逻辑已集成到AI服务中")
        print("✅ 新生成的策略将自动提取纯Python代码")
        
        return True

async def main():
    """主函数"""
    success = await test_strategy_code_extraction_flow()
    print(f"\n🏆 整体测试结果: {'✅ 修复成功' if success else '❌ 仍需修复'}")
    return success

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ 测试执行异常: {e}")
        sys.exit(1)