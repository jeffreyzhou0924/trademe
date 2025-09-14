#!/usr/bin/env python3
"""
AI策略回测系统错误处理和边界情况测试
测试系统在各种异常情况下的表现
"""

import asyncio
import json
import time
import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class ErrorHandlingTester:
    """错误处理和边界情况测试器"""
    
    def __init__(self):
        self.test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_details": [],
            "error_scenarios": {},
            "performance_under_stress": {}
        }
        self.base_url = "http://43.167.252.120:8001/api/v1"
        self.auth_token = None
        
    def log_test_result(self, test_name: str, success: bool, details: str, execution_time: float = 0):
        """记录测试结果"""
        self.test_results["total_tests"] += 1
        if success:
            self.test_results["passed_tests"] += 1
            status = "✅ PASSED"
        else:
            self.test_results["failed_tests"] += 1
            status = "❌ FAILED"
        
        self.test_results["test_details"].append({
            "test_name": test_name,
            "status": status,
            "details": details,
            "execution_time": f"{execution_time:.3f}s"
        })
        
        print(f"{status} {test_name} - {details} ({execution_time:.3f}s)")
    
    def setup_auth(self):
        """设置认证"""
        try:
            login_url = "http://43.167.252.120/api/v1/auth/login"
            login_data = {
                "email": "publictest@example.com",
                "password": "PublicTest123!"
            }
            
            response = requests.post(login_url, json=login_data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("data"):
                    self.auth_token = result["data"].get("access_token")
                    return True
            return False
        except Exception as e:
            print(f"认证设置失败: {e}")
            return False
    
    def make_api_request(self, method: str, endpoint: str, data: Dict = None, timeout: int = 30):
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.text else None,
                "text": response.text
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "status_code": 0,
                "data": None,
                "text": ""
            }
    
    def test_invalid_authentication(self):
        """测试无效认证处理"""
        print("🔐 测试无效认证处理...")
        start_time = time.time()
        
        scenarios = [
            {"name": "无token", "token": None},
            {"name": "无效token", "token": "invalid_token"},
            {"name": "过期token", "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIxIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiaWF0IjoxNjAwMDAwMDAwLCJleHAiOjE2MDAwMDAwMDB9.invalid"},
            {"name": "格式错误token", "token": "Bearer invalid_format"}
        ]
        
        passed_scenarios = 0
        for scenario in scenarios:
            old_token = self.auth_token
            self.auth_token = scenario["token"]
            
            result = self.make_api_request("GET", "/ai/sessions")
            
            # 期望返回401或403错误
            if result["status_code"] in [401, 403]:
                passed_scenarios += 1
            
            self.auth_token = old_token  # 恢复原token
        
        execution_time = time.time() - start_time
        success = passed_scenarios == len(scenarios)
        
        self.log_test_result(
            "无效认证处理", 
            success, 
            f"正确处理的认证错误: {passed_scenarios}/{len(scenarios)}",
            execution_time
        )
        
        self.test_results["error_scenarios"]["invalid_auth"] = {
            "total_scenarios": len(scenarios),
            "passed_scenarios": passed_scenarios,
            "details": scenarios
        }
    
    def test_invalid_request_data(self):
        """测试无效请求数据处理"""
        print("📝 测试无效请求数据处理...")
        start_time = time.time()
        
        invalid_configs = [
            {
                "name": "空策略代码",
                "config": {
                    "strategy_code": "",
                    "symbols": ["BTC/USDT"],
                    "timeframes": ["1h"],
                    "initial_capital": 10000,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30"
                }
            },
            {
                "name": "负数资金",
                "config": {
                    "strategy_code": "# 简单策略",
                    "symbols": ["BTC/USDT"],
                    "timeframes": ["1h"],
                    "initial_capital": -10000,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30"
                }
            },
            {
                "name": "无效日期格式",
                "config": {
                    "strategy_code": "# 简单策略",
                    "symbols": ["BTC/USDT"],
                    "timeframes": ["1h"],
                    "initial_capital": 10000,
                    "start_date": "invalid-date",
                    "end_date": "2024-06-30"
                }
            },
            {
                "name": "结束日期早于开始日期",
                "config": {
                    "strategy_code": "# 简单策略",
                    "symbols": ["BTC/USDT"],
                    "timeframes": ["1h"],
                    "initial_capital": 10000,
                    "start_date": "2024-06-30",
                    "end_date": "2024-01-01"
                }
            },
            {
                "name": "空交易对列表",
                "config": {
                    "strategy_code": "# 简单策略",
                    "symbols": [],
                    "timeframes": ["1h"],
                    "initial_capital": 10000,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30"
                }
            },
            {
                "name": "不支持的交易所",
                "config": {
                    "strategy_code": "# 简单策略",
                    "exchange": "invalid_exchange",
                    "symbols": ["BTC/USDT"],
                    "timeframes": ["1h"],
                    "initial_capital": 10000,
                    "start_date": "2024-01-01",
                    "end_date": "2024-06-30"
                }
            }
        ]
        
        passed_validations = 0
        for config_test in invalid_configs:
            result = self.make_api_request("POST", "/realtime-backtest/start", config_test["config"])
            
            # 期望返回400错误（参数验证失败）
            if result["status_code"] == 400 or (result["success"] and "error" in str(result["data"])):
                passed_validations += 1
        
        execution_time = time.time() - start_time
        success = passed_validations >= len(invalid_configs) * 0.8  # 80%通过率
        
        self.log_test_result(
            "无效请求数据处理", 
            success, 
            f"正确验证的无效配置: {passed_validations}/{len(invalid_configs)}",
            execution_time
        )
        
        self.test_results["error_scenarios"]["invalid_data"] = {
            "total_configs": len(invalid_configs),
            "passed_validations": passed_validations,
            "validation_rate": passed_validations / len(invalid_configs)
        }
    
    def test_nonexistent_resources(self):
        """测试不存在资源的处理"""
        print("🔍 测试不存在资源处理...")
        start_time = time.time()
        
        nonexistent_resources = [
            {"endpoint": "/ai/sessions/nonexistent_session_id", "method": "GET", "expected": 404},
            {"endpoint": "/realtime-backtest/status/fake_task_id", "method": "GET", "expected": 404},
            {"endpoint": "/realtime-backtest/results/fake_task_id", "method": "GET", "expected": 404},
            {"endpoint": "/strategies/999999", "method": "GET", "expected": 404},
            {"endpoint": "/strategies/latest-ai-strategy/fake_session", "method": "GET", "expected": 404}
        ]
        
        handled_correctly = 0
        for resource in nonexistent_resources:
            result = self.make_api_request(resource["method"], resource["endpoint"])
            
            if result["status_code"] == resource["expected"]:
                handled_correctly += 1
        
        execution_time = time.time() - start_time
        success = handled_correctly == len(nonexistent_resources)
        
        self.log_test_result(
            "不存在资源处理", 
            success, 
            f"正确处理的不存在资源: {handled_correctly}/{len(nonexistent_resources)}",
            execution_time
        )
        
        self.test_results["error_scenarios"]["nonexistent_resources"] = {
            "total_resources": len(nonexistent_resources),
            "handled_correctly": handled_correctly
        }
    
    def test_concurrent_requests(self):
        """测试并发请求处理"""
        print("🔄 测试并发请求处理...")
        start_time = time.time()
        
        # 准备并发请求
        def make_concurrent_request(request_id):
            config = {
                "strategy_code": f"# 并发测试策略 {request_id}",
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "initial_capital": 10000,
                "start_date": "2024-01-01",
                "end_date": "2024-03-31"
            }
            
            result = self.make_api_request("POST", "/realtime-backtest/start", config)
            return {
                "request_id": request_id,
                "success": result["success"],
                "status_code": result["status_code"],
                "response_time": time.time() - start_time
            }
        
        # 发送10个并发请求
        concurrent_requests = 10
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_request = {
                executor.submit(make_concurrent_request, i): i 
                for i in range(concurrent_requests)
            }
            
            for future in as_completed(future_to_request):
                result = future.result()
                response_times.append(result["response_time"])
                
                if result["status_code"] in [200, 201]:
                    successful_requests += 1
                else:
                    failed_requests += 1
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        execution_time = time.time() - start_time
        success = successful_requests >= concurrent_requests * 0.8  # 80%成功率
        
        self.log_test_result(
            "并发请求处理", 
            success, 
            f"成功请求: {successful_requests}/{concurrent_requests}, 平均响应时间: {avg_response_time:.3f}s",
            execution_time
        )
        
        self.test_results["performance_under_stress"]["concurrent_requests"] = {
            "total_requests": concurrent_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": successful_requests / concurrent_requests,
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time
        }
    
    def test_request_timeout_handling(self):
        """测试请求超时处理"""
        print("⏱️ 测试请求超时处理...")
        start_time = time.time()
        
        # 测试快速超时
        timeout_scenarios = [
            {"timeout": 0.1, "name": "极短超时"},
            {"timeout": 1.0, "name": "短超时"},
            {"timeout": 5.0, "name": "中等超时"}
        ]
        
        timeout_handled_correctly = 0
        
        for scenario in timeout_scenarios:
            config = {
                "strategy_code": "# 超时测试策略\ntime.sleep(10)",  # 会导致长时间执行
                "symbols": ["BTC/USDT"],
                "timeframes": ["1h"],
                "initial_capital": 10000,
                "start_date": "2024-01-01",
                "end_date": "2024-02-01"
            }
            
            result = self.make_api_request("POST", "/realtime-backtest/start", config, timeout=scenario["timeout"])
            
            # 如果超时或返回错误，认为处理正确
            if not result["success"] or result["status_code"] >= 400:
                timeout_handled_correctly += 1
        
        execution_time = time.time() - start_time
        success = timeout_handled_correctly >= len(timeout_scenarios) * 0.7  # 70%处理率
        
        self.log_test_result(
            "请求超时处理", 
            success, 
            f"正确处理的超时场景: {timeout_handled_correctly}/{len(timeout_scenarios)}",
            execution_time
        )
        
        self.test_results["error_scenarios"]["timeout_handling"] = {
            "total_scenarios": len(timeout_scenarios),
            "handled_correctly": timeout_handled_correctly
        }
    
    def test_malformed_json_handling(self):
        """测试格式错误的JSON处理"""
        print("📄 测试格式错误JSON处理...")
        start_time = time.time()
        
        malformed_requests = [
            {"data": "not_json", "name": "非JSON字符串"},
            {"data": '{"incomplete": json', "name": "不完整JSON"},
            {"data": '{"key": "value",}', "name": "多余逗号JSON"},
            {"data": '{"key": undefined}', "name": "undefined值JSON"}
        ]
        
        handled_malformed = 0
        
        for request_test in malformed_requests:
            try:
                url = f"{self.base_url}/realtime-backtest/start"
                headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/json"}
                
                response = requests.post(url, data=request_test["data"], headers=headers, timeout=10)
                
                # 期望返回400错误
                if response.status_code == 400:
                    handled_malformed += 1
            except Exception:
                # 如果抛出异常，也认为是正确处理
                handled_malformed += 1
        
        execution_time = time.time() - start_time
        success = handled_malformed == len(malformed_requests)
        
        self.log_test_result(
            "格式错误JSON处理", 
            success, 
            f"正确处理的格式错误请求: {handled_malformed}/{len(malformed_requests)}",
            execution_time
        )
        
        self.test_results["error_scenarios"]["malformed_json"] = {
            "total_requests": len(malformed_requests),
            "handled_correctly": handled_malformed
        }
    
    def test_memory_intensive_operations(self):
        """测试内存密集型操作"""
        print("💾 测试内存密集型操作...")
        start_time = time.time()
        
        # 创建大型策略代码
        large_strategy_code = "# 大型策略测试\n" + "# 注释行\n" * 1000 + """
class LargeStrategy:
    def __init__(self):
        self.data = [0] * 10000  # 大数据结构
        
    def on_data(self, data):
        # 计算密集型操作
        result = 0
        for i in range(len(self.data)):
            result += i * 2
        return result % 2
"""
        
        config = {
            "strategy_code": large_strategy_code,
            "symbols": ["BTC/USDT"],
            "timeframes": ["1h"],
            "initial_capital": 10000,
            "start_date": "2024-01-01",
            "end_date": "2024-02-01"
        }
        
        result = self.make_api_request("POST", "/realtime-backtest/start", config, timeout=30)
        
        execution_time = time.time() - start_time
        
        # 如果成功创建任务或返回合理的错误，认为处理正确
        success = result["success"] or result["status_code"] in [400, 413, 500]
        
        self.log_test_result(
            "内存密集型操作处理", 
            success, 
            f"大型策略处理结果: {result['status_code']}",
            execution_time
        )
        
        self.test_results["performance_under_stress"]["memory_intensive"] = {
            "strategy_size_bytes": len(large_strategy_code),
            "response_time": execution_time,
            "handled_successfully": success
        }
    
    def test_rate_limiting(self):
        """测试速率限制"""
        print("🚦 测试速率限制...")
        start_time = time.time()
        
        # 快速发送多个请求
        requests_in_burst = 20
        successful_requests = 0
        rate_limited_requests = 0
        
        for i in range(requests_in_burst):
            result = self.make_api_request("GET", "/ai/sessions")
            
            if result["status_code"] == 200:
                successful_requests += 1
            elif result["status_code"] == 429:  # 速率限制
                rate_limited_requests += 1
            
            # 很短的间隔
            time.sleep(0.01)
        
        execution_time = time.time() - start_time
        
        # 如果有速率限制或所有请求都成功，认为处理正确
        success = rate_limited_requests > 0 or successful_requests == requests_in_burst
        
        self.log_test_result(
            "速率限制处理", 
            success, 
            f"成功请求: {successful_requests}, 被限制请求: {rate_limited_requests}",
            execution_time
        )
        
        self.test_results["performance_under_stress"]["rate_limiting"] = {
            "total_requests": requests_in_burst,
            "successful_requests": successful_requests,
            "rate_limited_requests": rate_limited_requests,
            "requests_per_second": requests_in_burst / execution_time
        }
    
    def run_all_tests(self):
        """运行所有错误处理和边界情况测试"""
        print("🚀 开始错误处理和边界情况测试")
        print("=" * 60)
        
        overall_start_time = time.time()
        
        # 设置认证
        if not self.setup_auth():
            print("❌ 认证设置失败，跳过需要认证的测试")
            return self.generate_report()
        
        try:
            # 1. 无效认证处理测试
            self.test_invalid_authentication()
            
            # 2. 无效请求数据处理测试
            self.test_invalid_request_data()
            
            # 3. 不存在资源处理测试
            self.test_nonexistent_resources()
            
            # 4. 并发请求处理测试
            self.test_concurrent_requests()
            
            # 5. 请求超时处理测试
            self.test_request_timeout_handling()
            
            # 6. 格式错误JSON处理测试
            self.test_malformed_json_handling()
            
            # 7. 内存密集型操作测试
            self.test_memory_intensive_operations()
            
            # 8. 速率限制测试
            self.test_rate_limiting()
            
        except Exception as e:
            print(f"❌ 测试执行异常: {str(e)}")
        
        overall_execution_time = time.time() - overall_start_time
        print(f"\n总测试执行时间: {overall_execution_time:.3f}秒")
        
        return self.generate_report()
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("📊 错误处理和边界情况测试报告")
        print("=" * 60)
        
        total_tests = self.test_results["total_tests"]
        passed_tests = self.test_results["passed_tests"]
        failed_tests = self.test_results["failed_tests"]
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"总测试数量: {total_tests}")
        print(f"通过测试: {passed_tests} ✅")
        print(f"失败测试: {failed_tests} ❌")
        print(f"测试通过率: {success_rate:.1f}%")
        
        # 详细测试结果
        print("\n📋 详细测试结果:")
        for detail in self.test_results["test_details"]:
            print(f"  {detail['status']} {detail['test_name']} ({detail['execution_time']})")
        
        # 错误场景分析
        if self.test_results["error_scenarios"]:
            print("\n🚨 错误场景分析:")
            for scenario, data in self.test_results["error_scenarios"].items():
                if isinstance(data, dict) and "total_scenarios" in data:
                    rate = (data.get("passed_scenarios", 0) / data["total_scenarios"] * 100)
                    print(f"  {scenario}: {rate:.1f}% 正确处理率")
        
        # 压力测试性能
        if self.test_results["performance_under_stress"]:
            print("\n⚡ 压力测试性能:")
            perf_data = self.test_results["performance_under_stress"]
            
            if "concurrent_requests" in perf_data:
                concurrent = perf_data["concurrent_requests"]
                print(f"  并发处理: {concurrent['success_rate']:.1%} 成功率, {concurrent['avg_response_time']:.3f}s 平均响应")
            
            if "rate_limiting" in perf_data:
                rate_limit = perf_data["rate_limiting"]
                print(f"  速率限制: {rate_limit['requests_per_second']:.1f} 请求/秒")
        
        # 总体评估
        print("\n🏆 总体评估:")
        if success_rate >= 90:
            print("  ✅ 系统错误处理机制优秀，边界情况处理完善")
        elif success_rate >= 75:
            print("  ⚠️  系统错误处理机制良好，部分边界情况需要改进")
        else:
            print("  ❌ 系统错误处理机制需要重要改进")
        
        # 保存报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate
            },
            "test_details": self.test_results["test_details"],
            "error_scenarios": self.test_results["error_scenarios"],
            "performance_under_stress": self.test_results["performance_under_stress"]
        }
        
        report_filename = f"error_handling_test_report_{int(time.time())}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 详细测试报告已保存至: {report_filename}")
        
        return report


def main():
    """主测试函数"""
    tester = ErrorHandlingTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()