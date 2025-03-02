# Stock Dashboard

A Flask-based web application for visualizing stock data with interactive charts and real-time market insights.

## Features

- Interactive stock price charts with candlestick patterns
- Moving averages (20-day and 50-day)
- Volume analysis
- Daily returns tracking
- Top gainers and high-volume stocks

## Tech Stack

- Backend: Flask
- Database: Supabase (PostgreSQL)
- Charts: Plotly.js
- Deployment: Vercel
- Stock Data: Yahoo Finance

## Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   export SUPABASE_URL="your_supabase_url"
   export SUPABASE_KEY="your_supabase_key"
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Deployment to Vercel

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Log in to Vercel:
   ```bash
   vercel login
   ```

3. Set up environment variables in Vercel:
   ```bash
   vercel env add SUPABASE_URL
   vercel env add SUPABASE_KEY
   ```

4. Deploy:
   ```bash
   vercel
   ```

## Database Schema

### Tables

- `stocks`: Stores basic stock information
  - `ticker` (TEXT, PRIMARY KEY)
  - `created_at` (TIMESTAMP)

- `daily_prices`: Stores daily stock price data
  - `id` (BIGSERIAL, PRIMARY KEY)
  - `ticker` (TEXT, FOREIGN KEY)
  - `date` (DATE)
  - `open` (DECIMAL)
  - `high` (DECIMAL)
  - `low` (DECIMAL)
  - `close` (DECIMAL)
  - `volume` (BIGINT)
  - `created_at` (TIMESTAMP)

### Views

- `daily_returns`: Calculates daily return percentages
- `moving_averages`: Computes 20-day and 50-day moving averages
- `volume_analysis`: Analyzes volume trends with 20-day average

## API Endpoints

- `/`: Main dashboard
- `/api/chart/<ticker>`: Get charts and summary for a specific stock
- `/api/stocks/gainers`: Get top gaining stocks
- `/api/stocks/volume`: Get stocks with high volume relative to average
