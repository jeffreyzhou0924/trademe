/**
 * 前端组件功能测试脚本
 * 测试AI策略生成后立即回测功能的前端界面
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

class FrontendComponentTester {
    constructor() {
        this.browser = null;
        this.page = null;
        this.testResults = {
            total_tests: 0,
            passed_tests: 0,
            failed_tests: 0,
            test_details: [],
            screenshots: [],
            performance_metrics: {}
        };
        this.baseUrl = 'http://43.167.252.120';
    }

    async setup() {
        console.log('🚀 启动浏览器测试环境...');
        this.browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        this.page = await this.browser.newPage();
        
        // 设置视窗大小
        await this.page.setViewport({ width: 1920, height: 1080 });
        
        // 监听控制台错误
        this.page.on('console', msg => {
            if (msg.type() === 'error') {
                console.log('❌ 前端控制台错误:', msg.text());
            }
        });
        
        // 监听页面错误
        this.page.on('pageerror', error => {
            console.log('❌ 页面JavaScript错误:', error.message);
        });
    }

    async teardown() {
        if (this.browser) {
            await this.browser.close();
        }
    }

    logTestResult(testName, success, details, executionTime = 0) {
        this.testResults.total_tests++;
        if (success) {
            this.testResults.passed_tests++;
            console.log(`✅ PASSED ${testName} - ${details} (${executionTime.toFixed(3)}s)`);
        } else {
            this.testResults.failed_tests++;
            console.log(`❌ FAILED ${testName} - ${details} (${executionTime.toFixed(3)}s)`);
        }
        
        this.testResults.test_details.push({
            test_name: testName,
            success,
            details,
            execution_time: executionTime
        });
    }

    async takeScreenshot(name) {
        const filename = `screenshot_${name}_${Date.now()}.png`;
        await this.page.screenshot({ path: filename, fullPage: true });
        this.testResults.screenshots.push(filename);
        console.log(`📸 截图保存: ${filename}`);
        return filename;
    }

    async login() {
        console.log('🔐 执行用户登录...');
        const startTime = Date.now();
        
        try {
            await this.page.goto(`${this.baseUrl}/login`);
            await this.page.waitForSelector('input[type="email"]', { timeout: 10000 });
            
            // 输入测试用户凭据
            await this.page.type('input[type="email"]', 'publictest@example.com');
            await this.page.type('input[type="password"]', 'PublicTest123!');
            
            // 点击登录按钮
            await this.page.click('button[type="submit"]');
            
            // 等待登录成功跳转
            await this.page.waitForNavigation({ timeout: 10000 });
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('用户登录', true, '登录成功', executionTime);
            
            await this.takeScreenshot('login_success');
            return true;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('用户登录', false, `登录失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testAIChatPageAccess() {
        console.log('📱 测试AI对话页面访问...');
        const startTime = Date.now();
        
        try {
            await this.page.goto(`${this.baseUrl}/ai-chat`);
            await this.page.waitForSelector('.ai-chat-container', { timeout: 15000 });
            
            // 检查页面关键元素
            const titleExists = await this.page.$eval('h1, .page-title', el => el.textContent.includes('AI助手') || el.textContent.includes('AI对话'));
            const chatInputExists = await this.page.$('textarea, input[placeholder*="输入"], input[placeholder*="聊天"]') !== null;
            const sessionListExists = await this.page.$('.session-list, .chat-sessions') !== null;
            
            const allElementsPresent = titleExists && chatInputExists && sessionListExists;
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                'AI对话页面访问', 
                allElementsPresent, 
                `页面元素检查 - 标题:${titleExists}, 输入框:${chatInputExists}, 会话列表:${sessionListExists}`,
                executionTime
            );
            
            await this.takeScreenshot('ai_chat_page');
            return allElementsPresent;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('AI对话页面访问', false, `页面访问失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testStrategyGenerationUI() {
        console.log('🤖 测试策略生成UI...');
        const startTime = Date.now();
        
        try {
            // 查找聊天输入框
            const chatInput = await this.page.$('textarea, input[type="text"]:not([type="email"]):not([type="password"])');
            if (!chatInput) {
                throw new Error('找不到聊天输入框');
            }
            
            // 输入策略描述
            await this.page.focus('textarea, input[type="text"]:not([type="email"]):not([type="password"])');
            await this.page.type('textarea, input[type="text"]:not([type="email"]):not([type="password"])', '请帮我设计一个简单的MACD策略用于BTC交易');
            
            // 查找发送按钮
            const sendButton = await this.page.$('button[type="submit"], button:has-text("发送"), .send-button');
            if (sendButton) {
                await sendButton.click();
            } else {
                // 尝试按回车键
                await this.page.keyboard.press('Enter');
            }
            
            // 等待AI响应
            await this.page.waitForTimeout(3000);
            
            // 检查是否有回测按钮出现
            const backtestButton = await this.page.$('button:has-text("立即回测"), button:has-text("回测"), .backtest-button');
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                '策略生成UI测试', 
                backtestButton !== null, 
                backtestButton ? '发现回测按钮' : '未发现回测按钮',
                executionTime
            );
            
            await this.takeScreenshot('strategy_generation');
            return backtestButton !== null;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('策略生成UI测试', false, `策略生成测试失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testBacktestConfigModal() {
        console.log('⚙️ 测试回测配置模态框...');
        const startTime = Date.now();
        
        try {
            // 查找并点击回测按钮
            const backtestButton = await this.page.$('button:has-text("立即回测"), button:has-text("回测"), .backtest-button');
            if (!backtestButton) {
                throw new Error('找不到回测按钮');
            }
            
            await backtestButton.click();
            
            // 等待模态框出现
            await this.page.waitForSelector('.modal, .dialog, .popup', { timeout: 5000 });
            
            // 检查模态框内的配置项
            const symbolInput = await this.page.$('select[name="symbol"], input[name="symbol"]') !== null;
            const timeframeInput = await this.page.$('select[name="timeframe"], input[name="timeframe"]') !== null;
            const capitalInput = await this.page.$('input[name="capital"], input[name="initialCapital"]') !== null;
            const submitButton = await this.page.$('button[type="submit"], button:has-text("开始"), button:has-text("启动")') !== null;
            
            const configElementsPresent = symbolInput && timeframeInput && capitalInput && submitButton;
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                '回测配置模态框', 
                configElementsPresent, 
                `配置项检查 - 交易对:${symbolInput}, 时间框架:${timeframeInput}, 资金:${capitalInput}, 提交按钮:${submitButton}`,
                executionTime
            );
            
            await this.takeScreenshot('backtest_config_modal');
            return configElementsPresent;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('回测配置模态框', false, `配置模态框测试失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testBacktestExecution() {
        console.log('🚀 测试回测执行...');
        const startTime = Date.now();
        
        try {
            // 提交回测配置
            const submitButton = await this.page.$('button[type="submit"], button:has-text("开始"), button:has-text("启动")');
            if (submitButton) {
                await submitButton.click();
            }
            
            // 等待进度显示
            await this.page.waitForTimeout(2000);
            
            // 检查进度显示元素
            const progressBar = await this.page.$('.progress, .progress-bar') !== null;
            const statusText = await this.page.$('.status, .step') !== null;
            const logsArea = await this.page.$('.logs, .console') !== null;
            
            const progressElementsPresent = progressBar || statusText || logsArea;
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                '回测执行测试', 
                progressElementsPresent, 
                `进度显示检查 - 进度条:${progressBar}, 状态文本:${statusText}, 日志区域:${logsArea}`,
                executionTime
            );
            
            await this.takeScreenshot('backtest_execution');
            return progressElementsPresent;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('回测执行测试', false, `回测执行测试失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testResponsiveDesign() {
        console.log('📱 测试响应式设计...');
        const startTime = Date.now();
        
        try {
            const viewports = [
                { width: 1920, height: 1080, name: '桌面端' },
                { width: 768, height: 1024, name: '平板端' },
                { width: 375, height: 667, name: '移动端' }
            ];
            
            let responsiveTestsPassed = 0;
            
            for (const viewport of viewports) {
                await this.page.setViewport(viewport);
                await this.page.waitForTimeout(1000);
                
                // 检查关键元素是否可见
                const elementsVisible = await this.page.evaluate(() => {
                    const keyElements = document.querySelectorAll('.ai-chat-container, .chat-input, .session-list');
                    return Array.from(keyElements).every(el => {
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    });
                });
                
                if (elementsVisible) {
                    responsiveTestsPassed++;
                }
                
                await this.takeScreenshot(`responsive_${viewport.name}`);
            }
            
            const allViewportsWorking = responsiveTestsPassed === viewports.length;
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                '响应式设计测试', 
                allViewportsWorking, 
                `通过的视窗: ${responsiveTestsPassed}/${viewports.length}`,
                executionTime
            );
            
            // 恢复默认视窗
            await this.page.setViewport({ width: 1920, height: 1080 });
            
            return allViewportsWorking;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('响应式设计测试', false, `响应式测试失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async testPerformance() {
        console.log('⚡ 测试前端性能...');
        const startTime = Date.now();
        
        try {
            // 页面加载性能测试
            const navigationStart = await this.page.evaluate(() => performance.timing.navigationStart);
            const loadComplete = await this.page.evaluate(() => performance.timing.loadEventEnd);
            const loadTime = (loadComplete - navigationStart) / 1000;
            
            // 内存使用测试
            const memoryInfo = await this.page.evaluate(() => {
                if (performance.memory) {
                    return {
                        usedJSHeapSize: performance.memory.usedJSHeapSize,
                        totalJSHeapSize: performance.memory.totalJSHeapSize,
                        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
                    };
                }
                return null;
            });
            
            // 运行时性能测试
            const runtimeStart = performance.now();
            await this.page.evaluate(() => {
                // 模拟一些前端操作
                for (let i = 0; i < 1000; i++) {
                    document.querySelector('body');
                }
            });
            const runtimeEnd = performance.now();
            const runtimeDuration = (runtimeEnd - runtimeStart) / 1000;
            
            this.testResults.performance_metrics = {
                page_load_time: loadTime,
                memory_info: memoryInfo,
                runtime_performance: runtimeDuration
            };
            
            const performanceGood = loadTime < 5.0 && runtimeDuration < 0.1;
            
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult(
                '前端性能测试', 
                performanceGood, 
                `加载时间:${loadTime.toFixed(2)}s, 运行时间:${runtimeDuration.toFixed(3)}s`,
                executionTime
            );
            
            return performanceGood;
            
        } catch (error) {
            const executionTime = (Date.now() - startTime) / 1000;
            this.logTestResult('前端性能测试', false, `性能测试失败: ${error.message}`, executionTime);
            return false;
        }
    }

    async runAllTests() {
        console.log('🚀 开始前端组件功能测试');
        console.log('='.repeat(60));
        
        const overallStartTime = Date.now();
        
        try {
            await this.setup();
            
            // 1. 用户登录测试
            const loginSuccess = await this.login();
            if (!loginSuccess) {
                console.log('❌ 登录失败，跳过后续测试');
                return this.generateReport();
            }
            
            // 2. AI对话页面访问测试
            await this.testAIChatPageAccess();
            
            // 3. 策略生成UI测试
            const strategyUIWorking = await this.testStrategyGenerationUI();
            
            // 4. 回测配置模态框测试（如果策略生成UI工作）
            if (strategyUIWorking) {
                await this.testBacktestConfigModal();
                
                // 5. 回测执行测试
                await this.testBacktestExecution();
            }
            
            // 6. 响应式设计测试
            await this.testResponsiveDesign();
            
            // 7. 前端性能测试
            await this.testPerformance();
            
        } catch (error) {
            console.log(`❌ 测试执行异常: ${error.message}`);
        } finally {
            await this.teardown();
        }
        
        const overallExecutionTime = (Date.now() - overallStartTime) / 1000;
        console.log(`\n总测试执行时间: ${overallExecutionTime.toFixed(3)}秒`);
        
        return this.generateReport();
    }

    generateReport() {
        console.log('\n' + '='.repeat(60));
        console.log('📊 前端组件测试报告');
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
            console.log(`  ${status} ${detail.test_name}: ${detail.details} (${detail.execution_time.toFixed(3)}s)`);
        });
        
        // 性能指标
        if (this.testResults.performance_metrics) {
            console.log('\n⚡ 性能指标:');
            const metrics = this.testResults.performance_metrics;
            if (metrics.page_load_time) {
                console.log(`  页面加载时间: ${metrics.page_load_time.toFixed(2)}秒`);
            }
            if (metrics.runtime_performance) {
                console.log(`  运行时性能: ${metrics.runtime_performance.toFixed(3)}秒`);
            }
            if (metrics.memory_info) {
                const memMB = (metrics.memory_info.usedJSHeapSize / 1024 / 1024).toFixed(2);
                console.log(`  内存使用: ${memMB}MB`);
            }
        }
        
        // 截图文件
        if (this.testResults.screenshots.length > 0) {
            console.log('\n📸 测试截图:');
            this.testResults.screenshots.forEach(screenshot => {
                console.log(`  - ${screenshot}`);
            });
        }
        
        // 保存报告
        const report = {
            timestamp: new Date().toISOString(),
            summary: {
                total_tests,
                passed_tests,
                failed_tests,
                success_rate: successRate
            },
            test_details: this.testResults.test_details,
            performance_metrics: this.testResults.performance_metrics,
            screenshots: this.testResults.screenshots
        };
        
        const reportFilename = `frontend_test_report_${Date.now()}.json`;
        fs.writeFileSync(reportFilename, JSON.stringify(report, null, 2));
        console.log(`\n📄 详细测试报告已保存至: ${reportFilename}`);
        
        return report;
    }
}

// 主函数
async function main() {
    const tester = new FrontendComponentTester();
    try {
        await tester.runAllTests();
    } catch (error) {
        console.error('测试执行失败:', error);
    }
}

main().catch(console.error);