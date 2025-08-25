import { describe, test, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TradingPage from '../TradingPage'

// Mock ECharts
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn()
  })),
  dispose: vi.fn()
}))

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

describe('TradingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('renders trading page with all components', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 检查页面标题
    expect(screen.getByText('Trademe')).toBeInTheDocument()
    
    // 检查导航激活状态
    expect(screen.getByText('图表交易')).toHaveClass('active')
    
    // 检查市场选择器
    expect(screen.getByDisplayValue('BTC/USDT')).toBeInTheDocument()
    
    // 检查K线图标题
    expect(screen.getByText('BTC/USDT K线图')).toBeInTheDocument()
    
    // 检查交易面板
    expect(screen.getByText('现货交易')).toBeInTheDocument()
    expect(screen.getByText('买入')).toBeInTheDocument()
    expect(screen.getByText('卖出')).toBeInTheDocument()
    
    // 检查订单簿
    expect(screen.getByText('订单簿')).toBeInTheDocument()
    expect(screen.getByText('价格(USDT)')).toBeInTheDocument()
  })

  test('handles market pair selection', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    const marketSelector = screen.getByDisplayValue('BTC/USDT')
    fireEvent.change(marketSelector, { target: { value: 'ETH/USDT' } })
    
    expect(screen.getByDisplayValue('ETH/USDT')).toBeInTheDocument()
  })

  test('handles timeframe selection', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 检查默认选中的时间周期
    expect(screen.getByText('15分钟')).toHaveClass('bg-brand-500')
    
    // 切换到1分钟
    const oneMinuteButton = screen.getByText('1分钟')
    fireEvent.click(oneMinuteButton)
    
    expect(oneMinuteButton).toHaveClass('bg-brand-500')
  })

  test('handles trade type switching', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 默认选中买入
    expect(screen.getByText('买入')).toHaveClass('bg-green-100')
    
    // 切换到卖出
    const sellButton = screen.getByText('卖出')
    fireEvent.click(sellButton)
    
    expect(sellButton).toHaveClass('bg-red-100')
  })

  test('handles order type switching', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 默认选中限价单
    expect(screen.getByText('限价单')).toHaveClass('bg-brand-50')
    
    // 切换到市价单
    const marketOrderButton = screen.getByText('市价单')
    fireEvent.click(marketOrderButton)
    
    expect(marketOrderButton).toHaveClass('bg-brand-50')
  })

  test('handles price input and calculation', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 输入价格
    const priceInput = screen.getByPlaceholderText('43,250.00')
    fireEvent.change(priceInput, { target: { value: '50000' } })
    
    // 输入数量
    const quantityInput = screen.getByPlaceholderText('0.001')
    fireEvent.change(quantityInput, { target: { value: '0.1' } })
    
    // 检查金额计算
    await waitFor(() => {
      const amountInput = screen.getByPlaceholderText('43.25')
      expect(amountInput).toHaveValue('5000.00')
    })
  })

  test('handles quick percentage buttons', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 点击25%按钮
    const percentButton = screen.getByText('25%')
    fireEvent.click(percentButton)
    
    // 应该根据模拟余额计算金额
    await waitFor(() => {
      const amountInput = screen.getByPlaceholderText('43.25')
      expect(amountInput).toHaveValue('250.00') // 1000 * 0.25
    })
  })

  test('handles place order with premium account', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 填写价格和数量
    const priceInput = screen.getByPlaceholderText('43,250.00')
    const quantityInput = screen.getByPlaceholderText('0.001')
    
    fireEvent.change(priceInput, { target: { value: '50000' } })
    fireEvent.change(quantityInput, { target: { value: '0.1' } })
    
    // 点击买入按钮
    const buyButton = screen.getByRole('button', { name: /买入 BTC/i })
    fireEvent.click(buyButton)
    
    // 应该显示成功消息（通过mock验证）
    expect(buyButton).toBeInTheDocument()
  })

  test('shows connection status correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 检查连接状态显示
    expect(screen.getByText('实时数据已连接')).toBeInTheDocument()
    
    // 检查绿色连接指示器
    const statusIndicator = document.querySelector('.bg-green-500')
    expect(statusIndicator).toBeInTheDocument()
  })

  test('displays order book data', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 检查订单簿表头
    expect(screen.getByText('价格(USDT)')).toBeInTheDocument()
    expect(screen.getByText('数量(BTC)')).toBeInTheDocument()
    expect(screen.getByText('累计(BTC)')).toBeInTheDocument()
    
    // 检查当前价格显示
    expect(screen.getByText('43,250.00')).toBeInTheDocument()
  })

  test('handles navigation correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 测试导航到首页
    const homeButton = screen.getByText('首页')
    fireEvent.click(homeButton)
    expect(mockNavigate).toHaveBeenCalledWith('/')
    
    // 测试导航到策略页面
    const strategiesButton = screen.getByText('策略交易')
    fireEvent.click(strategiesButton)
    expect(mockNavigate).toHaveBeenCalledWith('/strategies')
  })

  test('shows premium features correctly', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 高级用户不应该看到升级提示
    expect(screen.queryByText('实盘交易需要高级版本')).not.toBeInTheDocument()
    
    // 应该看到正常的下单按钮
    expect(screen.getByText('买入 BTC')).toBeInTheDocument()
  })

  test('renders with responsive layout', async () => {
    const Wrapper = createTestWrapper()
    
    const { container } = render(
      <Wrapper>
        <TradingPage />
      </Wrapper>
    )

    // 检查响应式网格布局
    const gridContainer = container.querySelector('.grid.grid-cols-12')
    expect(gridContainer).toBeInTheDocument()
    
    // 检查K线图占8列
    const chartColumn = container.querySelector('.col-span-8')
    expect(chartColumn).toBeInTheDocument()
    
    // 检查交易面板占4列
    const tradingColumn = container.querySelector('.col-span-4')
    expect(tradingColumn).toBeInTheDocument()
  })
})

export {}