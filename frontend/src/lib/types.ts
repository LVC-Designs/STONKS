export interface ScreenerRow {
  symbol: string;
  name: string | null;
  exchange: string | null;
  exchange_group: string | null;
  last_price: number | null;
  change_pct: number | null;
  volume: number | null;
  avg_volume_20d: number | null;
  score: number | null;
  regime: string | null;
  signal_date: string | null;
  trend_score: number | null;
  momentum_score: number | null;
  volume_score: number | null;
  volatility_score: number | null;
  structure_score: number | null;
}

export interface ScreenerResponse {
  items: ScreenerRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
}

export interface IndicatorSet {
  trade_date: string;
  sma_50: number | null;
  sma_100: number | null;
  sma_200: number | null;
  ema_9: number | null;
  ema_20: number | null;
  ema_50: number | null;
  macd_line: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  rsi_14: number | null;
  stoch_k: number | null;
  stoch_d: number | null;
  roc_12: number | null;
  cci_20: number | null;
  adx_14: number | null;
  plus_di: number | null;
  minus_di: number | null;
  obv: number | null;
  volume_sma_20: number | null;
  volume_ratio: number | null;
  obv_slope: number | null;
  bb_upper: number | null;
  bb_middle: number | null;
  bb_lower: number | null;
  bb_width: number | null;
  bb_pctb: number | null;
  atr_14: number | null;
  atr_percentile: number | null;
  ichi_tenkan: number | null;
  ichi_kijun: number | null;
  ichi_senkou_a: number | null;
  ichi_senkou_b: number | null;
  ichi_chikou: number | null;
  fib_swing_high: number | null;
  fib_swing_low: number | null;
  fib_236: number | null;
  fib_382: number | null;
  fib_500: number | null;
  fib_618: number | null;
  fib_786: number | null;
}

export interface ReasonItem {
  component: string;
  reason: string;
  weight: number;
}

export interface InvalidationLevel {
  price: number;
  reason: string;
}

export interface SignalDetail {
  signal_date: string;
  score: number;
  regime: string | null;
  trend_score: number | null;
  momentum_score: number | null;
  volume_score: number | null;
  volatility_score: number | null;
  structure_score: number | null;
  reasons: ReasonItem[];
  invalidation: {
    levels: InvalidationLevel[];
    stop_atr_multiple: number;
  } | null;
  target_pct: number;
  target_days: number;
  max_drawdown_pct: number;
  outcome: string | null;
  actual_return: number | null;
  days_to_target: number | null;
}

export interface NewsItem {
  id: number;
  headline: string;
  summary: string | null;
  url: string | null;
  image_url: string | null;
  source: string | null;
  published_at: string;
  category: string | null;
  sentiment_score: number | null;
  sentiment_label: string | null;
}

export interface TickerDetail {
  ticker: {
    id: number;
    symbol: string;
    name: string;
    exchange: string;
    exchange_group: string;
    country: string;
    currency: string;
    active: boolean;
    description: string | null;
    sic_code: string | null;
    sic_description: string | null;
  };
  latest_signal: SignalDetail | null;
  latest_indicators: IndicatorSet | null;
}

export interface Setting {
  key: string;
  value: unknown;
  description: string | null;
  updated_at: string | null;
}

export interface JobRun {
  id: number;
  job_name: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  tickers_processed: number;
  errors: unknown;
  summary: unknown;
}

// Backtest types

export interface BacktestWeights {
  trend: number;
  momentum: number;
  volume: number;
  volatility: number;
  structure: number;
}

export interface BacktestPortfolioConfig {
  starting_capital: number;
  max_positions: number;
  position_size_pct: number;
  use_equal_weight: boolean;
}

export interface BacktestWalkForwardConfig {
  train_pct: number;
  validation_pct: number;
  oos_pct: number;
}

export interface BacktestConfig {
  name?: string;
  date_from: string;
  date_to: string;
  min_score: number;
  target_pct: number;
  target_days: number;
  max_drawdown_pct: number;
  weights?: BacktestWeights;
  portfolio: BacktestPortfolioConfig;
  tickers?: string[];
  exchange_groups: string[];
  walk_forward?: BacktestWalkForwardConfig;
}

export interface BacktestMetrics {
  total_trades: number;
  wins: number;
  losses: number;
  timeouts: number;
  win_rate: number;
  avg_return: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  expectancy: number;
  avg_days_held: number;
  total_return: number;
  p_value: number | null;
  portfolio?: {
    starting_capital: number;
    final_equity: number;
    total_return: number;
    cagr: number;
    sharpe_ratio: number;
    max_drawdown: number;
    trading_days: number;
  };
  walk_forward?: {
    train: BacktestMetrics;
    validation: BacktestMetrics;
    oos: BacktestMetrics;
  };
  oos_win_rate?: number;
  oos_sharpe?: number;
}

