#!/usr/bin/env python3
"""
AI策略回测API端点集成测试
测试实际的HTTP API端点功能
"""

import requests
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any


class APIEndpointTester:
    """API端点测试器"""
    
    def __init__(self, base_url: str = "http://43.167.252.120:8001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        self.auth_token = None
        
    def setup_auth(self):
        """设置认证令牌"""
        try:
            # 使用测试用户登录获取token
            login_url = "http://43.167.252.120/api/v1/auth/login"
            login_data = {
                "email": "publictest@example.com",
                "password": "PublicTest123!"
            }
            
            response = requests.post(login_url, json=login_data)
            if response.status_code == 200:
                result = response.json()
                # 检查返回的数据结构
                if result.get("success") and result.get("data"):
                    self.auth_token = result["data"].get("access_token")
                else:
                    self.auth_token = result.get("access_token")
                
                if self.auth_token:
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.auth_token}"
                    })
                    print("✅ 认证成功，获取到访问令牌")
                    return True
            
            print(f"❌ 认证失败: {response.status_code} - {response.text}")
            return False
            
        except Exception as e:
            print(f"❌ 认证异常: {str(e)}")
            return False
    
    def test_endpoint(self, name: str, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """测试单个API端点"""
        start_time = time.time()
        url = f"{self.base_url}/api/v1{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            execution_time = time.time() - start_time
            
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "status_code": response.status_code,
                "success": 200 <= response.status_code < 300,
                "execution_time": execution_time,
                "response_size": len(response.content),
                "content_type": response.headers.get("content-type", ""),
                "error_message": None
            }
            
            # 尝试解析JSON响应
            try:
                result["response_data"] = response.json()
            except:
                result["response_data"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
            
            if not result["success"]:
                result["error_message"] = f"HTTP {response.status_code}: {response.text[:100]}"
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "status_code": 0,
                "success": False,
                "execution_time": execution_time,
                "response_size": 0,
                "content_type": "",
                "error_message": str(e),
                "response_data": None
            }
        
        self.test_results.append(result)
        
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status} {name} ({result['execution_time']:.3f}s) - {result['status_code']}")
        if not result["success"]:
            print(f"    错误: {result['error_message']}")
        
        return result
    
    def run_api_tests(self):
        """运行API测试套件"""
        print("🚀 开始API端点集成测试")
        print("=" * 60)
        
        # 设置认证
        if not self.setup_auth():
            print("❌ 无法获取认证令牌，跳过需要认证的测试")
        
        # 测试AI相关端点
        print("\n📡 测试AI相关API端点:")
        
        # 1. 获取AI会话列表
        self.test_endpoint(
            "获取AI会话列表",
            "GET",
            "/ai/sessions?ai_mode=trader"
        )
        
        # 2. 创建AI会话
        session_data = {
            "name": f"测试会话_{uuid.uuid4().hex[:8]}",
            "ai_mode": "trader",
            "session_type": "strategy",
            "description": "集成测试会话"
        }
        create_result = self.test_endpoint(
            "创建AI会话",
            "POST",
            "/ai/sessions",
            session_data
        )
        
        session_id = None
        if create_result["success"] and create_result["response_data"]:
            session_id = create_result["response_data"].get("session_id")
        
        # 3. 发送AI聊天消息（如果有会话ID）
        if session_id:
            chat_data = {
                "content": "请帮我设计一个简单的MACD策略",
                "session_id": session_id,
                "ai_mode": "trader",
                "session_type": "strategy"
            }
            self.test_endpoint(
                "发送AI聊天消息",
                "POST",
                "/ai/chat",
                chat_data
            )
            
            # 4. 获取聊天历史
            self.test_endpoint(
                "获取聊天历史",
                "GET",
                f"/ai/chat/history?session_id={session_id}&limit=10"
            )
        
        # 测试实时回测端点
        print("\n⚡ 测试实时回测API端点:")
        
        # 5. 启动实时回测
        backtest_config = {
            "strategy_code": """
# 简单MACD策略测试
class TestMACDStrategy:
    def __init__(self):
        self.position = 0
        
    def on_data(self, data):
        # 简单的买入持有策略用于测试
        if len(data.get('close', [])) > 50:
            return 1 if self.position == 0 else 0
        return 0
""",
            "exchange": "binance",
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "initial_capital": 10000.0,
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "data_type": "kline"
        }
        
        start_result = self.test_endpoint(
            "启动实时回测",
            "POST",
            "/realtime-backtest/start",
            backtest_config
        )
        
        task_id = None
        if start_result["success"] and start_result["response_data"]:
            task_id = start_result["response_data"].get("task_id")
        
        # 6. 查询回测状态（如果有任务ID）
        if task_id:
            self.test_endpoint(
                "查询回测状态",
                "GET",
                f"/realtime-backtest/status/{task_id}"
            )
            
            # 等待一下，然后再次查询
            time.sleep(2)
            self.test_endpoint(
                "再次查询回测状态",
                "GET",
                f"/realtime-backtest/status/{task_id}"
            )
        
        # 测试AI策略集成端点
        print("\n🤖 测试AI策略集成API端点:")
        
        if session_id:
            # 7. AI策略自动回测
            ai_backtest_config = {
                "ai_session_id": session_id,
                "strategy_code": backtest_config["strategy_code"],
                "strategy_name": "测试AI策略",
                "auto_config": True,
                "initial_capital": 10000.0,
                "start_date": "2024-01-01",
                "end_date": "2024-03-31"
            }
            
            ai_result = self.test_endpoint(
                "AI策略自动回测",
                "POST",
                "/ai/strategy/auto-backtest",
                ai_backtest_config
            )
            
            ai_task_id = None
            if ai_result["success"] and ai_result["response_data"]:
                ai_task_id = ai_result["response_data"].get("task_id")
            
            # 8. 查询AI策略回测进度
            if ai_task_id:
                self.test_endpoint(
                    "查询AI策略回测进度",
                    "GET",
                    f"/realtime-backtest/ai-strategy/progress/{ai_task_id}"
                )
        
        # 测试策略管理端点
        print("\n📊 测试策略管理API端点:")
        
        # 9. 获取策略列表
        self.test_endpoint(
            "获取策略列表",
            "GET",
            "/strategies?limit=5"
        )
        
        # 10. 获取用户统计
        self.test_endpoint(
            "获取用户统计",
            "GET",
            "/users/me/stats"
        )
        
        # 生成测试报告
        self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 API端点测试报告")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数量: {total_tests}")
        print(f"通过测试: {passed_tests} ✅")
        print(f"失败测试: {failed_tests} ❌")
        print(f"测试通过率: {(passed_tests / total_tests * 100):.1f}%")
        
        # 性能统计
        response_times = [r["execution_time"] for r in self.test_results if r["success"]]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            print(f"平均响应时间: {avg_response_time:.3f}秒")
            print(f"最大响应时间: {max_response_time:.3f}秒")
        
        # 失败的测试详情
        if failed_tests > 0:
            print(f"\n❌ 失败的测试 ({failed_tests}个):")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['name']}: {result['error_message']}")
        
        # 成功的测试详情
        print(f"\n✅ 成功的测试 ({passed_tests}个):")
        for result in self.test_results:
            if result["success"]:
                print(f"  - {result['name']}: {result['status_code']} ({result['execution_time']:.3f}s)")
        
        # 保存详细报告
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0
            },
            "performance": {
                "avg_response_time": avg_response_time if response_times else 0,
                "max_response_time": max_response_time if response_times else 0
            },
            "test_details": self.test_results
        }
        
        report_filename = f"api_endpoint_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细测试报告已保存至: {report_filename}")
        
        return report_data


def main():
    """主测试函数"""
    # 检查服务是否可访问
    try:
        response = requests.get("http://43.167.252.120:8001/docs", timeout=5)
        if response.status_code == 200:
            print("✅ 交易服务API文档可访问")
        else:
            print(f"⚠️  交易服务响应状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 无法连接到交易服务: {str(e)}")
        print("请确保交易服务正在运行在端口8001")
        return
    
    # 运行API测试
    tester = APIEndpointTester()
    tester.run_api_tests()


if __name__ == "__main__":
    main()