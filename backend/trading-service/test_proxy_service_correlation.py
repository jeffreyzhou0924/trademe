#!/usr/bin/env python3
"""
执行外部代理服务复杂度关联测试
专门分析策略生成超时问题，测试不同复杂度请求的响应时间关系
绕过内部AI服务，直接测试外部代理服务的处理能力和限制
"""

import asyncio
import sys
import os
import time
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到Python路径
sys.path.append('/root/trademe/backend/trading-service')


class ProxyServiceTester:
    """外部代理服务测试器"""
    
    def __init__(self):
        self.proxy_base_url = "https://claude.cloudcdn7.com/api"
        self.proxy_api_key = "cr_b48f228f987b3d94495498a9260fdb6032ccc4cd3dd49ea380c960ed699bab56"
        self.results = []
        
    def build_test_requests(self) -> List[Dict[str, Any]]:
        """构建不同复杂度的测试请求"""
        
        base_system = "你是Trademe平台的AI交易助手，专门帮助用户进行数字货币交易决策。"
        
        # 创建多层次复杂度测试用例
        test_cases = [
            {
                "name": "极简对话",
                "complexity": "minimal",
                "system": base_system,
                "message": "你好",
                "expected_output_tokens": 50,
                "timeout_seconds": 10
            },
            {
                "name": "基础询问", 
                "complexity": "basic",
                "system": base_system,
                "message": "什么是MACD指标？请简单解释一下。",
                "expected_output_tokens": 200,
                "timeout_seconds": 15
            },
            {
                "name": "简单策略请求",
                "complexity": "simple_strategy", 
                "system": base_system + "请帮助用户创建交易策略。",
                "message": "创建一个简单的MACD策略",
                "expected_output_tokens": 500,
                "timeout_seconds": 20
            },
            {
                "name": "中等策略请求",
                "complexity": "medium_strategy",
                "system": base_system + "请帮助用户创建交易策略，提供Python代码实现。",
                "message": "请创建一个基于MACD和RSI指标的BTC交易策略，包括买卖信号逻辑",
                "expected_output_tokens": 1000,
                "timeout_seconds": 30
            },
            {
                "name": "复杂策略请求", 
                "complexity": "complex_strategy",
                "system": base_system + "请帮助用户创建交易策略，提供完整的Python代码实现，包括策略类定义、方法实现、参数配置和注释。请将Python代码包装在 ```python 代码块中。",
                "message": "请帮我创建一个完整的多因子量化交易策略，结合MACD、RSI、布林带指标，包含完整的风险管理、仓位管理、止损止盈逻辑，支持BTC和ETH交易对",
                "expected_output_tokens": 2000,
                "timeout_seconds": 35
            },
            {
                "name": "超复杂策略请求",
                "complexity": "ultra_complex",
                "system": base_system + "请帮助用户创建交易策略，提供完整的Python代码实现，包括策略类定义、方法实现、参数配置和注释。请将Python代码包装在 ```python 代码块中。",
                "message": "请帮我创建一个完整的高频量化交易策略系统，需要包括：1) 多因子信号生成（技术指标、情绪指标、基本面指标）2) 智能仓位管理和资金分配 3) 动态止损止盈机制 4) 风险管理模块（VaR、最大回撤控制）5) 回测框架集成 6) 实盘交易接口 7) 监控告警系统，支持多个交易对（BTC、ETH、BNB、SOL），包含完整的异常处理和日志记录",
                "expected_output_tokens": 4000,
                "timeout_seconds": 40
            }
        ]
        
        return test_cases
    
    async def test_single_request(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """测试单个请求"""
        
        print(f"\n🧪 测试: {test_case['name']} (复杂度: {test_case['complexity']})")
        print(f"📝 消息长度: {len(test_case['message'])} 字符")
        print(f"🎯 预期输出: {test_case['expected_output_tokens']} tokens")
        print(f"⏰ 超时设置: {test_case['timeout_seconds']} 秒")
        
        # 构建请求
        request_data = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": test_case["message"]}],
            "max_tokens": 4000,
            "temperature": 0.7,
            "system": test_case["system"]
        }
        
        # 计算请求大小
        request_json = json.dumps(request_data, ensure_ascii=False)
        request_size = len(request_json.encode('utf-8'))
        
        print(f"📦 请求大小: {request_size:,} 字节")
        
        # 执行请求并测量时间
        start_time = time.time()
        result = {
            "name": test_case["name"],
            "complexity": test_case["complexity"],
            "request_size": request_size,
            "system_length": len(test_case["system"]),
            "message_length": len(test_case["message"]),
            "expected_output_tokens": test_case["expected_output_tokens"],
            "timeout_setting": test_case["timeout_seconds"],
            "start_time": start_time
        }
        
        try:
            timeout_config = httpx.Timeout(test_case["timeout_seconds"])
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.proxy_api_key}",
                    "User-Agent": "Trademe-Proxy-Test/1.0"
                }
                
                response = await client.post(
                    f"{self.proxy_base_url}/v1/messages",
                    headers=headers,
                    json=request_data
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                # 分析响应
                result.update({
                    "success": response.status_code == 200,
                    "http_status": response.status_code,
                    "duration": duration,
                    "timed_out": False
                })
                
                if response.status_code == 200:
                    response_data = response.json()
                    usage = response_data.get("usage", {})
                    content = response_data.get("content", [])
                    
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    response_text = ""
                    
                    if content and len(content) > 0:
                        response_text = content[0].get("text", "")
                    
                    result.update({
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "response_length": len(response_text),
                        "tokens_per_second": output_tokens / duration if duration > 0 else 0,
                        "cost_estimate": (input_tokens * 0.003 + output_tokens * 0.015) / 1000,  # Claude定价估算
                        "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text
                    })
                    
                    print(f"✅ 成功响应: {duration:.2f}秒")
                    print(f"📊 Token使用: 输入{input_tokens}, 输出{output_tokens}")
                    print(f"💰 预估成本: ${result['cost_estimate']:.6f}")
                    print(f"⚡ 生成速度: {result['tokens_per_second']:.1f} tokens/秒")
                    
                else:
                    print(f"❌ 请求失败: HTTP {response.status_code}")
                    print(f"⏱️  失败时间: {duration:.2f}秒")
                    try:
                        error_data = response.json()
                        result["error_message"] = error_data.get("error", {}).get("message", response.text[:200])
                    except:
                        result["error_message"] = response.text[:200]
                
        except httpx.TimeoutException:
            end_time = time.time()
            duration = end_time - start_time
            result.update({
                "success": False,
                "timed_out": True,
                "duration": duration,
                "error_message": f"请求超时 ({duration:.1f}秒)"
            })
            print(f"⏰ 请求超时: {duration:.1f}秒")
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            result.update({
                "success": False,
                "timed_out": False,
                "duration": duration,
                "error_message": str(e)
            })
            print(f"❌ 请求异常: {str(e)} ({duration:.1f}秒)")
        
        print("-" * 60)
        return result
    
    async def run_correlation_test(self) -> List[Dict[str, Any]]:
        """运行完整的相关性测试"""
        
        print("🔍 外部代理服务复杂度关联测试")
        print("=" * 80)
        print("📋 测试目标: 分析请求复杂度与响应时间/超时关系")
        print("🎯 重点关注: 策略生成请求的超时模式")
        print("-" * 80)
        
        test_cases = self.build_test_requests()
        results = []
        
        # 串行执行测试，避免并发对结果的影响
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n【第{i}/{len(test_cases)}轮测试】")
            result = await self.test_single_request(test_case)
            results.append(result)
            
            # 测试间隔，避免过快请求
            if i < len(test_cases):
                print("⏱️  等待3秒后进行下一测试...")
                await asyncio.sleep(3)
        
        self.results = results
        return results
    
    def analyze_results(self) -> Dict[str, Any]:
        """分析测试结果"""
        
        print("\n" + "=" * 80)
        print("📊 测试结果分析")
        print("=" * 80)
        
        # 基础统计
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.get('success', False))
        timed_out_tests = sum(1 for r in self.results if r.get('timed_out', False))
        failed_tests = total_tests - successful_tests
        
        print(f"\n📈 总体统计:")
        print(f"  总测试数: {total_tests}")
        print(f"  成功: {successful_tests} ({successful_tests/total_tests*100:.1f}%)")
        print(f"  超时: {timed_out_tests} ({timed_out_tests/total_tests*100:.1f}%)")
        print(f"  失败: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
        
        # 详细结果表格
        print(f"\n📋 详细测试结果:")
        print(f"{'测试名称':<20} {'复杂度':<15} {'消息长度':<8} {'处理时间':<10} {'状态':<15} {'输出Token':<10}")
        print("-" * 90)
        
        for result in self.results:
            status = "✅成功" if result.get('success', False) else ("⏰超时" if result.get('timed_out', False) else "❌失败")
            output_tokens = result.get('output_tokens', 0)
            duration = result.get('duration', 0)
            
            print(f"{result['name']:<20} {result['complexity']:<15} {result['message_length']:<8} {duration:<10.2f} {status:<15} {output_tokens:<10}")
        
        # 成功请求的性能分析
        successful_results = [r for r in self.results if r.get('success', False)]
        if successful_results:
            print(f"\n⚡ 成功请求性能分析:")
            for result in successful_results:
                duration = result['duration']
                output_tokens = result.get('output_tokens', 0)
                tokens_per_sec = result.get('tokens_per_second', 0)
                cost = result.get('cost_estimate', 0)
                
                print(f"  {result['name']}: {duration:.2f}秒, {output_tokens}tokens, {tokens_per_sec:.1f}t/s, ${cost:.6f}")
        
        # 超时模式分析
        timeout_results = [r for r in self.results if r.get('timed_out', False)]
        if timeout_results:
            print(f"\n⏰ 超时模式分析:")
            for result in timeout_results:
                print(f"  {result['name']} (复杂度: {result['complexity']}): 超时于{result['duration']:.1f}秒")
                print(f"    消息长度: {result['message_length']} 字符")
                print(f"    请求大小: {result['request_size']:,} 字节")
                print(f"    预期输出: {result['expected_output_tokens']} tokens")
        
        # 关键发现
        print(f"\n🔍 关键发现:")
        
        # 1. 复杂度与超时关系
        complex_timeouts = [r for r in timeout_results if 'complex' in r['complexity']]
        simple_success = [r for r in successful_results if r['complexity'] in ['minimal', 'basic']]
        
        print(f"1. 复杂度影响:")
        print(f"   - 简单请求成功率: {len(simple_success)}/{len([r for r in self.results if r['complexity'] in ['minimal', 'basic']])}")
        print(f"   - 复杂策略请求超时: {len(complex_timeouts)}/{len([r for r in self.results if 'complex' in r['complexity']])}")
        
        # 2. 时间阈值分析
        if successful_results:
            max_success_time = max(r['duration'] for r in successful_results)
            min_timeout_time = min(r['duration'] for r in timeout_results) if timeout_results else None
            
            print(f"2. 时间阈值:")
            print(f"   - 最长成功请求: {max_success_time:.2f}秒")
            if min_timeout_time:
                print(f"   - 最短超时请求: {min_timeout_time:.2f}秒")
                print(f"   - 超时阈值范围: {max_success_time:.1f}-{min_timeout_time:.1f}秒")
        
        # 3. 输出Token分析
        if successful_results:
            avg_output_tokens = sum(r.get('output_tokens', 0) for r in successful_results) / len(successful_results)
            max_output_tokens = max(r.get('output_tokens', 0) for r in successful_results)
            
            print(f"3. 输出Token模式:")
            print(f"   - 平均输出: {avg_output_tokens:.0f} tokens")
            print(f"   - 最大输出: {max_output_tokens} tokens")
        
        # 4. 策略生成特殊分析
        strategy_results = [r for r in self.results if 'strategy' in r['complexity']]
        strategy_timeouts = [r for r in strategy_results if r.get('timed_out', False)]
        
        if strategy_results:
            print(f"4. 策略生成特殊模式:")
            print(f"   - 策略请求总数: {len(strategy_results)}")
            print(f"   - 策略请求超时: {len(strategy_timeouts)} ({len(strategy_timeouts)/len(strategy_results)*100:.1f}%)")
            
            if strategy_timeouts:
                print("   - 超时的策略请求类型:")
                for result in strategy_timeouts:
                    print(f"     * {result['name']}: 消息{result['message_length']}字符, 预期{result['expected_output_tokens']}tokens")
        
        return {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "timed_out_tests": timed_out_tests,
            "failed_tests": failed_tests,
            "timeout_pattern": {
                "complex_strategy_timeouts": len(complex_timeouts),
                "simple_request_success": len(simple_success)
            },
            "performance_metrics": {
                "max_success_time": max(r['duration'] for r in successful_results) if successful_results else 0,
                "avg_output_tokens": sum(r.get('output_tokens', 0) for r in successful_results) / len(successful_results) if successful_results else 0
            }
        }
    
    def generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        
        analysis = self.analyze_results()
        recommendations = []
        
        print(f"\n💡 优化建议:")
        
        # 基于超时模式的建议
        if analysis['timed_out_tests'] > 0:
            complex_timeout_rate = analysis['timeout_pattern']['complex_strategy_timeouts'] / analysis['timed_out_tests']
            
            if complex_timeout_rate > 0.5:
                rec1 = "1. 实施策略生成分段处理：将复杂策略请求拆分为多个简单步骤"
                recommendations.append(rec1)
                print(f"  {rec1}")
                
                rec2 = "2. 优化系统提示：移除不必要的详细指令，专注核心功能要求"
                recommendations.append(rec2)
                print(f"  {rec2}")
        
        # 基于性能指标的建议
        if analysis['performance_metrics']['max_success_time'] > 20:
            rec3 = "3. 设置动态超时：根据请求复杂度调整超时时间（简单15s，复杂45s）"
            recommendations.append(rec3)
            print(f"  {rec3}")
        
        # 基于输出Token的建议
        if analysis['performance_metrics']['avg_output_tokens'] > 1000:
            rec4 = "4. 限制输出长度：为复杂策略请求设置max_tokens=2000，避免过长响应"
            recommendations.append(rec4)
            print(f"  {rec4}")
        
        # 通用建议
        rec5 = "5. 实施预检测：在发送请求前评估复杂度，预警可能的超时风险"
        recommendations.append(rec5)
        print(f"  {rec5}")
        
        rec6 = "6. 考虑备用方案：超时后自动切换到简化版策略生成模式"
        recommendations.append(rec6)
        print(f"  {rec6}")
        
        return recommendations


async def main():
    """主测试函数"""
    
    print("🚀 TradeMe外部代理服务复杂度关联测试")
    print("=" * 80)
    print("🎯 目标: 找出AI策略生成30秒超时的根本原因")
    print("📊 方法: 系统性测试不同复杂度请求的响应模式")
    print("⏰ 预计时间: 约5-8分钟")
    
    # 创建测试器并运行测试
    tester = ProxyServiceTester()
    
    try:
        # 执行相关性测试
        results = await tester.run_correlation_test()
        
        # 分析结果
        analysis = tester.analyze_results()
        
        # 生成建议
        recommendations = tester.generate_recommendations()
        
        # 保存结果到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"proxy_correlation_test_results_{timestamp}.json"
        
        full_report = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(results),
                "test_duration": sum(r.get('duration', 0) for r in results)
            },
            "results": results,
            "analysis": analysis,
            "recommendations": recommendations
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细结果已保存到: {result_file}")
        
        # 关键结论
        print("\n" + "=" * 80)
        print("🎯 关键结论:")
        
        timeout_rate = analysis['timed_out_tests'] / analysis['total_tests']
        if timeout_rate > 0.3:
            print("❌ 高超时率确认: 外部代理服务确实存在复杂请求处理限制")
            print("🔍 主要原因: 复杂策略生成请求超出代理服务30秒处理能力")
            print("💡 解决方向: 实施请求分段、动态超时、输出限制策略")
        else:
            print("✅ 外部代理服务处理能力正常，可能是其他因素导致超时")
            print("🔍 需进一步排查: 网络连接、账号限制、系统负载等因素")
        
        return results
        
    except Exception as e:
        print(f"❌ 测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\n✅ 外部代理服务复杂度关联测试完成")
    sys.exit(0)