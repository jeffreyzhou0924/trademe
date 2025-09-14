#!/usr/bin/env python3
"""
验证确定性回测修复效果的测试脚本

测试用例：
1. 使用相同参数运行多次确定性回测，验证结果100%一致
2. 与标准回测引擎对比，展示修复效果
3. 验证用户报告的问题已完全解决

用户问题："我选择了两次相同的时间,回测结果还是不一样"
"""

import sys
import os
sys.path.append('/root/trademe/backend/trading-service')

import asyncio
from datetime import datetime, timedelta
from app.services.backtest_service import create_backtest_engine, create_deterministic_backtest_engine
from app.database import get_db
import json
from typing import List, Dict, Any
from loguru import logger

# 配置日志输出
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

class DeterministicBacktestValidator:
    """确定性回测验证器"""
    
    def __init__(self):
        self.test_results = []
    
    async def run_validation_suite(self):
        """运行完整的验证测试套件"""
        
        print("🔧 确定性回测修复效果验证测试")
        print("=" * 60)
        print(f"📅 测试时间: {datetime.now().isoformat()}")
        print(f"🎯 测试目的: 验证相同参数回测结果100%一致")
        print()
        
        # 测试参数 - 使用用户可能选择的典型参数
        test_config = {
            'strategy_id': 62,  # 用户策略
            'user_id': 6,       # 用户ID
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 1, 31),  # 一个月的回测
            'initial_capital': 10000.0,
            'symbol': 'BTC/USDT',
            'random_seed': 42
        }
        
        print(f"📊 测试参数:")
        print(f"   策略ID: {test_config['strategy_id']}")
        print(f"   时间范围: {test_config['start_date'].date()} - {test_config['end_date'].date()}")
        print(f"   初始资金: ${test_config['initial_capital']:,.2f}")
        print(f"   交易对: {test_config['symbol']}")
        print(f"   随机种子: {test_config['random_seed']}")
        print()
        
        # 第一阶段：验证确定性回测的一致性
        await self.test_deterministic_consistency(test_config)
        
        # 第二阶段：对比标准回测的变异性
        await self.test_standard_backtest_variance(test_config)
        
        # 第三阶段：生成最终报告
        self.generate_validation_report()
        
    async def test_deterministic_consistency(self, config: Dict[str, Any]):
        """测试确定性回测的一致性"""
        
        print("🧪 阶段1: 确定性回测一致性验证")
        print("-" * 40)
        
        deterministic_results = []
        
        async for db_session in get_db():
            try:
                # 运行5次确定性回测
                for i in range(5):
                    print(f"🔄 执行第 {i+1} 次确定性回测...")
                    
                    # 创建确定性回测引擎
                    engine = create_deterministic_backtest_engine(config['random_seed'])
                    
                    # 执行回测
                    result = await engine.run_deterministic_backtest(
                        strategy_id=config['strategy_id'],
                        user_id=config['user_id'],
                        start_date=config['start_date'],
                        end_date=config['end_date'],
                        initial_capital=config['initial_capital'],
                        symbol=config['symbol'],
                        session=db_session
                    )
                    
                    deterministic_results.append({
                        'run': i + 1,
                        'final_value': result['final_value'],
                        'trade_count': result['trade_count'],
                        'result_hash': result.get('result_hash', 0),
                        'random_seed': result.get('random_seed', 42),
                        'deterministic': result.get('deterministic', True)
                    })
                    
                    print(f"   ✅ 第{i+1}次: 最终价值=${result['final_value']:.2f}, 交易数={result['trade_count']}, 哈希={result.get('result_hash', 0)}")
                
                break
                
            except Exception as e:
                logger.error(f"确定性回测执行失败: {str(e)}")
                return
        
        # 分析确定性结果
        print("\n📈 确定性回测结果分析:")
        
        first_result = deterministic_results[0]
        all_values_same = all(r['final_value'] == first_result['final_value'] for r in deterministic_results)
        all_trades_same = all(r['trade_count'] == first_result['trade_count'] for r in deterministic_results)
        all_hashes_same = all(r['result_hash'] == first_result['result_hash'] for r in deterministic_results)
        
        print(f"   最终价值一致性: {'✅ 完全一致' if all_values_same else '❌ 存在差异'}")
        print(f"   交易次数一致性: {'✅ 完全一致' if all_trades_same else '❌ 存在差异'}")
        print(f"   结果哈希一致性: {'✅ 完全一致' if all_hashes_same else '❌ 存在差异'}")
        
        if all_values_same and all_trades_same and all_hashes_same:
            print(f"\n🎉 确定性回测验证成功！")
            print(f"   固定结果: 最终价值=${first_result['final_value']:.2f}, 交易数={first_result['trade_count']}")
            self.test_results.append({
                'test': 'deterministic_consistency',
                'status': 'PASSED',
                'details': '相同参数产生完全一致的结果'
            })
        else:
            print(f"\n❌ 确定性回测验证失败！")
            print(f"   价值范围: ${min(r['final_value'] for r in deterministic_results):.2f} - ${max(r['final_value'] for r in deterministic_results):.2f}")
            self.test_results.append({
                'test': 'deterministic_consistency',
                'status': 'FAILED',
                'details': '相同参数产生了不同的结果'
            })
    
    async def test_standard_backtest_variance(self, config: Dict[str, Any]):
        """测试标准回测的变异性（对照组）"""
        
        print(f"\n🔬 阶段2: 标准回测变异性对比")
        print("-" * 40)
        
        standard_results = []
        
        async for db_session in get_db():
            try:
                # 运行3次标准回测作为对比
                for i in range(3):
                    print(f"🔄 执行第 {i+1} 次标准回测...")
                    
                    # 创建标准回测引擎
                    engine = create_backtest_engine()
                    
                    # 使用标准回测方法（如果存在）
                    try:
                        result = await engine.run_backtest(
                            strategy_id=config['strategy_id'],
                            user_id=config['user_id'],
                            start_date=config['start_date'],
                            end_date=config['end_date'],
                            initial_capital=config['initial_capital'],
                            symbol=config['symbol'],
                            session=db_session
                        )
                        
                        standard_results.append({
                            'run': i + 1,
                            'final_value': result.get('final_value', 0),
                            'trade_count': len(result.get('trades', [])),
                        })
                        
                        print(f"   📊 第{i+1}次: 最终价值=${result.get('final_value', 0):.2f}, 交易数={len(result.get('trades', []))}")
                        
                    except Exception as e:
                        logger.warning(f"标准回测第{i+1}次失败: {str(e)}")
                        standard_results.append({
                            'run': i + 1,
                            'final_value': 'ERROR',
                            'trade_count': 'ERROR',
                        })
                
                break
                
            except Exception as e:
                logger.error(f"标准回测对比失败: {str(e)}")
                return
        
        # 分析标准回测结果变异性
        print(f"\n📊 标准回测变异性分析:")
        
        valid_results = [r for r in standard_results if r['final_value'] != 'ERROR']
        
        if len(valid_results) > 1:
            values = [r['final_value'] for r in valid_results]
            value_variance = max(values) - min(values)
            
            print(f"   结果数量: {len(valid_results)}")
            print(f"   价值变异范围: ${min(values):.2f} - ${max(values):.2f}")
            print(f"   价值差异: ${value_variance:.2f}")
            
            if value_variance > 0.01:  # 如果差异超过1分钱
                print(f"   ⚠️ 标准回测存在变异性（这是我们要修复的问题）")
                self.test_results.append({
                    'test': 'standard_variance',
                    'status': 'CONFIRMED',
                    'details': f'标准回测存在${value_variance:.2f}的变异性'
                })
            else:
                print(f"   ✅ 标准回测结果一致")
                self.test_results.append({
                    'test': 'standard_variance',
                    'status': 'CONSISTENT',
                    'details': '标准回测结果意外一致'
                })
        else:
            print(f"   ⚠️ 标准回测执行失败，无法对比")
            self.test_results.append({
                'test': 'standard_variance',
                'status': 'ERROR',
                'details': '标准回测执行失败'
            })
    
    def generate_validation_report(self):
        """生成最终验证报告"""
        
        print(f"\n📋 最终验证报告")
        print("=" * 60)
        
        deterministic_test = next((t for t in self.test_results if t['test'] == 'deterministic_consistency'), None)
        variance_test = next((t for t in self.test_results if t['test'] == 'standard_variance'), None)
        
        print(f"🎯 用户问题: \"我选择了两次相同的时间,回测结果还是不一样\"")
        print()
        
        print(f"📊 测试结果:")
        print(f"   确定性回测一致性: {deterministic_test['status'] if deterministic_test else 'UNKNOWN'}")
        print(f"   标准回测变异性验证: {variance_test['status'] if variance_test else 'UNKNOWN'}")
        print()
        
        if deterministic_test and deterministic_test['status'] == 'PASSED':
            print(f"✅ 修复验证成功!")
            print(f"   🔧 DeterministicBacktestEngine已成功解决回测结果不一致问题")
            print(f"   📈 相同参数现在能够产生100%一致的结果")
            print(f"   🎯 用户报告的问题已完全修复")
            
            success_status = "VALIDATION_PASSED"
        else:
            print(f"❌ 修复验证失败!")
            print(f"   🚨 确定性回测引擎仍存在一致性问题")
            print(f"   🔧 需要进一步调试和修复")
            
            success_status = "VALIDATION_FAILED"
        
        print()
        print(f"🏆 总体状态: {success_status}")
        
        # 保存验证报告
        report = {
            'timestamp': datetime.now().isoformat(),
            'validation_status': success_status,
            'user_issue': "相同参数回测结果不一致",
            'fix_description': "实施DeterministicBacktestEngine确定性回测引擎",
            'test_results': self.test_results,
            'conclusion': "修复验证通过" if success_status == "VALIDATION_PASSED" else "修复验证失败"
        }
        
        with open('/root/trademe/backend/trading-service/deterministic_backtest_validation_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📋 详细报告已保存: deterministic_backtest_validation_report.json")


async def main():
    """主测试函数"""
    validator = DeterministicBacktestValidator()
    await validator.run_validation_suite()


if __name__ == "__main__":
    asyncio.run(main())