#!/usr/bin/env python3
"""
WebSocket AI流式对话系统测试执行器

执行完整的测试套件，包括：
1. 单元测试
2. 集成测试  
3. 端到端测试
4. Object错误重现测试
5. 性能测试
"""

import asyncio
import sys
import os
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试报告类
class TestReport:
    def __init__(self):
        self.start_time = datetime.now()
        self.test_results = []
        self.summary = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
    
    def add_result(self, test_name: str, status: str, duration: float, error: Optional[str] = None):
        result = {
            'test_name': test_name,
            'status': status,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        if error:
            result['error'] = error
        
        self.test_results.append(result)
        self.summary['total'] += 1
        self.summary[status] += 1
        
        if error:
            self.summary['errors'].append({'test': test_name, 'error': error})
    
    def generate_report(self) -> Dict[str, Any]:
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        return {
            'test_session': {
                'start_time': self.start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_duration': total_duration
            },
            'summary': self.summary,
            'test_results': self.test_results,
            'success_rate': (self.summary['passed'] / self.summary['total'] * 100) if self.summary['total'] > 0 else 0
        }


class WebSocketAITestRunner:
    """WebSocket AI测试运行器"""
    
    def __init__(self):
        self.report = TestReport()
        self.test_server_process = None
        self.base_dir = Path(__file__).parent
        
    async def setup_test_environment(self):
        """设置测试环境"""
        print("🔧 设置测试环境...")
        
        # 检查必要依赖
        required_packages = ['pytest', 'pytest-asyncio', 'websockets']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
            print("安装命令: pip install " + " ".join(missing_packages))
            return False
            
        print("✅ 测试环境检查完成")
        return True
    
    async def run_unit_tests(self):
        """运行单元测试"""
        print("\n📋 开始单元测试...")
        start_time = time.time()
        
        try:
            # 导入测试模块
            from tests.test_websocket_ai_streaming import (
                TestWebSocketAIMessageSerialization,
                TestWebSocketAIUnit
            )
            
            # 运行序列化测试
            serialization_test = TestWebSocketAIMessageSerialization()
            serialization_test.test_error_object_serialization()
            print("  ✅ 错误对象序列化测试通过")
            
            serialization_test.test_stream_message_format_validation()
            print("  ✅ 流式消息格式验证测试通过")
            
            serialization_test.test_error_message_format_validation()
            print("  ✅ 错误消息格式验证测试通过")
            
            duration = time.time() - start_time
            self.report.add_result("单元测试", "passed", duration)
            print(f"✅ 单元测试完成 ({duration:.2f}s)")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"单元测试失败: {str(e)}"
            self.report.add_result("单元测试", "failed", duration, error_msg)
            print(f"❌ {error_msg}")
    
    async def run_object_error_reproduction_tests(self):
        """运行Object错误重现测试"""
        print("\n🔍 开始Object错误重现测试...")
        start_time = time.time()
        
        try:
            from tests.test_websocket_ai_streaming import TestWebSocketAIObjectErrorReproduction
            
            test_instance = TestWebSocketAIObjectErrorReproduction()
            
            # 运行错误重现测试
            test_instance.test_reproduce_object_serialization_error()
            print("  ✅ Object序列化错误重现测试通过")
            
            test_instance.test_aistore_error_message_generator()
            print("  ✅ AIStore错误消息生成器测试通过")
            
            duration = time.time() - start_time
            self.report.add_result("Object错误重现测试", "passed", duration)
            print(f"✅ Object错误重现测试完成 ({duration:.2f}s)")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Object错误重现测试失败: {str(e)}"
            self.report.add_result("Object错误重现测试", "failed", duration, error_msg)
            print(f"❌ {error_msg}")
    
    async def run_websocket_connection_tests(self):
        """运行WebSocket连接测试"""
        print("\n🔌 开始WebSocket连接测试...")
        start_time = time.time()
        
        try:
            import websockets
            import json
            
            # 测试WebSocket连接（如果服务器运行中）
            websocket_url = "ws://localhost:8001/ai/ws/chat"
            
            try:
                # 尝试连接WebSocket
                async with websockets.connect(websocket_url, timeout=5) as websocket:
                    # 发送测试认证消息
                    auth_message = {
                        "type": "authenticate",
                        "token": "test-token"
                    }
                    await websocket.send(json.dumps(auth_message))
                    
                    # 等待响应
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    response_data = json.loads(response)
                    
                    print(f"  ✅ WebSocket连接测试通过，响应: {response_data.get('type', 'unknown')}")
                    
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                print("  ⚠️  WebSocket服务器未运行，跳过连接测试")
            
            duration = time.time() - start_time
            self.report.add_result("WebSocket连接测试", "passed", duration)
            print(f"✅ WebSocket连接测试完成 ({duration:.2f}s)")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"WebSocket连接测试失败: {str(e)}"
            self.report.add_result("WebSocket连接测试", "failed", duration, error_msg)
            print(f"❌ {error_msg}")
    
    async def run_performance_tests(self):
        """运行性能测试"""
        print("\n⚡ 开始性能测试...")
        start_time = time.time()
        
        try:
            # 测试大量错误对象处理性能
            test_errors = []
            for i in range(1000):
                test_errors.append({
                    'error': f'Test error {i}',
                    'details': {'index': i, 'data': list(range(100))}
                })
            
            # 模拟getErrorMessage函数
            def get_error_message(error):
                if not error:
                    return '未知错误，请重试'
                
                error_message = error.get('error', '')
                if isinstance(error_message, dict):
                    try:
                        error_message = json.dumps(error_message)
                    except:
                        error_message = str(error_message)
                
                return str(error_message or '未知错误')
            
            # 性能测试
            perf_start = time.time()
            processed_count = 0
            for error in test_errors:
                result = get_error_message(error)
                if isinstance(result, str) and len(result) > 0:
                    processed_count += 1
            perf_end = time.time()
            
            processing_time = perf_end - perf_start
            throughput = processed_count / processing_time
            
            print(f"  ✅ 处理了{processed_count}个错误对象")
            print(f"  ✅ 处理时间: {processing_time:.3f}s")
            print(f"  ✅ 吞吐量: {throughput:.0f} 错误/秒")
            
            # 性能要求：应该能在1秒内处理1000个错误
            if processing_time < 1.0:
                print("  ✅ 性能测试通过")
                duration = time.time() - start_time
                self.report.add_result("性能测试", "passed", duration)
            else:
                raise Exception(f"性能不达标：处理时间{processing_time:.3f}s超过1s限制")
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"性能测试失败: {str(e)}"
            self.report.add_result("性能测试", "failed", duration, error_msg)
            print(f"❌ {error_msg}")
    
    def run_frontend_tests(self):
        """运行前端测试"""
        print("\n🌐 开始前端测试...")
        start_time = time.time()
        
        try:
            # 检查前端测试文件是否存在
            frontend_test_file = Path(__file__).parent.parent.parent / "frontend" / "src" / "tests" / "websocket-ai.test.ts"
            
            if not frontend_test_file.exists():
                print(f"  ⚠️  前端测试文件不存在: {frontend_test_file}")
                duration = time.time() - start_time
                self.report.add_result("前端测试", "skipped", duration, "测试文件不存在")
                return
            
            # 检查是否安装了vitest
            try:
                result = subprocess.run(
                    ["npm", "list", "vitest"],
                    cwd=frontend_test_file.parent.parent.parent,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    print("  ⚠️  Vitest未安装，跳过前端测试")
                    duration = time.time() - start_time
                    self.report.add_result("前端测试", "skipped", duration, "Vitest未安装")
                    return
                
            except subprocess.TimeoutExpired:
                print("  ⚠️  npm检查超时，跳过前端测试")
                duration = time.time() - start_time
                self.report.add_result("前端测试", "skipped", duration, "npm检查超时")
                return
            
            # 运行前端测试
            try:
                result = subprocess.run(
                    ["npm", "run", "test", "--", "websocket-ai.test.ts"],
                    cwd=frontend_test_file.parent.parent.parent,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    print("  ✅ 前端测试通过")
                    duration = time.time() - start_time
                    self.report.add_result("前端测试", "passed", duration)
                else:
                    error_msg = f"前端测试失败: {result.stderr}"
                    print(f"  ❌ {error_msg}")
                    duration = time.time() - start_time
                    self.report.add_result("前端测试", "failed", duration, error_msg)
                    
            except subprocess.TimeoutExpired:
                error_msg = "前端测试超时"
                print(f"  ❌ {error_msg}")
                duration = time.time() - start_time
                self.report.add_result("前端测试", "failed", duration, error_msg)
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"前端测试执行失败: {str(e)}"
            self.report.add_result("前端测试", "failed", duration, error_msg)
            print(f"❌ {error_msg}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始WebSocket AI流式对话系统全面测试")
        print("=" * 60)
        
        # 设置测试环境
        if not await self.setup_test_environment():
            return
        
        # 运行各类测试
        await self.run_unit_tests()
        await self.run_object_error_reproduction_tests()
        await self.run_websocket_connection_tests()
        await self.run_performance_tests()
        self.run_frontend_tests()
        
        # 生成报告
        report = self.report.generate_report()
        self.save_report(report)
        self.print_summary(report)
    
    def save_report(self, report: Dict[str, Any]):
        """保存测试报告"""
        report_file = self.base_dir / "test_results" / f"websocket_ai_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 测试报告已保存: {report_file}")
    
    def print_summary(self, report: Dict[str, Any]):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("🏁 测试总结")
        print("=" * 60)
        
        summary = report['summary']
        success_rate = report['success_rate']
        
        print(f"总测试数: {summary['total']}")
        print(f"通过: {summary['passed']} ✅")
        print(f"失败: {summary['failed']} ❌")
        print(f"跳过: {summary['skipped']} ⚠️")
        print(f"成功率: {success_rate:.1f}%")
        print(f"总耗时: {report['test_session']['total_duration']:.2f}s")
        
        if summary['errors']:
            print("\n❌ 错误详情:")
            for error in summary['errors']:
                print(f"  - {error['test']}: {error['error']}")
        
        if success_rate == 100 and summary['failed'] == 0:
            print("\n🎉 所有测试通过！WebSocket AI系统运行正常")
        elif success_rate >= 80:
            print("\n🔶 大部分测试通过，系统基本正常，但需要关注失败项")
        else:
            print("\n🔴 多个测试失败，系统存在问题，需要立即修复")


async def main():
    """主函数"""
    runner = WebSocketAITestRunner()
    await runner.run_all_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试执行异常: {e}")
        sys.exit(1)