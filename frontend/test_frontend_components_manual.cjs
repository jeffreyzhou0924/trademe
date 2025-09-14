#!/usr/bin/env node
/**
 * 前端组件手动代码检查测试
 * 分析AI策略生成后立即回测功能的前端实现
 */

const fs = require('fs');
const path = require('path');

class FrontendCodeAnalyzer {
    constructor() {
        this.testResults = {
            total_tests: 0,
            passed_tests: 0,
            failed_tests: 0,
            test_details: [],
            code_analysis: {}
        };
        this.srcPath = path.join(__dirname, 'src');
    }

    logTestResult(testName, success, details) {
        this.testResults.total_tests++;
        if (success) {
            this.testResults.passed_tests++;
            console.log(`✅ PASSED ${testName} - ${details}`);
        } else {
            this.testResults.failed_tests++;
            console.log(`❌ FAILED ${testName} - ${details}`);
        }
        
        this.testResults.test_details.push({
            test_name: testName,
            success,
            details
        });
    }

    readFile(filePath) {
        try {
            return fs.readFileSync(filePath, 'utf8');
        } catch (error) {
            return null;
        }
    }

    searchInFile(content, patterns) {
        const results = {};
        patterns.forEach(pattern => {
            const regex = new RegExp(pattern, 'gi');
            const matches = content.match(regex);
            results[pattern] = matches ? matches.length : 0;
        });
        return results;
    }

    testAIChatPageComponents() {
        console.log('🔍 分析AI对话页面组件...');
        
        const aiChatPagePath = path.join(this.srcPath, 'pages', 'AIChatPage.tsx');
        const content = this.readFile(aiChatPagePath);
        
        if (!content) {
            this.logTestResult('AI对话页面存在性', false, 'AIChatPage.tsx文件不存在');
            return;
        }

        // 检查关键功能
        const patterns = [
            '立即回测',
            'BacktestConfig',
            'autoBacktest',
            'getBacktestProgress',
            'WebSocket',
            'realtime-backtest',
            'aiStore',
            'useState',
            'useEffect'
        ];

        const searchResults = this.searchInFile(content, patterns);
        this.testResults.code_analysis.aiChatPage = searchResults;

        // 评估实现完整性
        const criticalFeatures = ['立即回测', 'autoBacktest', 'getBacktestProgress'];
        const implementedFeatures = criticalFeatures.filter(feature => searchResults[feature] > 0);
        
        const implementationComplete = implementedFeatures.length === criticalFeatures.length;
        
        this.logTestResult(
            'AI对话页面功能实现',
            implementationComplete,
            `实现的关键功能: ${implementedFeatures.length}/${criticalFeatures.length} (${implementedFeatures.join(', ')})`
        );

        // 检查代码质量
        const codeQualityIndicators = ['useState', 'useEffect', 'try', 'catch', 'async', 'await'];
        const qualityScore = codeQualityIndicators.filter(indicator => content.includes(indicator)).length;
        
        this.logTestResult(
            'AI对话页面代码质量',
            qualityScore >= 4,
            `代码质量指标得分: ${qualityScore}/${codeQualityIndicators.length}`
        );
    }

    testTypeDefinitions() {
        console.log('🔍 分析TypeScript类型定义...');
        
        const typesPath = path.join(this.srcPath, 'types', 'aiBacktest.ts');
        const content = this.readFile(typesPath);
        
        if (!content) {
            this.logTestResult('类型定义文件存在性', false, 'aiBacktest.ts文件不存在');
            return;
        }

        // 检查关键类型
        const typePatterns = [
            'AutoBacktestConfig',
            'BacktestProgress',
            'BacktestResults',
            'AIGeneratedStrategy',
            'BacktestHistoryItem'
        ];

        const typeSearchResults = this.searchInFile(content, typePatterns);
        this.testResults.code_analysis.typeDefinitions = typeSearchResults;

        const definedTypes = typePatterns.filter(type => typeSearchResults[type] > 0);
        const typesComplete = definedTypes.length === typePatterns.length;

        this.logTestResult(
            'TypeScript类型定义完整性',
            typesComplete,
            `定义的类型: ${definedTypes.length}/${typePatterns.length} (${definedTypes.join(', ')})`
        );

        // 检查类型的完整性
        const interfaceCount = (content.match(/export interface/g) || []).length;
        this.logTestResult(
            'TypeScript接口数量',
            interfaceCount >= 5,
            `导出的接口数量: ${interfaceCount}`
        );
    }

