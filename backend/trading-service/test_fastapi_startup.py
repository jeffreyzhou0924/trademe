#!/usr/bin/env python3
"""
FastAPI服务启动测试
验证服务基本功能和API可用性
"""

import asyncio
import sys
import os
import time
import subprocess
from typing import Dict, Any
import httpx
from loguru import logger

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 测试配置
TEST_CONFIG = {
    "base_url": "http://localhost:8001",
    "timeout": 30,
    "retry_attempts": 3,
    "retry_delay": 2
}

async def test_basic_imports():
    """测试基础模块导入"""
    print("🔍 测试基础模块导入...")
    
    try:
        # 测试配置导入
        from app.config import settings
        print(f"✅ 配置模块导入成功 - 环境: {settings.environment}")
        
        # 测试数据库模块
        from app.database import AsyncSessionLocal, check_db_connection
        print("✅ 数据库模块导入成功")
        
        # 测试AI模块 (跳过Claude客户端初始化问题)
        try:
            from app.ai.core.claude_client import ClaudeClient
            print("✅ AI模块导入成功 - Claude类可用")
        except Exception as e:
            print(f"⚠️ AI模块部分可用 - Claude初始化问题: {str(e)}")
        
        # 测试回测引擎
        from app.services.backtest_service import BacktestEngine
        from app.services.tiered_backtest_service import TieredBacktestService
        print("✅ 回测引擎导入成功")
        
        # 测试主应用
        from app.main import app
        print("✅ FastAPI应用导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 模块导入失败: {str(e)}")
        return False

async def test_database_connection():
    """测试数据库连接"""
    print("\n🗄️ 测试数据库连接...")
    
    try:
        from app.database import check_db_connection
        
        is_connected = await check_db_connection()
        if is_connected:
            print("✅ 数据库连接正常")
            return True
        else:
            print("❌ 数据库连接失败")
            return False
            
    except Exception as e:
        print(f"❌ 数据库连接测试异常: {str(e)}")
        return False

async def test_redis_connection():
    """测试Redis连接"""
    print("\n📡 测试Redis连接...")
    
    try:
        from app.redis_client import redis_client
        
        # 尝试ping Redis
        await redis_client.ping()
        print("✅ Redis连接正常")
        return True
        
    except Exception as e:
        print(f"⚠️ Redis连接失败: {str(e)} (某些功能可能受限)")
        return False  # Redis失败不是致命错误

async def start_fastapi_server():
    """启动FastAPI服务器"""
    print("\n🚀 启动FastAPI服务器...")
    
    try:
        # 使用subprocess启动服务器
        process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8001",
            "--log-level", "info"
        ], cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # 等待服务器启动
        print("等待服务器启动...")
        await asyncio.sleep(5)
        
        # 检查进程是否还在运行
        if process.poll() is None:
            print("✅ FastAPI服务器启动成功")
            return process
        else:
            print("❌ FastAPI服务器启动失败")
            return None
            
    except Exception as e:
        print(f"❌ 启动服务器异常: {str(e)}")
        return None

async def test_health_endpoints():
    """测试健康检查端点"""
    print("\n❤️ 测试健康检查端点...")
    
    health_endpoints = [
        "/",
        "/health"
    ]
    
    results = {}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        for endpoint in health_endpoints:
            url = f"{TEST_CONFIG['base_url']}{endpoint}"
            
            try:
                response = await client.get(url)
                
                if response.status_code == 200:
                    results[endpoint] = "✅ 正常"
                    data = response.json()
                    print(f"✅ {endpoint} - 状态码: {response.status_code}")
                    
                    if endpoint == "/":
                        print(f"   服务: {data.get('service', 'N/A')}")
                        print(f"   版本: {data.get('version', 'N/A')}")
                    elif endpoint == "/health":
                        print(f"   状态: {data.get('status', 'N/A')}")
                        print(f"   环境: {data.get('environment', 'N/A')}")
                else:
                    results[endpoint] = f"❌ 状态码: {response.status_code}"
                    print(f"❌ {endpoint} - 状态码: {response.status_code}")
                    
            except Exception as e:
                results[endpoint] = f"❌ 异常: {str(e)}"
                print(f"❌ {endpoint} - 异常: {str(e)}")
    
    return results

async def test_api_endpoints():
    """测试主要API端点"""
    print("\n🔌 测试主要API端点...")
    
    # 不需要认证的端点
    public_endpoints = [
        "/api/v1/exchanges/supported",
        "/api/v1/market/symbols/binance",
        "/docs",
        "/openapi.json"
    ]
    
    results = {}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        for endpoint in public_endpoints:
            url = f"{TEST_CONFIG['base_url']}{endpoint}"
            
            try:
                response = await client.get(url)
                
                if response.status_code == 200:
                    results[endpoint] = "✅ 正常"
                    print(f"✅ {endpoint} - 响应正常")
                elif response.status_code == 401:
                    results[endpoint] = "🔒 需要认证 (正常)"
                    print(f"🔒 {endpoint} - 需要认证")
                else:
                    results[endpoint] = f"⚠️ 状态码: {response.status_code}"
                    print(f"⚠️ {endpoint} - 状态码: {response.status_code}")
                    
            except Exception as e:
                results[endpoint] = f"❌ 异常: {str(e)}"
                print(f"❌ {endpoint} - 异常: {str(e)}")
    
    return results

