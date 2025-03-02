-- Create stocks table
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create daily_prices table
CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT REFERENCES stocks(ticker),
    date DATE,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker ON daily_prices(ticker);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices(ticker, date);

-- Create view for daily returns
CREATE OR REPLACE VIEW daily_returns AS
SELECT 
    ticker,
    date,
    close,
    ROUND(((close - LAG(close) OVER (PARTITION BY ticker ORDER BY date)) / 
           LAG(close) OVER (PARTITION BY ticker ORDER BY date)) * 100, 2) as daily_return_percent
FROM daily_prices;

-- Create view for moving averages
CREATE OR REPLACE VIEW moving_averages AS
SELECT 
    ticker,
    date,
    close,
    AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as MA20,
    AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as MA50
FROM daily_prices;

-- Create view for volume analysis
CREATE OR REPLACE VIEW volume_analysis AS
SELECT 
    ticker,
    date,
    volume,
    AVG(volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as avg_20day_volume
FROM daily_prices;
