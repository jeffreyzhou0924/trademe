import { describe, test, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DashboardPage from '../DashboardPage'

// Mock stores
vi.mock('@/store', () => ({
  useUserInfo: () => ({
    user: { username: '测试用户' },
    isAuthenticated: true,
    isPremium: false
  }),
  useWebSocketStatus: () => ({
    isConnected: true
  }),
  useGlobalLoading: () => ({
    isLoading: false
  }),
  useStrategyStore: () => [],
  useAuthStore: () => ({})
}))

// Mock dashboard API
vi.mock('@/services/api/dashboard', () => ({
  dashboardApi: {
    getStats: vi.fn().mockResolvedValue({
      apiKeys: 6,
      activeStrategies: 4,
      monthlyReturn: 12.3,
      totalValue: 56970,
      dailyPnl: 1240
    }),
    getRecentActivity: vi.fn().mockResolvedValue([]),
  }
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

describe('DashboardPage', () => {
  test('renders dashboard page correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    // 检查欢迎信息
    expect(screen.getByText(/欢迎回来，测试用户/)).toBeInTheDocument()
    
    // 检查统计卡片
    await waitFor(() => {
      expect(screen.getByText('APIKEY数量')).toBeInTheDocument()
      expect(screen.getByText('实盘策略数')).toBeInTheDocument()
      expect(screen.getByText('本月收益率')).toBeInTheDocument()
    })

    // 检查快捷入口
    expect(screen.getByText('快捷入口')).toBeInTheDocument()
    expect(screen.getByText('图表交易')).toBeInTheDocument()
    expect(screen.getByText('策略回测')).toBeInTheDocument()
    expect(screen.getByText('策略库')).toBeInTheDocument()
    expect(screen.getByText('API管理')).toBeInTheDocument()

    // 检查收益曲线图
    expect(screen.getByText('当前收益率曲线')).toBeInTheDocument()
    expect(screen.getByText('近7天')).toBeInTheDocument()
    expect(screen.getByText('本月')).toBeInTheDocument()
    expect(screen.getByText('近3月')).toBeInTheDocument()

    // 检查最近活动
    expect(screen.getByText('最近活动')).toBeInTheDocument()
  })

  test('handles quick action clicks', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    // 测试图表交易按钮
    const chartButton = screen.getByText('图表交易')
    fireEvent.click(chartButton)
    expect(mockNavigate).toHaveBeenCalledWith('/trading-chart')

    // 测试策略回测按钮
    const backtestButton = screen.getByText('策略回测')
    fireEvent.click(backtestButton)
    expect(mockNavigate).toHaveBeenCalledWith('/strategy/backtest')

    // 测试策略库按钮
    const libraryButton = screen.getByText('策略库')
    fireEvent.click(libraryButton)
    expect(mockNavigate).toHaveBeenCalledWith('/strategy/library')

    // 测试API管理按钮
    const apiButton = screen.getByText('API管理')
    fireEvent.click(apiButton)
    expect(mockNavigate).toHaveBeenCalledWith('/api-keys')
  })

  test('switches time range in earnings chart', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    // 测试切换时间范围
    const sevenDayButton = screen.getByText('近7天')
    const oneMonthButton = screen.getByText('本月')
    const threeMonthButton = screen.getByText('近3月')

    // 默认选中近3月
    expect(threeMonthButton).toHaveClass('bg-blue-100', 'text-blue-700')

    // 切换到近7天
    fireEvent.click(sevenDayButton)
    expect(sevenDayButton).toHaveClass('bg-blue-100', 'text-blue-700')

    // 切换到本月
    fireEvent.click(oneMonthButton)
    expect(oneMonthButton).toHaveClass('bg-blue-100', 'text-blue-700')
  })

  test('displays connection status correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    // 检查连接状态指示器
    expect(screen.getByText('实时数据已连接')).toBeInTheDocument()
    
    // 应该有绿色的连接指示器
    const statusIndicator = screen.getByText('实时数据已连接').previousElementSibling
    expect(statusIndicator).toHaveClass('bg-green-500')
  })

  test('shows mock activity data when no API data available', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    await waitFor(() => {
      // 检查模拟活动数据
      expect(screen.getByText('EMA交叉策略执行了一笔交易')).toBeInTheDocument()
      expect(screen.getByText('RSI策略完成回测分析')).toBeInTheDocument()
      expect(screen.getByText('AI助手生成新策略建议')).toBeInTheDocument()
    })
  })

  test('renders responsive layout classes', async () => {
    const Wrapper = createTestWrapper()
    
    const { container } = render(
      <Wrapper>
        <DashboardPage />
      </Wrapper>
    )

    // 检查响应式网格类
    const statsGrid = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-3')
    expect(statsGrid).toBeInTheDocument()

    const mainGrid = container.querySelector('.grid.grid-cols-1.lg\\:grid-cols-3')
    expect(mainGrid).toBeInTheDocument()

    // 检查快捷入口网格
    const quickActionGrid = container.querySelector('.grid.grid-cols-2')
    expect(quickActionGrid).toBeInTheDocument()
  })
})

export {}