export interface BacktestDiagnostics {
  tickers_in_universe: number;
  bars_available: {
    min_date: string | null;
    max_date: string | null;
    total_rows: number;
  };
  signals_computed: number;
  signals_meeting_threshold: number;
  max_signal_score_in_range: number | null;
  min_signal_score_in_range: number | null;
  reasons: string[];
}

export interface BacktestRun {
  id: number;
  name: string | null;
  status: string;
  date_from: string;
  date_to: string;
  config: BacktestConfig;
  results: BacktestMetrics | null;
  diagnostics: BacktestDiagnostics | null;
  signal_count: number;
  created_at: string | null;
  finished_at: string | null;
}

export interface BacktestRunListResponse {
  items: BacktestRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface BacktestDetail extends BacktestRun {
  portfolio_simulation: {
    config: BacktestPortfolioConfig;
    equity_curve: EquityCurvePoint[];
    metrics: Record<string, number>;
  } | null;
}

export interface BacktestSignal {
  id: number;
  ticker_symbol: string;
  ticker_name: string;
  signal_date: string;
  score: number | null;
  entry_price: number | null;
  target_price: number | null;
  stop_price: number | null;
  outcome: string | null;
  actual_return: number | null;
  days_held: number | null;
  max_drawdown: number | null;
}

export interface BacktestSignalListResponse {
  items: BacktestSignal[];
  total: number;
  page: number;
  page_size: number;
}

export interface EquityCurvePoint {
  date: string;
  equity: number;
  positions: number;
}

export interface CompareRunSummary {
  id: number;
  name: string | null;
  config: BacktestConfig;
  results: BacktestMetrics | null;
}

export interface SweepConfig {
  date_from: string;
  date_to: string;
  exchange_groups: string[];
  min_scores: number[];
  target_pcts: number[];
  target_days_list: number[];
  max_drawdown_pcts: number[];
  portfolio: BacktestPortfolioConfig;
  walk_forward?: BacktestWalkForwardConfig;
}

export interface SweepResponse {
  run_ids: number[];
  total_combinations: number;
}

// ---------------------------------------------------------------------------
// Quant Backtest types
// ---------------------------------------------------------------------------

export interface QuantSplitDates {
  date_from_train: string;
  date_to_train: string;
  date_from_val: string;
  date_to_val: string;
  date_from_oos: string;
  date_to_oos: string;
}

export interface WalkForwardParams {
  window_train_months: number;
  window_val_months: number;
  window_oos_months: number;
  step_months: number;
}

export interface QuantSweepConfig {
  name?: string;
  mode: "split" | "walk_forward";
  splits?: QuantSplitDates;
  date_from?: string;
  date_to?: string;
  walk_forward?: WalkForwardParams;
  min_scores: number[];
  target_pcts: number[];
  target_days_list: number[];
  max_drawdown_pcts: number[];
  portfolio: {
    starting_capital: number;
    max_positions: number;
    position_size_pct: number;
  };
  exchange_groups: string[];
  tickers?: string[];
  top_k: number;
  objective: string;
}

export interface QuantMetrics {
  trades: number;
  wins: number;
  losses: number;
  timeouts: number;
  win_rate: number;
  avg_return: number;
  avg_win: number;
  avg_loss: number;
  expectancy: number;
  profit_factor: number | null;
  total_return: number;
  max_drawdown: number;
  calmar_ratio: number | null;
  sharpe: number;
  sortino: number | null;
  volatility: number;
  exposure_pct: number;
  avg_hold_days: number;
  best_trade: number | null;
  worst_trade: number | null;
  p_value: number | null;
  final_equity: number | null;
  cagr: number | null;
}

export interface QuantCandidate {
  id: number;
  config: Record<string, number>;
  rank: number | null;
  train_metrics: QuantMetrics | null;
  train_objective: number | null;
  val_metrics: QuantMetrics | null;
  val_objective: number | null;
  oos_metrics: QuantMetrics | null;
  stability_score: number | null;
  is_selected: boolean;
  fold_metrics: Array<{
    fold: number;
    dates: { train: string; val: string; oos: string };
    train: QuantMetrics | null;
    val: QuantMetrics | null;
    oos?: QuantMetrics | null;
  }> | null;
  equity_curve: EquityCurvePoint[] | null;
  warnings: string[] | null;
  diagnostics: Record<string, unknown> | null;
}

export interface QuantBacktest {
  id: number;
  name: string | null;
  mode: string;
  status: string;
  config: Record<string, unknown>;
  selected_config: Record<string, number> | null;
  objective: string | null;
  stability_score: number | null;
  results: {
    train: QuantMetrics;
    val: QuantMetrics;
    oos: QuantMetrics;
    folds: number;
    candidates_tested: number;
    top_k_evaluated: number;
    insights?: {
      summary: string;
      takeaways: string[];
      next_steps: string[];
    };
  } | null;
  diagnostics: Record<string, unknown> | null;
  warnings: string[] | null;
  candidates_count: number;
  progress: string | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface QuantBacktestListResponse {
  items: QuantBacktest[];
  total: number;
  page: number;
  page_size: number;
}

export interface QuantBacktestDetail extends QuantBacktest {
  candidates: QuantCandidate[];
}

// ---------------------------------------------------------------------------
// News types
// ---------------------------------------------------------------------------

export interface MarketNewsItem {
  id: number;
  ticker_symbol: string;
  ticker_name: string;
  headline: string;
  summary: string | null;
  url: string | null;
  image_url: string | null;
  source: string | null;
  published_at: string | null;
  category: string | null;
  sentiment_score: number | null;
  sentiment_label: string | null;
}

export interface SentimentSummary {
  avg_score: number | null;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
}

export interface MarketNewsResponse {
  items: MarketNewsItem[];
  total: number;
  page: number;
  page_size: number;
  sentiment_summary: SentimentSummary;
}

// News V2 types

export interface TickerContext {
  ticker: string;
  bar_date: string | null;
  close_at_publish: number | null;
  ret_1d: number | null;
  ret_5d: number | null;
  ret_20d: number | null;
}

export interface NewsArticle {
  id: number;
  provider: string;
  url: string;
  source: string | null;
  headline: string;
  summary: string | null;
  image_url: string | null;
  published_at: string;
  fetched_at: string | null;
  tickers: string[];
  sentiment_label: string | null;
  sentiment_score: number | null;
  sentiment_model: string | null;
  ticker_context: TickerContext[];
}

export interface NewsListResponse {
  items: NewsArticle[];
  total: number;
  page: number;
  page_size: number;
  sentiment_summary: SentimentSummary;
}

export interface NewsRefreshRequest {
  mode: "quick" | "full";
  limit_tickers?: number;
  max_articles_per_ticker?: number;
  lookback_days?: number;
}

export interface NewsRefreshResponse {
  status: string;
  mode: string;
  tickers_queued: number;
  tickers_processed: number;
  articles_stored: number;
  errors: string[];
}

export interface NewsStatsResponse {
  total_articles: number;
  avg_sentiment: number | null;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  articles_without_sentiment: number;
  tickers_with_news: number;
  oldest_article: string | null;
  newest_article: string | null;
}

// ---------------------------------------------------------------------------
// ML types
// ---------------------------------------------------------------------------

export interface MLModel {
  id: number;
  model_type: string;
  version: number;
  name: string | null;
  status: string;
  is_active: boolean;
  architecture: Record<string, unknown> | null;
  hyperparameters: Record<string, unknown> | null;
  train_samples: number | null;
  val_samples: number | null;
  test_samples: number | null;
  train_date_from: string | null;
  train_date_to: string | null;
  train_metrics: Record<string, unknown> | null;
  val_metrics: Record<string, unknown> | null;
  test_metrics: Record<string, unknown> | null;
  training_time_seconds: number | null;
  inference_time_ms: number | null;
  file_size_mb: number | null;
  created_at: string | null;
}

export interface MLTrainingRun {
  id: number;
  ml_model_id: number;
  status: string;
  progress: string | null;
  current_epoch: number | null;
  total_epochs: number | null;
  epoch_history: Array<Record<string, number>> | null;
  best_epoch: number | null;
  best_val_loss: number | null;
  best_val_metric: number | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface MLConfig {
  scoring_mode: string;
  nn_weight: number;
  active_models: Record<string, { id: number; version: number }>;
}

export interface MLDashboard {
  models: MLModel[];
  active_models: Record<string, { id: number; version: number }>;
  recent_training_runs: MLTrainingRun[];
  scoring_mode: string;
  nn_weight: number;
  total_models: number;
}

export interface TrainRequest {
  model_type: string;
  name?: string;
  date_from?: string;
  date_to?: string;
  epochs?: number;
  batch_size?: number;
  lr?: number;
  hidden_dim?: number;
  dropout?: number;
}