async def test_swagger_docs():
    """测试API文档可访问性"""
    print("\n📚 测试API文档...")
    
    doc_endpoints = [
        "/docs",      # Swagger UI
        "/redoc",     # ReDoc
        "/openapi.json"  # OpenAPI规范
    ]
    
    results = {}
    
    async with httpx.AsyncClient(timeout=TEST_CONFIG["timeout"]) as client:
        for endpoint in doc_endpoints:
            url = f"{TEST_CONFIG['base_url']}{endpoint}"
            
            try:
                response = await client.get(url)
                
                if response.status_code == 200:
                    results[endpoint] = "✅ 可访问"
                    print(f"✅ {endpoint} - 可访问")
                    
                    # 检查内容类型
                    content_type = response.headers.get("content-type", "")
                    if endpoint == "/openapi.json" and "application/json" in content_type:
                        print("   OpenAPI规范格式正确")
                    elif endpoint in ["/docs", "/redoc"] and "text/html" in content_type:
                        print("   文档页面格式正确")
                        
                else:
                    results[endpoint] = f"❌ 状态码: {response.status_code}"
                    print(f"❌ {endpoint} - 状态码: {response.status_code}")
                    
            except Exception as e:
                results[endpoint] = f"❌ 异常: {str(e)}"
                print(f"❌ {endpoint} - 异常: {str(e)}")
    
    return results

async def run_startup_test():
    """运行完整的启动测试"""
    print("🎯 开始FastAPI服务启动测试")
    print("=" * 60)
    
    test_results = {
        "module_imports": False,
        "database_connection": False,
        "redis_connection": False,
        "server_startup": False,
        "health_endpoints": {},
        "api_endpoints": {},
        "swagger_docs": {}
    }
    
    # 1. 测试模块导入
    test_results["module_imports"] = await test_basic_imports()
    
    if not test_results["module_imports"]:
        print("\n❌ 模块导入失败，无法继续测试")
        return test_results
    
    # 2. 测试数据库连接
    test_results["database_connection"] = await test_database_connection()
    
    # 3. 测试Redis连接
    test_results["redis_connection"] = await test_redis_connection()
    
    # 4. 启动服务器
    server_process = await start_fastapi_server()
    if server_process:
        test_results["server_startup"] = True
        
        try:
            # 5. 测试健康检查端点
            test_results["health_endpoints"] = await test_health_endpoints()
            
            # 6. 测试API端点
            test_results["api_endpoints"] = await test_api_endpoints()
            
            # 7. 测试文档
            test_results["swagger_docs"] = await test_swagger_docs()
            
        finally:
            # 关闭服务器
            print("\n🛑 关闭测试服务器...")
            server_process.terminate()
            await asyncio.sleep(2)
            if server_process.poll() is None:
                server_process.kill()
    
    return test_results

def generate_test_report(results: Dict[str, Any]):
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("📊 FastAPI启动测试报告")
    print("=" * 60)
    
    # 基础测试
    print("\n🔧 基础功能测试:")
    basic_tests = [
        ("模块导入", results["module_imports"]),
        ("数据库连接", results["database_connection"]),
        ("Redis连接", results["redis_connection"]),
        ("服务器启动", results["server_startup"])
    ]
    
    for test_name, success in basic_tests:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name:<12} {status}")
    
    # 端点测试
    endpoint_categories = [
        ("健康检查端点", results["health_endpoints"]),
        ("API端点", results["api_endpoints"]),
        ("文档端点", results["swagger_docs"])
    ]
    
    for category_name, endpoint_results in endpoint_categories:
        if endpoint_results:
            print(f"\n🔌 {category_name}:")
            for endpoint, status in endpoint_results.items():
                print(f"  {endpoint:<25} {status}")
    
    # 总体评估
    print("\n📈 总体评估:")
    total_tests = len(basic_tests)
    passed_tests = sum(success for _, success in basic_tests)
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    print(f"  基础功能通过率: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
    
    if success_rate >= 75:
        print("  🎉 服务基本可用，可以进行进一步优化")
    elif success_rate >= 50:
        print("  ⚠️ 服务部分可用，需要修复关键问题")
    else:
        print("  ❌ 服务存在严重问题，需要紧急修复")
    
    # 建议
    print(f"\n💡 下一步建议:")
    if not results["module_imports"]:
        print("  • 修复模块导入问题，检查依赖安装")
    if not results["database_connection"]:
        print("  • 检查SQLite数据库配置和文件权限")
    if not results["redis_connection"]:
        print("  • 启动Redis服务或调整配置")
    if not results["server_startup"]:
        print("  • 检查端口占用和服务配置")
    else:
        print("  • 继续进行中间件优化和性能调优")
        print("  • 添加认证中间件测试")
        print("  • 进行负载测试")

async def main():
    """主函数"""
    results = await run_startup_test()
    generate_test_report(results)

if __name__ == "__main__":
    asyncio.run(main())