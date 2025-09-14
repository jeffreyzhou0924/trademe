#!/usr/bin/env python3
"""
测试前端回测确定性修复效果

验证前端调用的 /api/v1/realtime-backtest/start 端点
现在是否默认使用确定性回测引擎，解决相同参数产生不同结果的问题
"""

import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

import asyncio
import aiohttp
import json
from datetime import datetime
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

class FrontendDeterministicBacktestTester:
    """前端确定性回测测试器"""
    
    def __init__(self):
        self.base_url = "http://localhost:8001"
        # 生成测试用JWT token
        self.jwt_token = self._generate_test_jwt()
        
    def _generate_test_jwt(self):
        """生成测试用的JWT token"""
        import subprocess
        try:
            result = subprocess.run([
                'bash', '-c', 
                'JWT_SECRET="trademe_super_secret_jwt_key_for_development_only_32_chars" node -e "'
                'const jwt = require(\"jsonwebtoken\");'
                'const newToken = jwt.sign('
                '  {'
                '    userId: \"6\",'
                '    email: \"admin@trademe.com\",'
                '    membershipLevel: \"professional\",'
                '    type: \"access\"'
                '  },'
                '  process.env.JWT_SECRET,'
                '  {'
                '    expiresIn: \"7d\",'
                '    audience: \"trademe-app\",'
                '    issuer: \"trademe-user-service\"'
                '  }'
                ');'
                'console.log(newToken);'
                '"'
            ], capture_output=True, text=True, cwd='/root/trademe/backend/user-service')
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"JWT生成失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"JWT生成异常: {str(e)}")
            return None
    
    async def test_frontend_deterministic_backtest(self):
        """测试前端回测的确定性"""
        
        print("🔧 前端确定性回测修复验证测试")
        print("=" * 60)
        print(f"📅 测试时间: {datetime.now().isoformat()}")
        print(f"🎯 测试目标: 验证前端调用现在默认使用确定性回测引擎")
        print(f"🔗 测试端点: /api/v1/realtime-backtest/start")
        print()
        
        if not self.jwt_token:
            print("❌ JWT Token生成失败，无法进行API测试")
            return False
        
        # 模拟前端发送的回测请求（不包含确定性参数）
        frontend_backtest_config = {
            "strategy_code": """
# 模拟用户的AI生成策略
class TestStrategy:
    def __init__(self):
        self.ma_short = 5
        self.ma_long = 20
        self.position = 0
    
    def on_data(self, data):
        if len(data.get('close', [])) < self.ma_long:
            return 'HOLD'
        
        closes = data['close']
        ma5 = sum(closes[-self.ma_short:]) / self.ma_short
        ma20 = sum(closes[-self.ma_long:]) / self.ma_long
        
        if ma5 > ma20 and self.position == 0:
            self.position = 1
            return 'BUY'
        elif ma5 < ma20 and self.position == 1:
            self.position = 0
            return 'SELL'
        else:
            return 'HOLD'
""",
            "exchange": "binance",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "initial_capital": 10000.0,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",  # 用户选择的相同时间参数
            "data_type": "kline"
            # 注意：这里故意不包含 deterministic 和 random_seed 参数
            # 来模拟前端的实际请求
        }
        
        print(f"📊 模拟前端请求配置:")
        print(f"   策略类型: MA双均线策略")
        print(f"   时间范围: {frontend_backtest_config['start_date']} - {frontend_backtest_config['end_date']}")
        print(f"   初始资金: ${frontend_backtest_config['initial_capital']:,.2f}")
        print(f"   是否包含确定性参数: ❌ 否 (模拟前端实际情况)")
        print()
        
        # 执行多次回测，验证结果一致性
        task_ids = []
        results = []
        
        async with aiohttp.ClientSession() as session:
            try:
                # 发送3次相同的回测请求
                for i in range(3):
                    print(f"🔄 发送第 {i+1} 次前端回测请求...")
                    
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.jwt_token}'
                    }
                    
                    async with session.post(
                        f"{self.base_url}/api/v1/realtime-backtest/start",
                        json=frontend_backtest_config,
                        headers=headers
                    ) as response:
                        
                        if response.status == 200:
                            result = await response.json()
                            task_id = result.get("task_id")
                            task_ids.append(task_id)
                            print(f"   ✅ 回测任务启动成功: {task_id}")
                        else:
                            error_text = await response.text()
                            print(f"   ❌ 回测请求失败 ({response.status}): {error_text}")
                            return False
                
                print(f"\n⏳ 等待回测任务完成...")
                await asyncio.sleep(10)  # 等待回测执行
                
                # 获取回测结果
                for i, task_id in enumerate(task_ids):
                    print(f"🔍 获取第 {i+1} 次回测结果...")
                    
                    async with session.get(
                        f"{self.base_url}/api/v1/realtime-backtest/result/{task_id}",
                        headers=headers
                    ) as response:
                        
                        if response.status == 200:
                            result = await response.json()
                            
                            # 提取关键结果指标
                            final_value = result.get('final_portfolio_value', 0)
                            trade_count = len(result.get('trades', []))
                            total_return = result.get('total_return', 0)
                            
                            results.append({
                                'run': i + 1,
                                'task_id': task_id,
                                'final_value': final_value,
                                'trade_count': trade_count,
                                'total_return': total_return,
                                'deterministic': result.get('deterministic', False)
                            })
                            
                            print(f"   📊 第{i+1}次: 最终价值=${final_value:.2f}, 交易数={trade_count}, 收益率={total_return:.2f}%, 确定性={result.get('deterministic', False)}")
                        else:
                            print(f"   ❌ 获取结果失败: {response.status}")
                            results.append({
                                'run': i + 1,
                                'task_id': task_id,
                                'final_value': 'ERROR',
                                'trade_count': 'ERROR',
                                'total_return': 'ERROR',
                                'deterministic': False
                            })
                
            except Exception as e:
                logger.error(f"API请求异常: {str(e)}")
                return False
        
        # 分析结果一致性
        return self._analyze_frontend_results(results, frontend_backtest_config)
    
    def _analyze_frontend_results(self, results, config):
        """分析前端回测结果的一致性"""
        
        print(f"\n📈 前端回测结果一致性分析:")
        print("-" * 40)
        
        valid_results = [r for r in results if r['final_value'] != 'ERROR']
        
        if len(valid_results) < 2:
            print(f"   ❌ 有效结果不足，无法分析一致性")
            return False
        
        # 检查结果一致性
        first_result = valid_results[0]
        
        value_consistent = all(abs(r['final_value'] - first_result['final_value']) < 0.01 for r in valid_results)
        trade_consistent = all(r['trade_count'] == first_result['trade_count'] for r in valid_results)
        return_consistent = all(abs(r['total_return'] - first_result['total_return']) < 0.01 for r in valid_results)
        deterministic_enabled = all(r['deterministic'] for r in valid_results)
        
        print(f"   最终价值一致性: {'✅ 完全一致' if value_consistent else '❌ 存在差异'}")
        print(f"   交易次数一致性: {'✅ 完全一致' if trade_consistent else '❌ 存在差异'}")  
        print(f"   收益率一致性: {'✅ 完全一致' if return_consistent else '❌ 存在差异'}")
        print(f"   确定性模式启用: {'✅ 已启用' if deterministic_enabled else '❌ 未启用'}")
        
        if not value_consistent:
            values = [r['final_value'] for r in valid_results]
            print(f"   价值变异范围: ${min(values):.2f} - ${max(values):.2f}")
        
        print(f"\n🎯 修复效果评估:")
        
        if value_consistent and trade_consistent and return_consistent and deterministic_enabled:
            print(f"   ✅ 前端确定性修复成功！")
            print(f"   🔧 相同参数现在产生完全相同的结果")
            print(f"   📈 确定性模式已自动启用")
            print(f"   🎉 用户报告的问题已完全解决")
            
            # 保存成功报告
            success_report = {
                'timestamp': datetime.now().isoformat(),
                'test_type': 'frontend_deterministic_backtest',
                'status': 'SUCCESS',
                'user_issue_resolved': True,
                'config_used': config,
                'results_summary': {
                    'consistent_final_value': first_result['final_value'],
                    'consistent_trade_count': first_result['trade_count'],
                    'consistent_return': first_result['total_return'],
                    'deterministic_enabled': True
                },
                'conclusion': '前端回测现在默认使用确定性引擎，相同参数保证相同结果'
            }
            
            with open('/root/trademe/backend/trading-service/frontend_deterministic_fix_success.json', 'w', encoding='utf-8') as f:
                json.dump(success_report, f, indent=2, ensure_ascii=False)
            
            return True
        else:
            print(f"   ❌ 前端确定性修复失败！")
            print(f"   🚨 相同参数仍然产生不同结果")
            print(f"   🔧 需要进一步调试前端API集成")
            
            return False


async def main():
    """主测试函数"""
    tester = FrontendDeterministicBacktestTester()
    success = await tester.test_frontend_deterministic_backtest()
    
    print(f"\n🏆 最终测试结果: {'✅ 成功' if success else '❌ 失败'}")
    
    if success:
        print(f"🎊 用户问题已解决：\"我选择了两次相同的时间,回测结果还是不一样\" ✅")
    else:
        print(f"⚠️ 用户问题仍存在，需要进一步调试")


if __name__ == "__main__":
    asyncio.run(main())