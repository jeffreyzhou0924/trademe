import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import BacktestPage from '../BacktestPage'
import * as backtestStore from '../../store/backtestStore'
import * as authStore from '../../store/authStore'

// Mock the store modules
vi.mock('../../store/backtestStore')
vi.mock('../../store/authStore')
vi.mock('../../components/charts', () => ({
  BacktestResultChart: ({ metrics }: any) => (
    <div data-testid="backtest-result-chart">
      <div>Total Return: {metrics.total_return}%</div>
      <div>Max Drawdown: {metrics.max_drawdown}%</div>
      <div>Sharpe Ratio: {metrics.sharpe_ratio}</div>
      <div>Win Rate: {metrics.win_rate}%</div>
    </div>
  )
}))
vi.mock('../../components/common', () => ({
  LoadingSpinner: ({ className }: any) => <div data-testid="loading-spinner" className={className} />,
  Button: ({ children, onClick, disabled, className }: any) => (
    <button onClick={onClick} disabled={disabled} className={className} data-testid="button">
      {children}
    </button>
  )
}))

// Mock data
const mockUser = {
  id: '1',
  username: 'testuser',
  email: 'test@example.com',
  membership_level: 'premium'
}

const mockBacktest = {
  id: 'bt-123',
  strategy_id: 'rsi_strategy',
  config: {
    strategy_id: 'rsi_strategy',
    symbol: 'BTC/USDT',
    exchange: 'binance',
    start_date: '2024-01-01',
    end_date: '2024-03-31',
    initial_capital: 10000,
    commission_rate: 0.001,
    timeframe: '1h'
  },
  status: 'completed' as const,
  results: {
    total_return: 15.5,
    max_drawdown: -5.2,
    sharpe_ratio: 1.8,
    win_rate: 65.0,
    total_trades: 45,
    profit_factor: 2.1,
    annual_return: 12.3,
    volatility: 8.7,
    final_capital: 11550,
    equity_curve: [
      { timestamp: '2024-01-01', value: 10000 },
      { timestamp: '2024-02-01', value: 10500 },
      { timestamp: '2024-03-01', value: 11200 },
      { timestamp: '2024-03-31', value: 11550 }
    ],
    trade_history: [
      {
        timestamp: '2024-01-15',
        side: 'buy' as const,
        price: 42000,
        quantity: 0.1,
        pnl: 250
      },
      {
        timestamp: '2024-01-20',
        side: 'sell' as const,
        price: 43500,
        quantity: 0.1,
        pnl: -100
      }
    ]
  },
  created_at: '2024-01-01T10:00:00Z'
}

const defaultConfigForm = {
  strategy_id: '',
  symbol: 'BTC/USDT',
  exchange: 'binance',
  start_date: '2024-01-01',
  end_date: '2024-03-31',
  initial_capital: 10000,
  commission_rate: 0.001,
  timeframe: '1h'
}

// Mock store functions
const mockFetchBacktests = vi.fn()
const mockCreateBacktest = vi.fn()
const mockUpdateBacktestForm = vi.fn()
const mockResetBacktestForm = vi.fn()
const mockDeleteBacktest = vi.fn()
const mockDownloadReport = vi.fn()
const mockToggleComparisonSelection = vi.fn()
const mockCompareBacktests = vi.fn()
const mockClearComparison = vi.fn()

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>{children}</BrowserRouter>
)

