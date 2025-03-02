-- Create view for daily returns
CREATE VIEW IF NOT EXISTS daily_returns AS
SELECT 
    ticker,
    date,
    close,
    ROUND(((close - LAG(close) OVER (PARTITION BY ticker ORDER BY date)) / 
           LAG(close) OVER (PARTITION BY ticker ORDER BY date)) * 100, 2) as daily_return_percent
FROM daily_prices;

-- Create view for moving averages
CREATE VIEW IF NOT EXISTS moving_averages AS
SELECT 
    ticker,
    date,
    close,
    ROUND(AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 2) as MA20,
    ROUND(AVG(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW), 2) as MA50
FROM daily_prices;

-- Create view for volume analysis
CREATE VIEW IF NOT EXISTS volume_analysis AS
SELECT 
    ticker,
    date,
    volume,
    close,
    ROUND(AVG(volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0) as avg_20day_volume,
    ROUND(volume * close, 2) as daily_dollar_volume
FROM daily_prices;

-- Create view for price statistics
CREATE VIEW IF NOT EXISTS price_statistics AS
WITH price_stats AS (
    SELECT 
        ticker,
        MIN(low) as period_low,
        MAX(high) as period_high,
        ROUND(AVG(close), 2) as avg_close,
        ROUND(AVG(volume), 0) as avg_volume
    FROM daily_prices
    GROUP BY ticker
)
SELECT 
    p.*,
    d.date,
    d.close,
    d.volume,
    ROUND(((d.close - p.period_low) / (p.period_high - p.period_low)) * 100, 2) as price_position_percent
FROM price_stats p
JOIN daily_prices d ON p.ticker = d.ticker;

-- Create function to get stock performance over custom period
CREATE VIEW IF NOT EXISTS stock_performance AS
WITH latest_prices AS (
    SELECT 
        ticker,
        date as latest_date,
        close as latest_close,
        LAG(close, 5) OVER (PARTITION BY ticker ORDER BY date) as week_ago_close,
        LAG(close, 21) OVER (PARTITION BY ticker ORDER BY date) as month_ago_close,
        LAG(close, 252) OVER (PARTITION BY ticker ORDER BY date) as year_ago_close
    FROM daily_prices
)
SELECT 
    ticker,
    latest_date,
    latest_close,
    ROUND((latest_close - week_ago_close) / week_ago_close * 100, 2) as weekly_return,
    ROUND((latest_close - month_ago_close) / month_ago_close * 100, 2) as monthly_return,
    ROUND((latest_close - year_ago_close) / year_ago_close * 100, 2) as yearly_return
FROM latest_prices
WHERE latest_date = (SELECT MAX(date) FROM daily_prices);

-- Example queries using the views:

-- 1. Get latest stock performance
SELECT * FROM stock_performance;

-- 2. Get stocks with highest daily returns
SELECT * FROM daily_returns 
WHERE date = (SELECT MAX(date) FROM daily_returns)
ORDER BY daily_return_percent DESC;

-- 3. Get stocks trading above their 20-day moving average
SELECT 
    m.ticker,
    m.date,
    m.close,
    m.MA20,
    ROUND((m.close - m.MA20) / m.MA20 * 100, 2) as percent_above_ma20
FROM moving_averages m
WHERE date = (SELECT MAX(date) FROM moving_averages)
    AND close > MA20
ORDER BY percent_above_ma20 DESC;

-- 4. Get stocks with unusually high volume
SELECT 
    v.ticker,
    v.date,
    v.volume,
    v.avg_20day_volume,
    ROUND(CAST(v.volume as FLOAT) / v.avg_20day_volume * 100 - 100, 2) as volume_increase_percent
FROM volume_analysis v
WHERE date = (SELECT MAX(date) FROM volume_analysis)
    AND volume > avg_20day_volume
ORDER BY volume_increase_percent DESC;

-- 5. Get current price position relative to 52-week range
SELECT 
    ticker,
    date,
    close,
    period_low as "52_week_low",
    period_high as "52_week_high",
    price_position_percent
FROM price_statistics
WHERE date = (SELECT MAX(date) FROM price_statistics)
ORDER BY price_position_percent DESC;