    testAPIServices() {
        console.log('🔍 分析API服务层...');
        
        const apiPath = path.join(this.srcPath, 'services', 'api', 'ai.ts');
        const content = this.readFile(apiPath);
        
        if (!content) {
            this.logTestResult('API服务文件存在性', false, 'ai.ts API文件不存在');
            return;
        }

        // 检查API方法
        const apiMethods = [
            'getLatestAIStrategy',
            'autoBacktest',
            'getBacktestProgress',
            'getBacktestResults',
            'getAISessionBacktestHistory'
        ];

        const apiSearchResults = this.searchInFile(content, apiMethods);
        this.testResults.code_analysis.apiServices = apiSearchResults;

        const implementedMethods = apiMethods.filter(method => apiSearchResults[method] > 0);
        const apiComplete = implementedMethods.length === apiMethods.length;

        this.logTestResult(
            'API服务方法实现',
            apiComplete,
            `实现的API方法: ${implementedMethods.length}/${apiMethods.length} (${implementedMethods.join(', ')})`
        );

        // 检查错误处理
        const errorHandlingPatterns = ['try', 'catch', 'handleApiError', 'throw'];
        const errorHandlingScore = errorHandlingPatterns.filter(pattern => content.includes(pattern)).length;

        this.logTestResult(
            'API错误处理机制',
            errorHandlingScore >= 3,
            `错误处理得分: ${errorHandlingScore}/${errorHandlingPatterns.length}`
        );
    }

    testStateManagement() {
        console.log('🔍 分析状态管理...');
        
        const storePath = path.join(this.srcPath, 'store', 'aiStore.ts');
        const content = this.readFile(storePath);
        
        if (!content) {
            this.logTestResult('状态管理文件存在性', false, 'aiStore.ts文件不存在');
            return;
        }

        // 检查状态管理功能
        const stateFeatures = [
            'backtest',
            'progress',
            'results',
            'setBacktest',
            'updateProgress',
            'clearBacktest'
        ];

        const stateSearchResults = this.searchInFile(content, stateFeatures);
        this.testResults.code_analysis.stateManagement = stateSearchResults;

        const implementedStateFeatures = stateFeatures.filter(feature => stateSearchResults[feature] > 0);
        const stateComplete = implementedStateFeatures.length >= stateFeatures.length * 0.7; // 70%完成率

        this.logTestResult(
            '状态管理功能实现',
            stateComplete,
            `实现的状态功能: ${implementedStateFeatures.length}/${stateFeatures.length}`
        );

        // 检查Zustand使用
        const zustandPatterns = ['create', 'immer', 'devtools'];
        const zustandScore = zustandPatterns.filter(pattern => content.includes(pattern)).length;

        this.logTestResult(
            'Zustand状态管理集成',
            zustandScore >= 1,
            `Zustand集成得分: ${zustandScore}/${zustandPatterns.length}`
        );
    }

    testBacktestComponents() {
        console.log('🔍 分析回测相关组件...');
        
        const componentsDir = path.join(this.srcPath, 'components');
        const componentFiles = [
            'strategy/BacktestModal.tsx',
            'backtest/BacktestProgress.tsx',
            'backtest/BacktestResults.tsx'
        ];

        let existingComponents = 0;
        const componentAnalysis = {};

        componentFiles.forEach(file => {
            const filePath = path.join(componentsDir, file);
            const content = this.readFile(filePath);
            
            if (content) {
                existingComponents++;
                
                // 分析组件内容
                const componentPatterns = ['useState', 'useEffect', 'props', 'interface', 'export'];
                componentAnalysis[file] = this.searchInFile(content, componentPatterns);
            }
        });

        this.testResults.code_analysis.backtestComponents = componentAnalysis;

        this.logTestResult(
            '回测组件文件存在性',
            existingComponents >= 1,
            `存在的组件文件: ${existingComponents}/${componentFiles.length}`
        );

        // 检查组件质量
        let qualityComponentsCount = 0;
        Object.values(componentAnalysis).forEach(analysis => {
            const qualityScore = analysis.useState + analysis.useEffect + analysis.props;
            if (qualityScore >= 2) qualityComponentsCount++;
        });

        this.logTestResult(
            '回测组件代码质量',
            qualityComponentsCount >= 1,
            `高质量组件数量: ${qualityComponentsCount}`
        );
    }

