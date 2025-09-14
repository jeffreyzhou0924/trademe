#!/usr/bin/env python3
"""
Trademe回测系统端到端综合测试
==================================

测试目标：
1. 数据一致性验证 - 相同配置多次回测结果应该完全一致
2. 错误处理验证 - 无效配置应该正确拒绝并给出明确错误信息
3. API端点完整性 - 所有回测相关API端点功能正常
4. WebSocket实时通信 - 实时进度监控和状态管理正常
5. 数据边界条件 - 测试各种边界情况和异常输入

测试场景：
- 场景1：正常OKX数据回测一致性验证
- 场景2：数据验证错误处理机制
- 场景3：WebSocket实时进度监控
- 场景4：策略代码执行验证

Created: 2025-09-14
Author: Claude Code
"""

import asyncio
import json
import time
import websocket
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
import hashlib
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import ssl
import traceback

# 测试配置
BASE_URL = "http://127.0.0.1:8001"
USER_SERVICE_URL = "http://127.0.0.1:3001"
WS_URL = "ws://127.0.0.1:8001"
TEST_USER = {"email": "admin@trademe.com", "password": "admin123456"}

# 测试用MACD策略代码
SAMPLE_STRATEGY_CODE = '''
# MACD策略 - 端到端测试用例
# 当MACD线上穿信号线且MACD值为正时买入，反之卖出

def generate_signals(df):
    import pandas as pd
    import numpy as np
    
    # 计算MACD指标
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    close_prices = df['close']
    macd_line, signal_line, histogram = calculate_macd(close_prices)
    
    # 生成信号
    signals = []
    for i in range(1, len(df)):
        if (macd_line.iloc[i] > signal_line.iloc[i] and 
            macd_line.iloc[i-1] <= signal_line.iloc[i-1] and 
            macd_line.iloc[i] > 0):
            signals.append({'action': 'buy', 'price': df.iloc[i]['close'], 'timestamp': df.iloc[i]['timestamp']})
        elif (macd_line.iloc[i] < signal_line.iloc[i] and 
              macd_line.iloc[i-1] >= signal_line.iloc[i-1] and 
              macd_line.iloc[i] < 0):
            signals.append({'action': 'sell', 'price': df.iloc[i]['close'], 'timestamp': df.iloc[i]['timestamp']})
    
    return signals
'''

@dataclass
class TestResult:
    """测试结果数据类"""
    test_name: str
    success: bool
    message: str
    data: Any = None
    error: str = None
    execution_time: float = 0.0

