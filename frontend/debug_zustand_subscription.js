// 调试Zustand订阅机制的测试脚本
console.log('🔍 [Zustand调试] 开始分析订阅机制问题')

// 模拟当前的messages更新逻辑
function simulateCurrentUpdate() {
  console.log('📊 [测试] 模拟当前的messages更新逻辑')
  
  // 模拟初始state
  const initialState = {
    messages: [
      {
        id: 1,
        role: 'user',
        content: '测试消息',
        metadata: { timestamp: Date.now() }
      },
      {
        id: 2,
        role: 'assistant',
        content: '正在生成策略...',
        metadata: { isStreaming: true, timestamp: Date.now() }
      }
    ]
  }
  
  // 模拟当前的更新逻辑（有问题的逻辑）
  const updatedMessages = [...initialState.messages]
  const streamingMessageIndex = 1
  const currentMessage = updatedMessages[streamingMessageIndex]
  const finalContent = '✅ **策略生成成功！**'
  
  // 问题代码：完全替换metadata
  updatedMessages[streamingMessageIndex] = {
    ...currentMessage,
    content: finalContent,
    metadata: {
      // 移除isStreaming标记，表示已完成
      codeBlock: finalContent.includes('```') ? finalContent : undefined
    }
  }
  
  console.log('❌ [问题分析] 原始metadata:', currentMessage.metadata)
  console.log('❌ [问题分析] 更新后metadata:', updatedMessages[streamingMessageIndex].metadata)
  console.log('⚠️  [问题] timestamp等重要信息丢失！')
  
  return updatedMessages
}

// 推荐的修复逻辑
function simulateFixedUpdate() {
  console.log('🔧 [修复] 推荐的正确更新逻辑')
  
  const initialState = {
    messages: [
      {
        id: 1,
        role: 'user',
        content: '测试消息',
        metadata: { timestamp: Date.now() }
      },
      {
        id: 2,
        role: 'assistant',
        content: '正在生成策略...',
        metadata: { isStreaming: true, timestamp: Date.now(), requestId: 'req_123' }
      }
    ]
  }
  
  // 修复的更新逻辑
  const updatedMessages = [...initialState.messages]
  const streamingMessageIndex = 1
  const currentMessage = updatedMessages[streamingMessageIndex]
  const finalContent = '✅ **策略生成成功！**'
  
  // 正确的metadata合并逻辑
  updatedMessages[streamingMessageIndex] = {
    ...currentMessage,
    content: finalContent,
    metadata: {
      ...currentMessage.metadata, // 保留原有metadata
      isStreaming: undefined, // 移除流式标记
      codeBlock: finalContent.includes('```') ? finalContent : undefined,
      completedAt: Date.now() // 添加完成时间戳
    }
  }
  
  console.log('✅ [修复] 原始metadata:', currentMessage.metadata)
  console.log('✅ [修复] 更新后metadata:', updatedMessages[streamingMessageIndex].metadata)
  console.log('🎯 [成功] 保留了所有重要信息，并添加了新字段')
  
  return updatedMessages
}

// 执行测试
console.log('\n=== 当前有问题的逻辑测试 ===')
const problematicResult = simulateCurrentUpdate()

console.log('\n=== 修复后的逻辑测试 ===')
const fixedResult = simulateFixedUpdate()

console.log('\n🎯 [结论] 问题分析完成：')
console.log('1. metadata对象被完全替换，导致重要信息丢失')
console.log('2. React组件可能依赖某些metadata属性来触发useEffect')
console.log('3. 需要使用spread操作符保留原有metadata')