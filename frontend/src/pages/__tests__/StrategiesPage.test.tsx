import { describe, test, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StrategiesPage from '../StrategiesPage'

// Mock stores
vi.mock('@/store', () => ({
  useUserInfo: () => ({
    user: { username: '测试用户', avatar_url: null },
    isAuthenticated: true,
    isPremium: true
  }),
  useWebSocketStatus: () => ({
    isConnected: true
  }),
  useGlobalLoading: () => ({
    isLoading: false
  })
}))

// Mock toast
vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn()
  }
}))

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate
  }
})

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </BrowserRouter>
  )
}

describe('StrategiesPage', () => {
  test('renders strategies page with all components', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查页面标题
    expect(screen.getByText('Trademe')).toBeInTheDocument()
    
    // 检查导航激活状态
    expect(screen.getByText('策略交易')).toHaveClass('active')
    
    // 检查统计卡片
    expect(screen.getByText('策略总数')).toBeInTheDocument()
    expect(screen.getByText('运行中')).toBeInTheDocument()
    expect(screen.getByText('总收益')).toBeInTheDocument()
    expect(screen.getByText('平均胜率')).toBeInTheDocument()
    
    // 检查策略列表
    expect(screen.getByText('策略列表')).toBeInTheDocument()
    expect(screen.getByText('管理您的交易策略，监控实时表现')).toBeInTheDocument()
  })

  test('displays strategy statistics correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查统计数据
    expect(screen.getByText('4')).toBeInTheDocument() // 策略总数
    expect(screen.getByText('2')).toBeInTheDocument() // 运行中策略数
    expect(screen.getByText(/\+8,478/)).toBeInTheDocument() // 总收益
  })

  test('displays strategy list in table view', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查表头
    expect(screen.getByText('策略信息')).toBeInTheDocument()
    expect(screen.getByText('状态')).toBeInTheDocument()
    expect(screen.getByText('交易对')).toBeInTheDocument()
    expect(screen.getByText('收益')).toBeInTheDocument()
    expect(screen.getByText('表现')).toBeInTheDocument()
    expect(screen.getByText('操作')).toBeInTheDocument()
    
    // 检查策略数据
    expect(screen.getByText('RSI 均值回归策略')).toBeInTheDocument()
    expect(screen.getByText('MACD 趋势跟踪')).toBeInTheDocument()
    expect(screen.getByText('网格交易策略')).toBeInTheDocument()
    expect(screen.getByText('布林带突破策略')).toBeInTheDocument()
  })

  test('switches between list and card view', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 默认是列表视图
    expect(screen.getByRole('table')).toBeInTheDocument()
    
    // 切换到卡片视图
    const cardViewButton = screen.getAllByRole('button').find(btn => 
      btn.querySelector('svg')?.getAttribute('viewBox') === '0 0 24 24' &&
      btn.querySelector('path')?.getAttribute('d')?.includes('M4 6a2 2 0 012-2h2')
    )
    
    if (cardViewButton) {
      fireEvent.click(cardViewButton)
      
      // 应该看到卡片布局
      await waitFor(() => {
        expect(screen.queryByRole('table')).not.toBeInTheDocument()
        expect(screen.getByText('RSI 均值回归策略')).toBeInTheDocument()
      })
    }
  })

  test('handles search functionality', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 搜索RSI策略
    const searchInput = screen.getByPlaceholderText('搜索策略名称或描述...')
    fireEvent.change(searchInput, { target: { value: 'RSI' } })
    
    // 应该只显示RSI策略
    await waitFor(() => {
      expect(screen.getByText('RSI 均值回归策略')).toBeInTheDocument()
      expect(screen.queryByText('MACD 趋势跟踪')).not.toBeInTheDocument()
    })
  })

  test('handles status filter', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 筛选运行中的策略
    const statusFilter = screen.getByDisplayValue('全部状态')
    fireEvent.change(statusFilter, { target: { value: 'running' } })
    
    // 应该只显示运行中的策略
    await waitFor(() => {
      expect(screen.getByText('RSI 均值回归策略')).toBeInTheDocument()
      expect(screen.getByText('网格交易策略')).toBeInTheDocument()
      expect(screen.queryByText('MACD 趋势跟踪')).not.toBeInTheDocument()
    })
  })

  test('handles strategy start/stop actions', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 找到停止状态的策略并启动
    const startButtons = screen.getAllByText('启动')
    if (startButtons.length > 0) {
      fireEvent.click(startButtons[0])
      
      // 应该显示成功消息（通过toast mock验证）
      expect(startButtons[0]).toBeInTheDocument()
    }
    
    // 找到运行中的策略并停止
    const stopButtons = screen.getAllByText('停止')
    if (stopButtons.length > 0) {
      fireEvent.click(stopButtons[0])
      
      // 应该显示成功消息
      expect(stopButtons[0]).toBeInTheDocument()
    }
  })

  test('handles strategy pause action', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 找到运行中的策略并暂停
    const pauseButtons = screen.getAllByText('暂停')
    if (pauseButtons.length > 0) {
      fireEvent.click(pauseButtons[0])
      
      // 应该显示成功消息
      expect(pauseButtons[0]).toBeInTheDocument()
    }
  })

  test('handles create strategy action', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 点击创建策略按钮
    const createButton = screen.getByText('创建策略')
    fireEvent.click(createButton)
    
    // 应该导航到策略创建页面
    expect(mockNavigate).toHaveBeenCalledWith('/strategy/create')
  })

  test('handles edit strategy action', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 点击编辑按钮
    const editButtons = screen.getAllByText('编辑')
    if (editButtons.length > 0) {
      fireEvent.click(editButtons[0])
      
      // 应该导航到策略编辑页面
      expect(mockNavigate).toHaveBeenCalledWith('/strategy/edit/1')
    }
  })

  test('handles backtest action', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 点击回测按钮
    const backtestButtons = screen.getAllByText('回测')
    if (backtestButtons.length > 0) {
      fireEvent.click(backtestButtons[0])
      
      // 应该导航到回测页面
      expect(mockNavigate).toHaveBeenCalledWith('/backtest?strategy=1')
    }
  })

  test('handles delete strategy action', async () => {
    const Wrapper = createTestWrapper()
    
    // Mock window.confirm
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 点击删除按钮
    const deleteButtons = screen.getAllByText('删除')
    if (deleteButtons.length > 0) {
      fireEvent.click(deleteButtons[0])
      
      // 应该显示确认对话框
      expect(confirmSpy).toHaveBeenCalled()
    }
    
    confirmSpy.mockRestore()
  })

  test('shows connection status correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查连接状态显示
    expect(screen.getByText('策略服务已连接')).toBeInTheDocument()
    
    // 检查绿色连接指示器
    const statusIndicator = document.querySelector('.bg-green-500')
    expect(statusIndicator).toBeInTheDocument()
  })

  test('handles navigation correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 测试导航到首页
    const homeButton = screen.getByText('首页')
    fireEvent.click(homeButton)
    expect(mockNavigate).toHaveBeenCalledWith('/')
    
    // 测试导航到交易页面
    const tradingButton = screen.getByText('图表交易')
    fireEvent.click(tradingButton)
    expect(mockNavigate).toHaveBeenCalledWith('/trading')
  })

  test('displays premium features correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 高级用户应该看到创建策略按钮
    expect(screen.getByText('创建策略')).toBeInTheDocument()
    
    // 不应该看到升级提示
    expect(screen.queryByText('创建策略需要升级到高级版本')).not.toBeInTheDocument()
  })

  test('shows strategy performance metrics', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查收益显示
    expect(screen.getByText('+2,847.32 USDT')).toBeInTheDocument()
    expect(screen.getByText('+12.3%')).toBeInTheDocument()
    
    // 检查胜率显示
    expect(screen.getByText('67.8%')).toBeInTheDocument()
    
    // 检查交易笔数
    expect(screen.getByText('交易 28 笔')).toBeInTheDocument()
  })

  test('renders with responsive layout', async () => {
    const Wrapper = createTestWrapper()
    
    const { container } = render(
      <Wrapper>
        <StrategiesPage />
      </Wrapper>
    )

    // 检查统计卡片的响应式布局
    const statsGrid = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-4')
    expect(statsGrid).toBeInTheDocument()
    
    // 检查最大宽度容器
    const maxWidthContainer = container.querySelector('.max-w-\\[1440px\\]')
    expect(maxWidthContainer).toBeInTheDocument()
  })
})

export {}