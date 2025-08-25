export interface MarketData {
  id: string
  exchange: string
  symbol: string
  timeframe: string
  open_price: number
  high_price: number
  low_price: number
  close_price: number
  volume: number
  timestamp: string
  created_at: string
}

export interface KlineData {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TickerData {
  symbol: string
  price: number
  change: number
  change_percent: number
  high_24h: number
  low_24h: number
  volume_24h: number
  timestamp: number
}

export interface OrderBookEntry {
  price: number
  quantity: number
}

export interface OrderBook {
  symbol: string
  bids: OrderBookEntry[]
  asks: OrderBookEntry[]
  timestamp: number
}

export interface TradingPair {
  symbol: string
  base_asset: string
  quote_asset: string
  min_quantity: number
  max_quantity: number
  step_size: number
  min_price: number
  max_price: number
  tick_size: number
}

export interface Exchange {
  id: string
  name: string
  display_name: string
  is_active: boolean
  supported_pairs: TradingPair[]
}