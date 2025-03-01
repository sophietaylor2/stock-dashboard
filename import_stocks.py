import yfinance as yf
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pandas as pd
import time
import random

# Database connection URL
DATABASE_URL = "mysql://root:CjnVuCPQDUUjVFKqnLVCywJFswPtgcAq@maglev.proxy.rlwy.net:26984/railway"

def import_stock_data(ticker_symbol, days=365):
    try:
        # Create SQLAlchemy engine
        engine = create_engine(DATABASE_URL)
        
        # Get stock data from yfinance
        ticker = yf.Ticker(ticker_symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        df = ticker.history(start=start_date, end=end_date)
        
        # Reset index to make Date a column
        df = df.reset_index()
        
        with engine.connect() as conn:
            # Insert ticker into stocks table
            conn.execute(
                text("INSERT IGNORE INTO stocks (ticker) VALUES (:ticker)"),
                {"ticker": ticker_symbol}
            )
            conn.commit()
            
            # Prepare and insert daily prices
            for _, row in df.iterrows():
                conn.execute(
                    text("""
                    INSERT IGNORE INTO daily_prices 
                    (ticker, date, open, high, low, close, volume)
                    VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
                    """),
                    {
                        "ticker": ticker_symbol,
                        "date": row['Date'].date(),
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": int(row['Volume'])
                    }
                )
                conn.commit()
        
        print(f"Successfully imported data for {ticker_symbol}")
        return True
        
    except Exception as e:
        print(f"Error importing {ticker_symbol}: {str(e)}")
        return False

def main():
    # List of popular stocks to import
    stocks = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'NVDA']
    
    for stock in stocks:
        retries = 3
        while retries > 0:
            if import_stock_data(stock):
                break
            retries -= 1
            if retries > 0:
                # Random delay between 5-15 seconds
                delay = random.uniform(5, 15)
                print(f"Retrying {stock} in {delay:.1f} seconds...")
                time.sleep(delay)
        # Add delay between different stocks
        if stock != stocks[-1]:
            delay = random.uniform(3, 8)
            print(f"Waiting {delay:.1f} seconds before next stock...")
            time.sleep(delay)

if __name__ == "__main__":
    main()
