from sqlalchemy import create_engine, Column, Integer, String, Numeric, Date, ForeignKey, text, BigInteger
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.schema import UniqueConstraint
import pandas as pd
from datetime import datetime
import json
import os
from scrape_yahoo import StockScraper

# Create the base class for declarative models
Base = declarative_base()

class Stock(Base):
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, nullable=False)
    created_at = Column(Date, default=datetime.now)
    prices = relationship("DailyPrice", back_populates="stock")
    
class DailyPrice(Base):
    __tablename__ = 'daily_prices'
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), ForeignKey('stocks.ticker'), nullable=False)
    date = Column(Date, nullable=False)
    open = Column(Numeric(10,2), nullable=False)
    high = Column(Numeric(10,2), nullable=False)
    low = Column(Numeric(10,2), nullable=False)
    close = Column(Numeric(10,2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    created_at = Column(Date, default=datetime.now)
    
    stock = relationship("Stock", back_populates="prices")
    
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date'),
    )

def init_db(host='localhost', user='root', password='', database='financial_data'):
    """Initialize the database and create tables"""
    # Create MySQL connection URL
    db_url = f'mysql://{user}:{password}@{host}/{database}'
    engine = create_engine(db_url)
    
    # Create tables
    Base.metadata.create_all(engine)
    
    return engine

def get_session(engine):
    """Create a new session"""
    Session = sessionmaker(bind=engine)
    return Session()

def import_daily_history(json_file, host='localhost', user='root', password='', database='financial_data'):
    """Import daily history data from JSON file into MySQL database"""
    # Read JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Initialize database and get session
    engine = init_db(host=host, user=user, password=password, database=database)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Track statistics per ticker
        stats = {}
        
        # Process all data points
        for point in data:
            ticker = point['ticker']
            date = datetime.strptime(point['date'], '%b %d, %Y').date()
            
            # Initialize stats for new ticker
            if ticker not in stats:
                stats[ticker] = {'new': 0, 'updated': 0}
                
                # Create stock record if it doesn't exist
                stock = session.query(Stock).filter_by(ticker=ticker).first()
                if not stock:
                    stock = Stock(ticker=ticker)
                    session.add(stock)
                    session.flush()
            
            # Check if record exists
            existing = session.query(DailyPrice).filter_by(
                ticker=ticker,
                date=date
            ).first()
            
            if existing:
                # Update existing record
                existing.open = point['open']
                existing.high = point['high']
                existing.low = point['low']
                existing.close = point['close']
                existing.volume = point['volume']
                stats[ticker]['updated'] += 1
            else:
                # Create new record
                daily_price = DailyPrice(
                    ticker=ticker,
                    date=date,
                    open=point['open'],
                    high=point['high'],
                    low=point['low'],
                    close=point['close'],
                    volume=point['volume']
                )
                session.add(daily_price)
                stats[ticker]['new'] += 1
        
        # Commit all changes
        session.commit()
        
        # Print import summary for all tickers
        print("\nImport Summary:")
        for ticker, ticker_stats in stats.items():
            print(f"\n{ticker}:")
            print(f"  New records: {ticker_stats['new']}")
            print(f"  Updated records: {ticker_stats['updated']}")
            
            # Query and print data summary
            prices = session.query(DailyPrice).filter_by(ticker=ticker).all()
            if prices:
                dates = [p.date for p in prices]
                opens = [float(p.open) for p in prices]
                highs = [float(p.high) for p in prices]
                lows = [float(p.low) for p in prices]
                closes = [float(p.close) for p in prices]
                volumes = [int(p.volume) for p in prices]
                
                print("\nData Summary:")
                print(f"  Number of days: {len(prices)}")
                print(f"  Date range: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')}")
                print(f"  Average open: ${sum(opens)/len(opens):.2f}")
                print(f"  Average high: ${sum(highs)/len(highs):.2f}")
                print(f"  Average low: ${sum(lows)/len(lows):.2f}")
                print(f"  Average close: ${sum(closes)/len(closes):.2f}")
                print(f"  Average volume: {int(sum(volumes)/len(volumes))}")
                
    except Exception as e:
        print(f"Error importing data: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    # MySQL connection details
    mysql_config = {
        'host': '127.0.0.1',
        'user': 'root',
        'password': 'lucydog1019',
        'database': 'financial_data'
    }
    
    # Initialize scraper and get data
    scraper = StockScraper()
    tickers = ['AAPL', 'GOOGL', 'MSFT']
    
    try:
        # Scrape data for all tickers
        for ticker in tickers:
            print(f"\nScraping {ticker}...")
            historical_data = scraper.get_historical_data(ticker)
            if historical_data:
                scraper.save_data(historical_data, ticker, data_type='historical')
        
        # Import combined data to MySQL
        json_file = os.path.join('stock_data', 'historical', 'stock_data_historical.json')
        if os.path.exists(json_file):
            print("\nImporting combined historical data...")
            import_daily_history(
                json_file,
                host=mysql_config['host'],
                user=mysql_config['user'],
                password=mysql_config['password'],
                database=mysql_config['database']
            )
        else:
            print(f"\nError: Combined data file not found at {json_file}")
    finally:
        scraper.close()
