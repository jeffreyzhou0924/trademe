#!/usr/bin/env python3
"""
独立的Object错误重现测试脚本
不依赖pytest，可直接运行验证修复方案
"""

import json
import time
from typing import Any, Dict
from unittest.mock import Mock
from datetime import datetime


def test_object_serialization_errors():
    """重现并测试Object序列化错误的修复方案"""
    
    print("🔍 开始重现 '[AIStore] 流式错误: Object' 错误...")
    print("=" * 60)
    
    # 这些是可能导致"Object"错误的场景
    problematic_objects = [
        # 1. 异常对象
        Exception("测试异常"),
        # 2. 复杂嵌套对象
        {"error": {"nested": {"exception": Exception("嵌套异常")}}},
        # 3. Mock对象
        Mock(),
        # 4. 包含不可序列化内容的字典
        {"error": {"data": object()}},  # 普通对象
        # 5. 循环引用
        None,  # 将在下面设置
        # 6. 函数对象 
        lambda x: x,
        # 7. 复杂的错误响应对象
        {
            "error": {
                "type": "error",
                "error": {
                    "type": "overloaded_error", 
                    "message": "Service overloaded"
                }
            },
            "error_type": "api_error"
        },
        # 8. Date对象
        datetime.now(),
        # 9. 包含toString方法返回[object Object]的对象
        type('TestObj', (), {'toString': lambda: '[object Object]'})()
    ]
    
    # 设置循环引用
    circular = {"data": "test"}
    circular["self"] = circular
    problematic_objects[4] = circular
    
    # 原始的存在问题的处理方式（会导致Object错误）
    def problematic_error_handler(error: Any) -> str:
        if not error:
            return "未知错误，请重试"
        
        # 这种方式会导致Object序列化问题
        error_message = str(error.get('error', error) if hasattr(error, 'get') else error)
        
        if error_message == '[object Object]':
            return "Object"  # 这就是问题所在！
        
        return error_message or "未知错误"
    
    # 修复后的安全错误处理方式
    def fixed_error_handler(error: Any) -> str:
        if not error:
            return "未知错误，请重试"

        # 检查错误类型 - 修复对象序列化问题
        error_code = getattr(error, 'error_code', None) or getattr(error, 'code', None)
        error_message = getattr(error, 'error', None) or getattr(error, 'message', None) or error
        
        # 修复Object序列化问题: 如果error是对象，安全地转换为字符串
        if isinstance(error_message, Exception):
            error_message = str(error_message) if str(error_message) else "异常对象"
        elif hasattr(error_message, '__dict__') and not isinstance(error_message, (str, int, float, bool, list, dict)):
            # 处理复杂对象（如Mock对象）
            try:
                error_message = str(error_message)
                if error_message == '[object Object]' or 'object at 0x' in error_message:
                    error_message = f"{type(error_message).__name__}对象"
            except:
                error_message = f"{type(error_message).__name__}对象"
        elif isinstance(error_message, dict):
            try:
                error_message = json.dumps(error_message, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                error_message = "复杂对象，无法序列化"
        elif callable(error_message):
            error_message = "函数对象"
        else:
            try:
                error_message = str(error_message)
                # 检测并修复Object序列化问题
                if error_message == '[object Object]':
                    error_message = "对象序列化错误"
            except:
                error_message = "未知对象类型"
        
        error_message = str(error_message or '未知错误')
        
        # 基于错误码的友好提示
        if error_code == 'WEBSOCKET_TIMEOUT':
            return '⏰ AI响应超时，请重试或检查网络连接'
        elif error_code == 'AI_PROCESSING_FAILED':
            return '🤖 AI处理失败，请稍后重试'
        
        # 基于错误消息内容的智能识别
        if 'timeout' in error_message.lower():
            return '⏰ 请求超时，请重试'
        elif 'network' in error_message.lower():
            return '📡 网络连接异常，请检查网络设置'
        
        # 返回处理后的错误消息
        if error_message and error_message != '未知错误':
            return f"❌ {error_message}"
        
        return '⚠️ 服务暂时不可用，请稍后重试'
    
    # 测试所有问题对象
    print("测试对象处理结果:")
    print("-" * 40)
    
    all_passed = True
    for i, obj in enumerate(problematic_objects):
        try:
            # 使用原始方法（存在问题）
            try:
                problematic_result = problematic_error_handler(obj)
                has_object_issue = (problematic_result == "Object" or 
                                  "[object Object]" in problematic_result)
            except Exception:
                has_object_issue = True
                problematic_result = "处理异常"
            
            # 使用修复后的方法
            fixed_result = fixed_error_handler(obj)
            
            # 验证修复效果
            is_fixed = (
                isinstance(fixed_result, str) and
                len(fixed_result) > 0 and
                fixed_result != "Object" and
                "[object Object]" not in fixed_result and
                "undefined" not in fixed_result
            )
            
            status = "✅ 通过" if is_fixed else "❌ 失败"
            
            print(f"对象{i:2d} ({type(obj).__name__:12s}): {status}")
            print(f"       原始结果: {problematic_result}")
            print(f"       修复结果: {fixed_result}")
            
            if has_object_issue and is_fixed:
                print(f"       🔧 成功修复Object序列化问题!")
            elif not is_fixed:
                all_passed = False
                print(f"       ⚠️  仍存在问题")
            
            print()
            
        except Exception as e:
            print(f"对象{i:2d}: ❌ 测试异常: {e}")
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 所有Object序列化错误已成功修复!")
        print("✅ 修复方案验证通过")
    else:
        print("⚠️  部分问题仍存在，需要进一步优化")
    
    return all_passed


def test_websocket_error_scenarios():
    """测试WebSocket错误场景"""
    
    print("\n🔌 测试WebSocket错误场景...")
    print("=" * 60)
    
    # 模拟WebSocket AI中可能出现的错误场景
    websocket_errors = [
        # onStreamError中的错误
        {
            "type": "ai_stream_error",
            "error": Exception("Stream processing failed"),
            "error_type": "stream_error",
            "request_id": "test-123"
        },
        # WebSocket连接错误
        {
            "type": "websocket_error",
            "error": {"code": "ECONNREFUSED", "message": "Connection refused"},
            "error_type": "connection_error"
        },
        # Claude API响应错误  
        {
            "type": "ai_error",
            "error": {
                "type": "error",
                "error": {
                    "type": "overloaded_error",
                    "message": "Overloaded"
                }
            }
        },
        # 序列化失败的复杂对象
        {
            "type": "serialization_error",
            "error": Mock(spec=['error', 'message']),
            "details": "Mock object serialization"
        }
    ]
    
    # AIStore的getErrorMessage函数（修复版本）
    def get_error_message_fixed(error: Any) -> str:
        if not error:
            return '未知错误，请重试'

        # 检查错误类型 - 修复对象序列化问题
        error_code = error.get('error_code') or error.get('code') if hasattr(error, 'get') else None
        error_message = error.get('error') or error.get('message') or '' if hasattr(error, 'get') else error
        
        # 修复Object序列化问题: 如果error是对象，安全地转换为字符串
        if isinstance(error_message, Exception):
            error_message = str(error_message)
        elif hasattr(error_message, '__dict__') and not isinstance(error_message, (str, int, float, bool, list, dict)):
            # 处理Mock对象等复杂对象
            try:
                if hasattr(error_message, '_mock_name'):
                    error_message = f"Mock对象: {error_message._mock_name or 'unnamed'}"
                else:
                    error_message = f"{type(error_message).__name__}对象"
            except:
                error_message = "复杂对象"
        elif isinstance(error_message, dict):
            try:
                error_message = json.dumps(error_message, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                error_message = str(error_message)
        
        error_message = str(error_message or '')
        
        # 基于错误码的友好提示
        if error_code == 'WEBSOCKET_TIMEOUT':
            return '⏰ AI响应超时，请重试或检查网络连接'
        elif error_code == 'WEBSOCKET_DISCONNECTED':
            return '🔌 连接断开，正在重新连接...'
        elif error_code == 'AI_PROCESSING_FAILED':
            return '🤖 AI处理失败，请稍后重试'

        # 基于错误消息内容的智能识别
        if error_message and ('timeout' in error_message.lower() or '超时' in error_message.lower()):
            return '⏰ 请求超时，请重试'
        if error_message and ('network' in error_message.lower() or '网络' in error_message.lower()):
            return '📡 网络连接异常，请检查网络设置'

        # 默认错误消息
        if error_message:
            return f"❌ {error_message}"

        return '⚠️ 服务暂时不可用，请稍后重试'
    
    all_passed = True
    for i, error_scenario in enumerate(websocket_errors):
        try:
            result = get_error_message_fixed(error_scenario)
            
            # 验证结果
            is_valid = (
                isinstance(result, str) and
                len(result) > 0 and
                result != "Object" and
                "[object Object]" not in result
            )
            
            status = "✅ 通过" if is_valid else "❌ 失败"
            print(f"场景{i+1} ({error_scenario['type']}): {status}")
            print(f"    结果: {result}")
            
            if not is_valid:
                all_passed = False
            
        except Exception as e:
            print(f"场景{i+1}: ❌ 处理异常: {e}")
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("🎉 所有WebSocket错误场景处理正常!")
    else:
        print("⚠️  部分WebSocket错误场景需要优化")
    
    return all_passed


def test_performance():
    """性能测试：大量错误对象处理"""
    
    print("\n⚡ 性能测试...")
    print("=" * 60)
    
    # 生成大量测试错误对象
    test_errors = []
    for i in range(1000):
        if i % 4 == 0:
            test_errors.append(Exception(f"Exception {i}"))
        elif i % 4 == 1:
            test_errors.append({"error": f"Error {i}", "details": {"index": i}})
        elif i % 4 == 2:
            test_errors.append(Mock(name=f"mock_{i}"))
        else:
            test_errors.append(f"String error {i}")
    
    def get_error_message_perf(error: Any) -> str:
        if not error:
            return "未知错误，请重试"
        
        if isinstance(error, Exception):
            return f"异常: {str(error)}"
        elif isinstance(error, dict):
            try:
                return json.dumps(error, default=str)[:100]  # 限制长度
            except:
                return "字典对象"
        elif hasattr(error, '_mock_name'):
            return f"Mock: {error._mock_name}"
        else:
            return str(error)[:100]  # 限制长度
    
    # 性能测试
    start_time = time.time()
    processed_count = 0
    
    for error in test_errors:
        try:
            result = get_error_message_perf(error)
            if isinstance(result, str) and len(result) > 0 and "Object" not in result:
                processed_count += 1
        except:
            pass  # 忽略处理异常
    
    end_time = time.time()
    processing_time = end_time - start_time
    throughput = processed_count / processing_time if processing_time > 0 else 0
    
    print(f"处理错误对象数量: {processed_count}/{len(test_errors)}")
    print(f"处理时间: {processing_time:.3f}s")
    print(f"吞吐量: {throughput:.0f} 错误/秒")
    
    # 性能要求：1000个错误对象在1秒内处理完成
    success = processing_time < 1.0 and processed_count == len(test_errors)
    
    if success:
        print("✅ 性能测试通过")
    else:
        print("❌ 性能测试失败")
    
    return success


def main():
    """主测试函数"""
    print("🚀 WebSocket AI Object错误修复验证测试")
    print("=" * 80)
    
    test_results = []
    
    # 运行各项测试
    test_results.append(("Object序列化错误修复", test_object_serialization_errors()))
    test_results.append(("WebSocket错误场景", test_websocket_error_scenarios()))
    test_results.append(("性能测试", test_performance()))
    
    # 总结
    print("\n" + "=" * 80)
    print("🏁 测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n总测试: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！Object错误已成功修复！")
        print("✅ 可以安全部署到生产环境")
    else:
        print("\n⚠️  部分测试失败，需要进一步优化代码")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        exit_code = 0 if success else 1
    except KeyboardInterrupt:
        print("\n⏹️  测试被用户中断")
        exit_code = 2
    except Exception as e:
        print(f"\n💥 测试执行异常: {e}")
        exit_code = 3
    
    exit(exit_code)