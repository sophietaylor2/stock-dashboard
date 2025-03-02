-- Enable RLS
ALTER TABLE IF EXISTS public.stocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.daily_prices ENABLE ROW LEVEL SECURITY;

-- Drop existing tables and views if they exist
DROP VIEW IF EXISTS public.volume_analysis;
DROP VIEW IF EXISTS public.moving_averages;
DROP VIEW IF EXISTS public.daily_returns;
DROP TABLE IF EXISTS public.daily_prices;
DROP TABLE IF EXISTS public.stocks;

-- Create stocks table
CREATE TABLE public.stocks (
    ticker TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create daily_prices table
CREATE TABLE public.daily_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT REFERENCES public.stocks(ticker),
    date DATE,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date)
);

-- Create indexes
CREATE INDEX idx_daily_prices_ticker ON public.daily_prices(ticker);
CREATE INDEX idx_daily_prices_date ON public.daily_prices(date);
CREATE INDEX idx_daily_prices_ticker_date ON public.daily_prices(ticker, date);

-- Create views
CREATE OR REPLACE VIEW public.daily_returns AS
SELECT 
    dp.ticker,
    dp.date,
    dp.close,
    ROUND(((dp.close - LAG(dp.close) OVER (PARTITION BY dp.ticker ORDER BY dp.date)) / 
           LAG(dp.close) OVER (PARTITION BY dp.ticker ORDER BY dp.date)) * 100, 2) as daily_return_percent
FROM public.daily_prices dp;

CREATE OR REPLACE VIEW public.moving_averages AS
SELECT 
    dp.ticker,
    dp.date,
    dp.open,
    dp.high,
    dp.low,
    dp.close,
    dp.volume,
    AVG(dp.close) OVER (PARTITION BY dp.ticker ORDER BY dp.date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as MA20,
    AVG(dp.close) OVER (PARTITION BY dp.ticker ORDER BY dp.date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as MA50
FROM public.daily_prices dp;

CREATE OR REPLACE VIEW public.volume_analysis AS
SELECT 
    dp.ticker,
    dp.date,
    dp.volume,
    AVG(dp.volume) OVER (PARTITION BY dp.ticker ORDER BY dp.date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as avg_20day_volume
FROM public.daily_prices dp;

-- Create policies
CREATE POLICY stocks_select_policy ON public.stocks
    FOR SELECT
    TO public
    USING (true);

CREATE POLICY stocks_insert_policy ON public.stocks
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY daily_prices_select_policy ON public.daily_prices
    FOR SELECT
    TO public
    USING (true);

CREATE POLICY daily_prices_insert_policy ON public.daily_prices
    FOR INSERT
    TO authenticated
    WITH CHECK (true);