describe('BacktestPage', () => {
  beforeEach(() => {
    // Setup default mock implementations
    vi.mocked(authStore.useAuthStore).mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      register: vi.fn(),
      updateProfile: vi.fn(),
      loading: false,
      error: null
    } as any)

    vi.mocked(backtestStore.useBacktestList).mockReturnValue({
      backtests: [mockBacktest],
      loading: false,
      error: null,
      pagination: {
        page: 1,
        per_page: 10,
        total: 1,
        total_pages: 1
      },
      fetchBacktests: mockFetchBacktests,
      deleteBacktest: mockDeleteBacktest,
      downloadReport: mockDownloadReport
    })

    vi.mocked(backtestStore.useBacktestCreation).mockReturnValue({
      configForm: defaultConfigForm,
      isCreatingBacktest: false,
      createBacktest: mockCreateBacktest,
      updateBacktestForm: mockUpdateBacktestForm,
      resetBacktestForm: mockResetBacktestForm
    })

    vi.mocked(backtestStore.useBacktestComparison).mockReturnValue({
      selectedForComparison: [],
      comparisonResult: null,
      toggleComparisonSelection: mockToggleComparisonSelection,
      compareBacktests: mockCompareBacktests,
      clearComparison: mockClearComparison
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('renders the backtest page with correct title', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('Trademe')).toBeInTheDocument()
      expect(screen.getByText('创建回测')).toBeInTheDocument()
      expect(screen.getByText('回测历史')).toBeInTheDocument()
    })

    it('renders navigation links correctly', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('首页')).toBeInTheDocument()
      expect(screen.getByText('策略交易')).toBeInTheDocument()
      expect(screen.getByText('图表交易')).toBeInTheDocument()
      expect(screen.getByText('API管理')).toBeInTheDocument()
      expect(screen.getByText('交易心得')).toBeInTheDocument()
      expect(screen.getByText('账户中心')).toBeInTheDocument()
    })

    it('displays user avatar with correct initial', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('T')).toBeInTheDocument() // First letter of 'testuser'
    })
  })

  describe('Tab Navigation', () => {
    it('shows create backtest tab by default', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('回测配置')).toBeInTheDocument()
      expect(screen.getByText('回测预览')).toBeInTheDocument()
    })

    it('switches to history tab when clicked', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      const historyTab = screen.getByText('回测历史')
      fireEvent.click(historyTab)

      expect(screen.getByText('策略ID')).toBeInTheDocument()
      expect(screen.getByText('交易对')).toBeInTheDocument()
      expect(screen.getByText('总收益率')).toBeInTheDocument()
    })

    it('switches back to create tab when clicked', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      // Switch to history first
      fireEvent.click(screen.getByText('回测历史'))
      
      // Then back to create
      fireEvent.click(screen.getByText('创建回测'))

      expect(screen.getByText('回测配置')).toBeInTheDocument()
    })
  })

  describe('Backtest Creation Form', () => {
    it('renders all form fields with correct default values', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      // Check strategy dropdown
      expect(screen.getByDisplayValue('请选择策略')).toBeInTheDocument()
      
      // Check other form fields
      expect(screen.getByDisplayValue('BTC/USDT')).toBeInTheDocument()
      expect(screen.getByDisplayValue('币安 (Binance)')).toBeInTheDocument()
      expect(screen.getByDisplayValue('2024-01-01')).toBeInTheDocument()
      expect(screen.getByDisplayValue('2024-03-31')).toBeInTheDocument()
      expect(screen.getByDisplayValue('10000')).toBeInTheDocument()
      expect(screen.getByDisplayValue('1小时')).toBeInTheDocument()
    })

    it('calls updateBacktestForm when form fields change', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      const strategySelect = screen.getByDisplayValue('请选择策略')
      fireEvent.change(strategySelect, { target: { value: 'rsi_strategy' } })

      expect(mockUpdateBacktestForm).toHaveBeenCalledWith('strategy_id', 'rsi_strategy')
    })

    it('prevents backtest creation when no strategy is selected', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      const createButton = screen.getByText('开始回测')
      fireEvent.click(createButton)

      expect(mockCreateBacktest).not.toHaveBeenCalled()
    })

    it('creates backtest when form is valid', async () => {
      // Mock form with selected strategy
      vi.mocked(backtestStore.useBacktestCreation).mockReturnValue({
        configForm: { ...defaultConfigForm, strategy_id: 'rsi_strategy' },
        isCreatingBacktest: false,
        createBacktest: mockCreateBacktest,
        updateBacktestForm: mockUpdateBacktestForm,
        resetBacktestForm: mockResetBacktestForm
      })

      mockCreateBacktest.mockResolvedValue(mockBacktest)

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      const createButton = screen.getByText('开始回测')
      fireEvent.click(createButton)

      expect(mockCreateBacktest).toHaveBeenCalledWith({
        ...defaultConfigForm,
        strategy_id: 'rsi_strategy'
      })
    })

    it('shows loading state during backtest creation', () => {
      vi.mocked(backtestStore.useBacktestCreation).mockReturnValue({
        configForm: { ...defaultConfigForm, strategy_id: 'rsi_strategy' },
        isCreatingBacktest: true,
        createBacktest: mockCreateBacktest,
        updateBacktestForm: mockUpdateBacktestForm,
        resetBacktestForm: mockResetBacktestForm
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('创建中...')).toBeInTheDocument()
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    })

    it('resets form when reset button is clicked', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      const resetButton = screen.getByText('重置')
      fireEvent.click(resetButton)

      expect(mockResetBacktestForm).toHaveBeenCalled()
    })
  })

  describe('Backtest Results Preview', () => {
    it('shows empty state when no backtests exist', () => {
      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [],
        loading: false,
        error: null,
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('选择策略并开始回测')).toBeInTheDocument()
      expect(screen.getByText('回测结果将在此处显示')).toBeInTheDocument()
    })

    it('displays backtest result chart when backtests exist', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByTestId('backtest-result-chart')).toBeInTheDocument()
      expect(screen.getByText('Total Return: 15.5%')).toBeInTheDocument()
      expect(screen.getByText('Max Drawdown: -5.2%')).toBeInTheDocument()
    })

    it('shows loading state during backtest creation in preview', () => {
      vi.mocked(backtestStore.useBacktestCreation).mockReturnValue({
        configForm: defaultConfigForm,
        isCreatingBacktest: true,
        createBacktest: mockCreateBacktest,
        updateBacktestForm: mockUpdateBacktestForm,
        resetBacktestForm: mockResetBacktestForm
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('正在执行回测...')).toBeInTheDocument()
      expect(screen.getByText('预计需要 30-60 秒')).toBeInTheDocument()
    })
  })

  describe('Backtest History Management', () => {
    beforeEach(() => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )
      
      // Switch to history tab
      fireEvent.click(screen.getByText('回测历史'))
    })

    it('displays backtest history table with correct data', () => {
      expect(screen.getByText('rsi_strategy')).toBeInTheDocument()
      expect(screen.getByText('BTC/USDT')).toBeInTheDocument()
      expect(screen.getByText('binance')).toBeInTheDocument()
      expect(screen.getByText('+15.50%')).toBeInTheDocument()
      expect(screen.getByText('-5.20%')).toBeInTheDocument()
      expect(screen.getByText('1.80')).toBeInTheDocument()
      expect(screen.getByText('已完成')).toBeInTheDocument()
    })

    it('shows loading state when fetching backtests', () => {
      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [],
        loading: true,
        error: null,
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))
      
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    })

    it('shows empty state when no backtest history exists', () => {
      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [],
        loading: false,
        error: null,
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))

      expect(screen.getByText('暂无回测记录')).toBeInTheDocument()
      expect(screen.getByText('创建您的第一个回测以开始使用')).toBeInTheDocument()
    })

    it('handles backtest deletion', async () => {
      window.confirm = vi.fn(() => true)
      
      const deleteButtons = screen.getAllByText('删除')
      fireEvent.click(deleteButtons[0])

      expect(mockDeleteBacktest).toHaveBeenCalledWith('bt-123')
    })

    it('cancels deletion when user confirms no', () => {
      window.confirm = vi.fn(() => false)
      
      const deleteButtons = screen.getAllByText('删除')
      fireEvent.click(deleteButtons[0])

      expect(mockDeleteBacktest).not.toHaveBeenCalled()
    })

    it('handles report download', () => {
      const downloadButtons = screen.getAllByText('下载')
      fireEvent.click(downloadButtons[0])

      expect(mockDownloadReport).toHaveBeenCalledWith('bt-123', 'html')
    })
  })

  describe('Backtest Comparison', () => {
    beforeEach(() => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )
      
      // Switch to history tab
      fireEvent.click(screen.getByText('回测历史'))
    })

    it('enables comparison selection', () => {
      const checkboxes = screen.getAllByRole('checkbox')
      const backtestCheckbox = checkboxes.find(cb => !cb.hasAttribute('data-select-all'))
      
      if (backtestCheckbox) {
        fireEvent.click(backtestCheckbox)
        expect(mockToggleComparisonSelection).toHaveBeenCalledWith('bt-123')
      }
    })

    it('shows comparison panel when multiple backtests selected', () => {
      vi.mocked(backtestStore.useBacktestComparison).mockReturnValue({
        selectedForComparison: ['bt-123', 'bt-456'],
        comparisonResult: null,
        toggleComparisonSelection: mockToggleComparisonSelection,
        compareBacktests: mockCompareBacktests,
        clearComparison: mockClearComparison
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))

      expect(screen.getByText('已选择 2 个回测进行比较')).toBeInTheDocument()
      expect(screen.getByText('比较回测')).toBeInTheDocument()
      expect(screen.getByText('清除选择')).toBeInTheDocument()
    })

    it('handles comparison execution', () => {
      vi.mocked(backtestStore.useBacktestComparison).mockReturnValue({
        selectedForComparison: ['bt-123', 'bt-456'],
        comparisonResult: null,
        toggleComparisonSelection: mockToggleComparisonSelection,
        compareBacktests: mockCompareBacktests,
        clearComparison: mockClearComparison
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))
      fireEvent.click(screen.getByText('比较回测'))

      expect(mockCompareBacktests).toHaveBeenCalled()
    })

    it('clears comparison selection', () => {
      vi.mocked(backtestStore.useBacktestComparison).mockReturnValue({
        selectedForComparison: ['bt-123', 'bt-456'],
        comparisonResult: null,
        toggleComparisonSelection: mockToggleComparisonSelection,
        compareBacktests: mockCompareBacktests,
        clearComparison: mockClearComparison
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))
      fireEvent.click(screen.getByText('清除选择'))

      expect(mockClearComparison).toHaveBeenCalled()
    })
  })

  describe('Error Handling', () => {
    it('displays error message in create tab', () => {
      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [],
        loading: false,
        error: 'Failed to create backtest',
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(screen.getByText('Failed to create backtest')).toBeInTheDocument()
    })

    it('displays error message in history tab', () => {
      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [],
        loading: false,
        error: 'Failed to fetch backtests',
        pagination: {
          page: 1,
          per_page: 10,
          total: 0,
          total_pages: 0
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))

      expect(screen.getByText('Failed to fetch backtests')).toBeInTheDocument()
    })
  })

  describe('Data Fetching', () => {
    it('fetches backtests on component mount', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      expect(mockFetchBacktests).toHaveBeenCalled()
    })
  })

  describe('Status Display', () => {
    it('displays correct status styles and text', () => {
      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))

      const statusElement = screen.getByText('已完成')
      expect(statusElement).toHaveClass('bg-green-100', 'text-green-800')
    })

    it('displays running status correctly', () => {
      const runningBacktest = {
        ...mockBacktest,
        status: 'running' as const
      }

      vi.mocked(backtestStore.useBacktestList).mockReturnValue({
        backtests: [runningBacktest],
        loading: false,
        error: null,
        pagination: {
          page: 1,
          per_page: 10,
          total: 1,
          total_pages: 1
        },
        fetchBacktests: mockFetchBacktests,
        deleteBacktest: mockDeleteBacktest,
        downloadReport: mockDownloadReport
      })

      render(
        <TestWrapper>
          <BacktestPage />
        </TestWrapper>
      )

      fireEvent.click(screen.getByText('回测历史'))

      const statusElement = screen.getByText('运行中')
      expect(statusElement).toHaveClass('bg-yellow-100', 'text-yellow-800')
    })
  })
})