class BacktestE2ETester:
    """回测系统端到端测试器"""
    
    def __init__(self):
        self.jwt_token = None
        self.test_results = []
        self.websocket_messages = []
        self.ws_connection = None
        self.ws_connected = False
        
    def get_auth_token(self) -> bool:
        """获取JWT认证token"""
        try:
            response = requests.post(
                f"{USER_SERVICE_URL}/api/v1/auth/login",
                json=TEST_USER,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.jwt_token = data['data']['access_token']
                print(f"✅ 成功获取JWT token: {self.jwt_token[:50]}...")
                return True
            else:
                print(f"❌ JWT认证失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ JWT认证异常: {str(e)}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """获取认证头部"""
        return {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
    
    def test_api_endpoint(self, endpoint: str, method: str = "GET", data: dict = None) -> TestResult:
        """测试API端点"""
        start_time = time.time()
        try:
            url = f"{BASE_URL}{endpoint}"
            headers = self.get_auth_headers()
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            
            execution_time = time.time() - start_time
            
            if 200 <= response.status_code < 300:
                return TestResult(
                    test_name=f"{method} {endpoint}",
                    success=True,
                    message=f"API调用成功 ({response.status_code})",
                    data=response.json() if response.content else None,
                    execution_time=execution_time
                )
            else:
                return TestResult(
                    test_name=f"{method} {endpoint}",
                    success=False,
                    message=f"API调用失败 ({response.status_code})",
                    error=response.text,
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = time.time() - start_time
            return TestResult(
                test_name=f"{method} {endpoint}",
                success=False,
                message="API调用异常",
                error=str(e),
                execution_time=execution_time
            )
    
    def test_scenario_1_consistency(self) -> List[TestResult]:
        """场景1: 正常OKX数据回测一致性验证"""
        print("\n🔍 场景1: 正常OKX数据回测一致性验证")
        results = []
        
        # 测试配置
        backtest_config = {
            "strategy_code": SAMPLE_STRATEGY_CODE,
            "symbol": "BTC/USDT",
            "exchange": "OKX",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "initial_capital": 10000,
            "fee_rate": 0.001
        }
        
        # 执行3次相同的回测
        backtest_results = []
        for i in range(3):
            print(f"  🔄 执行第{i+1}次回测...")
            result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", backtest_config)
            results.append(result)
            
            if result.success and result.data:
                # 提取关键指标用于一致性比较
                key_metrics = {
                    'total_return': result.data.get('total_return'),
                    'max_drawdown': result.data.get('max_drawdown'),
                    'sharpe_ratio': result.data.get('sharpe_ratio'),
                    'total_trades': result.data.get('total_trades')
                }
                backtest_results.append(key_metrics)
                print(f"    📊 回测结果: {key_metrics}")
            else:
                print(f"    ❌ 回测{i+1}失败: {result.error}")
            
            time.sleep(2)  # 避免请求过于频繁
        
        # 验证一致性
        if len(backtest_results) >= 2:
            consistency_result = self._check_consistency(backtest_results)
            results.append(consistency_result)
        
        return results
    
    def test_scenario_2_error_handling(self) -> List[TestResult]:
        """场景2: 数据验证错误处理机制"""
        print("\n🚫 场景2: 数据验证错误处理机制")
        results = []
        
        # 测试用例：无效交易所（应该被拒绝）
        invalid_exchange_config = {
            "strategy_code": SAMPLE_STRATEGY_CODE,
            "symbol": "BTC/USDT",
            "exchange": "BINANCE",  # 应该被拒绝，因为数据库中只有OKX数据
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        }
        
        print("  🧪 测试无效交易所处理...")
        result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", invalid_exchange_config)
        result.test_name = "无效交易所错误处理"
        # 期望这个测试返回错误
        if not result.success:
            result.success = True  # 错误是期望的结果
            result.message = f"✅ 正确拒绝无效交易所: {result.error}"
        else:
            result.success = False
            result.message = "❌ 应该拒绝无效交易所但未拒绝"
        results.append(result)
        
        # 测试用例：无效时间范围
        invalid_date_config = {
            "strategy_code": SAMPLE_STRATEGY_CODE,
            "symbol": "BTC/USDT",
            "exchange": "OKX",
            "start_date": "2025-01-01",  # 未来日期
            "end_date": "2025-12-31"
        }
        
        print("  🧪 测试无效时间范围处理...")
        result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", invalid_date_config)
        result.test_name = "无效时间范围错误处理"
        if not result.success:
            result.success = True
            result.message = f"✅ 正确拒绝无效时间范围: {result.error}"
        else:
            result.success = False
            result.message = "❌ 应该拒绝无效时间范围但未拒绝"
        results.append(result)
        
        # 测试用例：无效策略代码
        invalid_strategy_config = {
            "strategy_code": "invalid python code !!!",
            "symbol": "BTC/USDT",
            "exchange": "OKX",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31"
        }
        
        print("  🧪 测试无效策略代码处理...")
        result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", invalid_strategy_config)
        result.test_name = "无效策略代码错误处理"
        if not result.success:
            result.success = True
            result.message = f"✅ 正确拒绝无效策略代码: {result.error}"
        else:
            result.success = False
            result.message = "❌ 应该拒绝无效策略代码但未拒绝"
        results.append(result)
        
        return results
    
    def test_scenario_3_websocket(self) -> List[TestResult]:
        """场景3: WebSocket实时进度监控"""
        print("\n🔌 场景3: WebSocket实时进度监控")
        results = []
        
        try:
            # WebSocket连接测试
            ws_result = self._test_websocket_connection()
            results.append(ws_result)
            
            if ws_result.success:
                # 启动回测并监控WebSocket消息
                backtest_config = {
                    "strategy_code": SAMPLE_STRATEGY_CODE,
                    "symbol": "BTC/USDT",
                    "exchange": "OKX",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-15"  # 较短时间以快速完成
                }
                
                print("  🚀 启动回测并监控WebSocket消息...")
                self.websocket_messages.clear()
                
                # 启动回测
                backtest_result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", backtest_config)
                
                # 等待WebSocket消息
                time.sleep(10)
                
                # 分析WebSocket消息
                ws_analysis = self._analyze_websocket_messages()
                results.append(ws_analysis)
                
        except Exception as e:
            results.append(TestResult(
                test_name="WebSocket测试异常",
                success=False,
                message="WebSocket测试发生异常",
                error=str(e)
            ))
        
        return results
    
    def test_scenario_4_strategy_execution(self) -> List[TestResult]:
        """场景4: 策略代码执行验证"""
        print("\n⚙️ 场景4: 策略代码执行验证")
        results = []
        
        # 测试不同类型的策略代码
        strategies = [
            {
                "name": "MACD策略",
                "code": SAMPLE_STRATEGY_CODE
            },
            {
                "name": "简单移动平均策略",
                "code": '''
def generate_signals(df):
    import pandas as pd
    
    # 计算20日和50日移动平均线
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma50'] = df['close'].rolling(window=50).mean()
    
    signals = []
    for i in range(1, len(df)):
        if df['ma20'].iloc[i] > df['ma50'].iloc[i] and df['ma20'].iloc[i-1] <= df['ma50'].iloc[i-1]:
            signals.append({'action': 'buy', 'price': df.iloc[i]['close'], 'timestamp': df.iloc[i]['timestamp']})
        elif df['ma20'].iloc[i] < df['ma50'].iloc[i] and df['ma20'].iloc[i-1] >= df['ma50'].iloc[i-1]:
            signals.append({'action': 'sell', 'price': df.iloc[i]['close'], 'timestamp': df.iloc[i]['timestamp']})
    
    return signals
'''
            }
        ]
        
        for strategy in strategies:
            print(f"  🧪 测试{strategy['name']}执行...")
            config = {
                "strategy_code": strategy['code'],
                "symbol": "BTC/USDT",
                "exchange": "OKX",
                "start_date": "2024-01-01",
                "end_date": "2024-01-15"
            }
            
            result = self.test_api_endpoint("/api/v1/realtime-backtest/start", "POST", config)
            result.test_name = f"{strategy['name']}执行测试"
            
            if result.success and result.data:
                # 验证返回数据的完整性
                required_fields = ['total_return', 'total_trades', 'win_rate', 'max_drawdown']
                missing_fields = [field for field in required_fields if field not in result.data]
                
                if not missing_fields:
                    result.message = f"✅ {strategy['name']}执行成功，数据完整"
                    print(f"    📊 总收益: {result.data.get('total_return')}, 总交易: {result.data.get('total_trades')}")
                else:
                    result.success = False
                    result.message = f"❌ 数据不完整，缺少字段: {missing_fields}"
            
            results.append(result)
            time.sleep(2)
        
        return results
    
    def _check_consistency(self, results: List[Dict]) -> TestResult:
        """检查回测结果一致性"""
        if len(results) < 2:
            return TestResult(
                test_name="一致性验证",
                success=False,
                message="结果数量不足，无法验证一致性"
            )
        
        # 比较所有结果
        first_result = results[0]
        inconsistencies = []
        
        for i, result in enumerate(results[1:], 1):
            for key, value in first_result.items():
                if key in result and abs(float(value or 0) - float(result[key] or 0)) > 0.001:
                    inconsistencies.append(f"结果{i+1}的{key}不一致: {value} vs {result[key]}")
        
        if inconsistencies:
            return TestResult(
                test_name="回测结果一致性验证",
                success=False,
                message="发现结果不一致",
                error="; ".join(inconsistencies)
            )
        else:
            return TestResult(
                test_name="回测结果一致性验证",
                success=True,
                message="✅ 所有回测结果完全一致",
                data={"consistency_check": "passed", "results_compared": len(results)}
            )
    
    def _test_websocket_connection(self) -> TestResult:
        """测试WebSocket连接"""
        try:
            def on_message(ws, message):
                self.websocket_messages.append({
                    "timestamp": datetime.now().isoformat(),
                    "message": message
                })
                print(f"    📨 WebSocket消息: {message[:100]}...")
            
            def on_open(ws):
                self.ws_connected = True
                print("  ✅ WebSocket连接已建立")
                # 发送认证消息
                auth_message = {
                    "type": "auth",
                    "token": self.jwt_token
                }
                ws.send(json.dumps(auth_message))
            
            def on_error(ws, error):
                print(f"  ❌ WebSocket错误: {error}")
            
            def on_close(ws, close_status_code, close_msg):
                self.ws_connected = False
                print("  🔌 WebSocket连接已关闭")
            
            # 创建WebSocket连接
            ws_url = f"{WS_URL}/ws/backtest-progress"
            print(f"  🔌 连接WebSocket: {ws_url}")
            
            self.ws_connection = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_open=on_open,
                on_error=on_error,
                on_close=on_close
            )
            
            # 在后台运行WebSocket
            ws_thread = threading.Thread(target=self.ws_connection.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # 等待连接建立
            time.sleep(3)
            
            if self.ws_connected:
                return TestResult(
                    test_name="WebSocket连接测试",
                    success=True,
                    message="✅ WebSocket连接成功建立"
                )
            else:
                return TestResult(
                    test_name="WebSocket连接测试",
                    success=False,
                    message="❌ WebSocket连接建立失败"
                )
                
        except Exception as e:
            return TestResult(
                test_name="WebSocket连接测试",
                success=False,
                message="WebSocket连接异常",
                error=str(e)
            )
    
    def _analyze_websocket_messages(self) -> TestResult:
        """分析WebSocket消息"""
        if not self.websocket_messages:
            return TestResult(
                test_name="WebSocket消息分析",
                success=False,
                message="❌ 未收到任何WebSocket消息"
            )
        
        progress_messages = []
        error_messages = []
        completed_messages = []
        
        for msg_data in self.websocket_messages:
            try:
                msg = json.loads(msg_data["message"])
                if msg.get("type") == "progress":
                    progress_messages.append(msg)
                elif msg.get("type") == "error":
                    error_messages.append(msg)
                elif msg.get("type") == "completed":
                    completed_messages.append(msg)
            except:
                pass
        
        analysis = {
            "total_messages": len(self.websocket_messages),
            "progress_messages": len(progress_messages),
            "error_messages": len(error_messages),
            "completed_messages": len(completed_messages)
        }
        
        success = len(progress_messages) > 0  # 至少要有进度消息
        message = f"✅ WebSocket消息分析: {analysis}" if success else f"❌ WebSocket消息分析异常: {analysis}"
        
        return TestResult(
            test_name="WebSocket消息分析",
            success=success,
            message=message,
            data=analysis
        )
    
    def test_api_endpoints_health(self) -> List[TestResult]:
        """测试API端点健康状态"""
        print("\n🏥 API端点健康检查")
        results = []
        
        endpoints = [
            ("/health", "GET"),
            ("/api/v1/strategies", "GET"),
            ("/api/v1/backtests", "GET"),
            ("/api/v1/realtime-backtest/status", "GET"),
            ("/api/v1/market-data/exchanges", "GET")
        ]
        
        for endpoint, method in endpoints:
            print(f"  🔍 检查 {method} {endpoint}")
            result = self.test_api_endpoint(endpoint, method)
            results.append(result)
            
            if result.success:
                print(f"    ✅ {endpoint} 响应正常 ({result.execution_time:.2f}s)")
            else:
                print(f"    ❌ {endpoint} 响应异常: {result.error}")
        
        return results
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """运行comprehensive测试"""
        print("🚀 开始Trademe回测系统端到端综合测试")
        print("=" * 60)
        
        # 获取认证token
        if not self.get_auth_token():
            return {"error": "无法获取认证token，测试终止"}
        
        # 执行所有测试场景
        all_results = []
        
        # API健康检查
        all_results.extend(self.test_api_endpoints_health())
        
        # 场景测试
        all_results.extend(self.test_scenario_1_consistency())
        all_results.extend(self.test_scenario_2_error_handling())
        all_results.extend(self.test_scenario_3_websocket())
        all_results.extend(self.test_scenario_4_strategy_execution())
        
        # 统计结果
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results if r.success)
        failed_tests = total_tests - passed_tests
        
        # 生成报告
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%",
                "test_time": datetime.now().isoformat()
            },
            "detailed_results": [
                {
                    "test_name": r.test_name,
                    "success": r.success,
                    "message": r.message,
                    "execution_time": f"{r.execution_time:.3f}s",
                    "error": r.error,
                    "data": r.data
                }
                for r in all_results
            ],
            "recommendations": self._generate_recommendations(all_results)
        }
        
        self.test_results = all_results
        return report
    
    def _generate_recommendations(self, results: List[TestResult]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        # 分析失败的测试
        failed_tests = [r for r in results if not r.success]
        
        if not failed_tests:
            recommendations.append("✅ 所有测试通过，系统运行正常")
            return recommendations
        
        # 按类别分析问题
        api_failures = [r for r in failed_tests if "API" in r.test_name or "端点" in r.test_name]
        consistency_failures = [r for r in failed_tests if "一致性" in r.test_name]
        websocket_failures = [r for r in failed_tests if "WebSocket" in r.test_name]
        strategy_failures = [r for r in failed_tests if "策略" in r.test_name]
        
        if api_failures:
            recommendations.append("🔧 API端点问题：检查服务运行状态和网络连接")
        
        if consistency_failures:
            recommendations.append("📊 数据一致性问题：检查数据库查询逻辑和缓存机制")
        
        if websocket_failures:
            recommendations.append("🔌 WebSocket问题：检查WebSocket服务和认证机制")
        
        if strategy_failures:
            recommendations.append("⚙️ 策略执行问题：检查策略解析器和执行环境")
        
        # 添加通用建议
        if len(failed_tests) > len(results) * 0.3:
            recommendations.append("🚨 多项测试失败，建议检查系统整体状态")
        
        return recommendations
    
    def print_summary_report(self, report: Dict[str, Any]):
        """打印摘要报告"""
        print("\n" + "=" * 60)
        print("📊 测试结果摘要")
        print("=" * 60)
        
        summary = report["test_summary"]
        print(f"总测试数: {summary['total_tests']}")
        print(f"通过: {summary['passed']} ✅")
        print(f"失败: {summary['failed']} ❌")
        print(f"成功率: {summary['success_rate']}")
        print(f"测试时间: {summary['test_time']}")
        
        print("\n🔍 详细结果:")
        for result in report["detailed_results"]:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['test_name']}: {result['message']}")
            if result["error"]:
                print(f"   错误: {result['error']}")
        
        print("\n💡 修复建议:")
        for rec in report["recommendations"]:
            print(f"  {rec}")
        
        print("=" * 60)

def main():
    """主函数"""
    tester = BacktestE2ETester()
    
    try:
        # 运行comprehensive测试
        report = tester.run_comprehensive_test()
        
        # 打印摘要报告
        tester.print_summary_report(report)
        
        # 保存详细报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"/root/trademe/backtest_e2e_test_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告已保存至: {report_file}")
        
        # 关闭WebSocket连接
        if tester.ws_connection:
            tester.ws_connection.close()
        
        return report
        
    except Exception as e:
        print(f"❌ 测试执行异常: {str(e)}")
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    main()