    testProjectStructure() {
        console.log('🔍 分析项目结构...');
        
        const expectedDirs = [
            'src/components',
            'src/pages',
            'src/services',
            'src/store',
            'src/types',
            'src/utils'
        ];

        let existingDirs = 0;
        expectedDirs.forEach(dir => {
            const dirPath = path.join(__dirname, dir);
            if (fs.existsSync(dirPath)) {
                existingDirs++;
            }
        });

        this.logTestResult(
            '项目目录结构',
            existingDirs === expectedDirs.length,
            `存在的目录: ${existingDirs}/${expectedDirs.length}`
        );

        // 检查package.json依赖
        const packagePath = path.join(__dirname, 'package.json');
        const packageContent = this.readFile(packagePath);
        
        if (packageContent) {
            const packageJson = JSON.parse(packageContent);
            const dependencies = Object.keys(packageJson.dependencies || {});
            const devDependencies = Object.keys(packageJson.devDependencies || {});
            const allDeps = [...dependencies, ...devDependencies];

            const requiredDeps = ['react', 'typescript', 'zustand', 'axios'];
            const foundDeps = requiredDeps.filter(dep => 
                allDeps.some(d => d.includes(dep))
            );

            this.logTestResult(
                '项目依赖完整性',
                foundDeps.length >= requiredDeps.length * 0.8,
                `找到的必需依赖: ${foundDeps.length}/${requiredDeps.length} (${foundDeps.join(', ')})`
            );
        }
    }

    testCodeComplexity() {
        console.log('🔍 分析代码复杂度...');
        
        const mainFiles = [
            'src/pages/AIChatPage.tsx',
            'src/services/api/ai.ts',
            'src/store/aiStore.ts'
        ];

        let totalLines = 0;
        let totalFunctions = 0;
        let totalInterfaces = 0;

        mainFiles.forEach(file => {
            const filePath = path.join(__dirname, file);
            const content = this.readFile(filePath);
            
            if (content) {
                const lines = content.split('\n').length;
                const functions = (content.match(/function|const\s+\w+\s*=|async\s+\w+/g) || []).length;
                const interfaces = (content.match(/interface\s+\w+/g) || []).length;
                
                totalLines += lines;
                totalFunctions += functions;
                totalInterfaces += interfaces;
            }
        });

        this.testResults.code_analysis.complexity = {
            total_lines: totalLines,
            total_functions: totalFunctions,
            total_interfaces: totalInterfaces
        };

        // 评估代码规模
        const codeScaleAppropriate = totalLines >= 1000 && totalLines <= 10000;
        this.logTestResult(
            '代码规模评估',
            codeScaleAppropriate,
            `总代码行数: ${totalLines}, 函数数量: ${totalFunctions}, 接口数量: ${totalInterfaces}`
        );

        // 评估代码组织
        const organizationGood = totalFunctions >= 20 && totalInterfaces >= 5;
        this.logTestResult(
            '代码组织评估',
            organizationGood,
            `函数组织度评分: ${totalFunctions >= 20 ? '✓' : '✗'}, 类型定义完整度: ${totalInterfaces >= 5 ? '✓' : '✗'}`
        );
    }

