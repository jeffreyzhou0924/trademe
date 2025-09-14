// 快速修复脚本：为MACD策略添加回测按钮
(function() {
    'use strict';
    
    console.log('🔧 [快速修复] MACD回测按钮修复脚本已加载');
    
    // 等待页面加载完成
    function waitForElement(selector, callback) {
        const element = document.querySelector(selector);
        if (element) {
            callback(element);
        } else {
            setTimeout(() => waitForElement(selector, callback), 500);
        }
    }
    
    // 检测MACD策略
    function detectMACDStrategy() {
        const messages = document.querySelectorAll('.message-content, [class*="message"], [class*="ai-"]');
        let hasMACDStrategy = false;
        
        messages.forEach(msg => {
            const content = msg.textContent || msg.innerText;
            if (content.includes('🚀 **开始生成MACD顶背离加仓策略代码！**') ||
                content.includes('MACD顶背离加仓策略') ||
                content.includes('MACD') && content.includes('策略') && content.includes('生成')) {
                hasMACDStrategy = true;
            }
        });
        
        return hasMACDStrategy;
    }
    
    // 创建回测按钮
    function createBacktestButton() {
        if (document.getElementById('quick-backtest-button')) {
            return; // 已经存在
        }
        
        const button = document.createElement('div');
        button.id = 'quick-backtest-button';
        button.innerHTML = `
            <div style="
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px 25px;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s ease;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 300px;
                text-align: center;
                " onmouseover="this.style.transform='translateY(-3px) scale(1.02)'" 
                onmouseout="this.style.transform='translateY(0) scale(1)'">
                
                <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <span style="font-size: 18px;">📊</span>
                    <span>MACD策略回测</span>
                </div>
                <div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">
                    点击进入专业回测界面
                </div>
            </div>
        `;
        
        button.onclick = function() {
            // 优先尝试调用React应用的回测功能
            if (typeof window.triggerBacktestModal === 'function') {
                const success = window.triggerBacktestModal();
                if (success) {
                    // 显示成功提示
                    const toast = document.createElement('div');
                    toast.innerHTML = `
                        <div style="
                            position: fixed;
                            top: 20px;
                            right: 20px;
                            z-index: 10001;
                            background: #10B981;
                            color: white;
                            padding: 12px 20px;
                            border-radius: 8px;
                            font-weight: 500;
                            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.3);
                        ">
                            ✅ 正在打开回测配置界面...
                        </div>
                    `;
                    document.body.appendChild(toast);
                    
                    setTimeout(() => {
                        if (toast.parentNode) {
                            toast.parentNode.removeChild(toast);
                        }
                    }, 3000);
                    return;
                }
            }
            
            // 降级处理：显示集成提示
            const toast = document.createElement('div');
            toast.innerHTML = `
                <div style="
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 10001;
                    background: #F59E0B;
                    color: white;
                    padding: 12px 20px;
                    border-radius: 8px;
                    font-weight: 500;
                    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.3);
                ">
                    ⚠️ 回测功能正在集成中...
                </div>
            `;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 3000);
        };
        
        document.body.appendChild(button);
        console.log('✅ [快速修复] MACD回测按钮已添加');
    }
    
    // 主函数
    function init() {
        // 检查是否在AI对话页面
        if (!window.location.pathname.includes('/ai-chat') && 
            !window.location.pathname.includes('/ai') &&
            !document.querySelector('[class*="ai"]')) {
            console.log('⚠️ [快速修复] 不在AI对话页面，跳过修复');
            return;
        }
        
        // 等待页面元素加载
        waitForElement('body', () => {
            setTimeout(() => {
                if (detectMACDStrategy()) {
                    createBacktestButton();
                    console.log('🎯 [快速修复] 检测到MACD策略，回测按钮已激活');
                } else {
                    console.log('ℹ️ [快速修复] 未检测到MACD策略');
                    
                    // 监听页面变化，动态检测
                    const observer = new MutationObserver(() => {
                        if (detectMACDStrategy()) {
                            createBacktestButton();
                            observer.disconnect();
                        }
                    });
                    
                    observer.observe(document.body, {
                        childList: true,
                        subtree: true,
                        characterData: true
                    });
                }
            }, 1000);
        });
    }
    
    // 页面加载完成后执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // 导出到全局，方便手动调用
    window.enableMACDBacktest = function() {
        createBacktestButton();
        console.log('🔧 [手动调用] MACD回测按钮已强制启用');
    };
    
})();