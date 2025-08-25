#!/usr/bin/env python3
"""
简单的测试脚本，验证核心模块功能
"""

import asyncio
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.abspath('.'))

async def test_database():
    """测试数据库连接"""
    try:
        from app.database import init_db, close_db, check_db_connection
        
        print("🔧 正在初始化数据库...")
        await init_db()
        
        print("🔍 检查数据库连接...")
        is_connected = await check_db_connection()
        
        if is_connected:
            print("✅ 数据库连接成功")
        else:
            print("❌ 数据库连接失败")
        
        await close_db()
        return is_connected
        
    except Exception as e:
        print(f"❌ 数据库测试失败: {e}")
        return False

async def test_config():
    """测试配置"""
    try:
        from app.config import settings
        
        print("🔧 测试配置...")
        print(f"  - App Name: {settings.app_name}")
        print(f"  - Environment: {settings.environment}")
        print(f"  - Database URL: {settings.database_url}")
        print(f"  - Host: {settings.host}:{settings.port}")
        print("✅ 配置加载成功")
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

async def test_models():
    """测试数据模型"""
    try:
        from app.models.user import User
        from app.models.strategy import Strategy
        from app.models.market_data import MarketData
        
        print("🔧 测试数据模型...")
        print("✅ 所有模型导入成功")
        return True
        
    except Exception as e:
        print(f"❌ 模型测试失败: {e}")
        return False

async def test_basic_api():
    """测试基本API路由"""
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        
        # 创建测试客户端，自动处理生命周期事件
        with TestClient(app) as client:
            print("🔧 测试基本API...")
            
            # 测试根路径
            response = client.get("/")
            if response.status_code == 200:
                print("✅ 根路径响应正常")
                data = response.json()
                print(f"  服务: {data.get('service')}")
                print(f"  版本: {data.get('version')}")
                print(f"  状态: {data.get('status')}")
            else:
                print(f"❌ 根路径失败: {response.status_code}")
                print(f"  错误: {response.text}")
                return False
            
            # 测试健康检查
            response = client.get("/health")
            if response.status_code == 200:
                print("✅ 健康检查正常")
                data = response.json()
                print(f"  状态: {data.get('status')}")
                print(f"  环境: {data.get('environment')}")
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                print(f"  错误: {response.text}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("🚀 开始交易服务集成测试")
    print("=" * 50)
    
    tests = [
        ("配置测试", test_config),
        ("数据模型测试", test_models),
        ("数据库测试", test_database),
        ("基本API测试", test_basic_api),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！交易服务基础功能正常")
        return True
    else:
        print("⚠️  部分测试失败，需要修复问题")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)