    runAllTests() {
        console.log('🚀 开始前端代码分析测试');
        console.log('='.repeat(60));
        
        // 1. AI对话页面组件分析
        this.testAIChatPageComponents();
        
        // 2. TypeScript类型定义分析
        this.testTypeDefinitions();
        
        // 3. API服务层分析
        this.testAPIServices();
        
        // 4. 状态管理分析
        this.testStateManagement();
        
        // 5. 回测组件分析
        this.testBacktestComponents();
        
        // 6. 项目结构分析
        this.testProjectStructure();
        
        // 7. 代码复杂度分析
        this.testCodeComplexity();
        
        return this.generateReport();
    }

    generateReport() {
        console.log('\n' + '='.repeat(60));
        console.log('📊 前端代码分析报告');
        console.log('='.repeat(60));
        
        const { total_tests, passed_tests, failed_tests } = this.testResults;
        const successRate = total_tests > 0 ? (passed_tests / total_tests * 100) : 0;
        
        console.log(`总测试数量: ${total_tests}`);
        console.log(`通过测试: ${passed_tests} ✅`);
        console.log(`失败测试: ${failed_tests} ❌`);
        console.log(`测试通过率: ${successRate.toFixed(1)}%`);
        
        // 详细测试结果
        console.log('\n📋 详细测试结果:');
        this.testResults.test_details.forEach(detail => {
            const status = detail.success ? '✅' : '❌';
            console.log(`  ${status} ${detail.test_name}: ${detail.details}`);
        });
        
        // 代码分析统计
        console.log('\n📈 代码分析统计:');
        const analysis = this.testResults.code_analysis;
        
        if (analysis.complexity) {
            console.log(`  总代码行数: ${analysis.complexity.total_lines}`);
            console.log(`  函数总数: ${analysis.complexity.total_functions}`);
            console.log(`  接口总数: ${analysis.complexity.total_interfaces}`);
        }
        
        // 功能实现度评估
        console.log('\n🎯 功能实现度评估:');
        
        const featureAreas = ['AI对话页面', 'API服务', '状态管理', '回测组件'];
        const implementationScores = [];
        
        if (analysis.aiChatPage) {
            const score = Object.values(analysis.aiChatPage).filter(v => v > 0).length;
            implementationScores.push(score);
            console.log(`  AI对话页面: ${score}/9 个功能特征`);
        }
        
        if (analysis.apiServices) {
            const score = Object.values(analysis.apiServices).filter(v => v > 0).length;
            implementationScores.push(score);
            console.log(`  API服务: ${score}/5 个方法`);
        }
        
        if (analysis.stateManagement) {
            const score = Object.values(analysis.stateManagement).filter(v => v > 0).length;
            implementationScores.push(score);
            console.log(`  状态管理: ${score}/6 个功能`);
        }
        
        // 总体评估
        const averageImplementation = implementationScores.length > 0 
            ? implementationScores.reduce((a, b) => a + b, 0) / implementationScores.length 
            : 0;
        
        console.log('\n🏆 总体评估:');
        if (successRate >= 80) {
            console.log('  ✅ AI策略回测集成功能前端实现完整，代码质量良好');
        } else if (successRate >= 60) {
            console.log('  ⚠️  AI策略回测集成功能前端实现基本完整，部分功能需要完善');
        } else {
            console.log('  ❌ AI策略回测集成功能前端实现不完整，需要重要功能开发');
        }
        
        console.log(`  平均功能实现度: ${averageImplementation.toFixed(1)}`);
        console.log(`  代码质量评级: ${successRate >= 80 ? 'A' : successRate >= 60 ? 'B' : 'C'}`);
        
        // 保存报告
        const report = {
            timestamp: new Date().toISOString(),
            summary: {
                total_tests,
                passed_tests,
                failed_tests,
                success_rate: successRate,
                average_implementation: averageImplementation
            },
            test_details: this.testResults.test_details,
            code_analysis: this.testResults.code_analysis
        };
        
        const reportFilename = `frontend_code_analysis_report_${Date.now()}.json`;
        fs.writeFileSync(reportFilename, JSON.stringify(report, null, 2));
        console.log(`\n📄 详细分析报告已保存至: ${reportFilename}`);
        
        return report;
    }
}

// 主函数
function main() {
    const analyzer = new FrontendCodeAnalyzer();
    analyzer.runAllTests();
}

main();