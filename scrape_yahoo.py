from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import os
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import os
import json
import pickle
from functools import wraps
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import logging
import sqlite3
from sqlite3 import Error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def rate_limit(max_calls: int = 1, period: int = 900) -> Callable:
    """Rate limiting decorator with exponential backoff
    
    Args:
        max_calls: Maximum number of calls allowed in the period
        period: Time period in seconds
    """
    calls = []
    error_count = 0
    last_error_time = 0
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal error_count, last_error_time
            now = time.time()
            
            # Reset error count if enough time has passed
            if now - last_error_time > period * 2:
                error_count = 0
            
            # Remove old calls outside the period
            while calls and calls[0] < now - period:
                calls.pop(0)
            
            # Check if we're within rate limits
            if len(calls) >= max_calls:
                # Calculate base wait time
                wait_time = calls[0] - (now - period)
                
                # Add exponential backoff if we've had errors
                if error_count > 0:
                    wait_time += min(1800, 60 * (2 ** error_count))  # Cap at 30 minutes
                
                if wait_time > 0:
                    logger.info(f'Rate limit reached. Waiting {wait_time:.2f} seconds...')
                    time.sleep(wait_time)
                    calls.pop(0)
            
            # Try the function
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    error_count = max(0, error_count - 1)  # Reduce error count on success
                    calls.append(now)
                    return result
                else:
                    error_count += 1
                    last_error_time = now
                    return None
            except Exception as e:
                error_count += 1
                last_error_time = now
                logger.warning(f'Error in rate-limited function: {str(e)}')
                return None
        return wrapper
    return decorator

def cache_result(cache_dir: str, expire_after: int = 3600) -> Callable:
    """Cache decorator that stores results in files
    
    Args:
        cache_dir: Directory to store cache files
        expire_after: Cache expiry time in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a shorter cache key using hash
            args_str = f"{str(args)}_{str(kwargs)}"
            cache_key = f"{func.__name__}_{hash(args_str)}"
            cache_file = Path(cache_dir) / f"{cache_key}.pkl"
            
            # Create cache directory if it doesn't exist
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if we have a valid cache
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        timestamp, data = pickle.load(f)
                        if time.time() - timestamp <= expire_after:
                            logger.info(f'Cache hit for {func.__name__}')
                            return data
                except Exception as e:
                    logger.warning(f'Error reading cache: {e}')
            
            # Get fresh data
            result = func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                try:
                    with open(cache_file, 'wb') as f:
                        pickle.dump((time.time(), result), f)
                except Exception as e:
                    logger.warning(f'Error writing cache: {e}')
            
            return result
        return wrapper
    return decorator

class AlpacaScraper:
    def __init__(self, data_dir='stock_data', cache_dir='cache', db_path='stock_data.db'):
        """Initialize Alpaca Market Data client
        
        Args:
            data_dir: Directory to store data files
            cache_dir: Directory to store cache
            db_path: SQLite database path
        """
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.db_path = db_path
        
        # Initialize Alpaca client
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError(
                'Alpaca API credentials not found. Please set ALPACA_API_KEY and '
                'ALPACA_API_SECRET environment variables.'
            )
        
        # Initialize stock client
        self.stock_client = StockHistoricalDataClient(api_key, api_secret)
        self.conn = self._create_connection()
        
        # Create necessary directories
        for d in [data_dir, cache_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
    
    def _create_connection(self):
        """Create a database connection"""
        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            # Create connection with foreign key support
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            
            # Initialize schema
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema = f.read()
                conn.executescript(schema)
                conn.commit()
            return conn
        except Error as e:
            logger.error(f'Error creating database connection: {e}')
            raise
    
    @rate_limit(max_calls=200, period=60)
    def fetch_stock_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical stock data from Alpaca
        
        Args:
            symbol: Stock symbol
            start_date: Start date for data fetch
            end_date: End date for data fetch
            
        Returns:
            DataFrame with stock data or None if error
        """
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date
            )
            bars = self.stock_client.get_stock_bars(request)
            
            if bars and hasattr(bars, 'df'):
                df = bars.df
                if not df.empty:
                    df = df.reset_index()
                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.date
                    return df
            return None
        except Exception as e:
            logger.error(f'Error fetching data for {symbol}: {e}')
            return None

    def save_to_database(self, symbol: str, data: pd.DataFrame) -> bool:
        """Save stock data to SQLite database
        
        Args:
            symbol: Stock symbol
            data: DataFrame with stock data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Insert stock if not exists
            self.conn.execute(
                'INSERT OR IGNORE INTO stocks (ticker) VALUES (?)',
                (symbol,)
            )
            
            # Insert daily prices
            for _, row in data.iterrows():
                self.conn.execute(
                    '''
                    INSERT OR REPLACE INTO daily_prices 
                    (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (symbol, row['timestamp'], row['open'], 
                     row['high'], row['low'], row['close'], 
                     row['volume'])
                )
            
            self.conn.commit()
            return True
        except Error as e:
            logger.error(f'Error saving data to database: {e}')
            self.conn.rollback()
            return False

    def update_stock_data(self, symbols: list[str], days_back: int = 365) -> dict[str, bool]:
        """Update stock data for multiple symbols
        
        Args:
            symbols: List of stock symbols
            days_back: Number of days of historical data to fetch
            
        Returns:
            Dictionary of symbols and their success status
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        results = {}
        
        for symbol in symbols:
            logger.info(f'Fetching data for {symbol}')
            data = self.fetch_stock_data(symbol, start_date, end_date)
            
            if data is not None:
                success = self.save_to_database(symbol, data)
                results[symbol] = success
                if success:
                    logger.info(f'Successfully updated data for {symbol}')
                else:
                    logger.error(f'Failed to save data for {symbol}')
            else:
                results[symbol] = False
                logger.error(f'Failed to fetch data for {symbol}')
        
        return results
    def __init__(self, data_dir='stock_data', cache_dir='cache', db_path='stock_data.db'):
        """Initialize Alpaca Market Data client
        
        Args:
            data_dir: Directory to store data files
            cache_dir: Directory to store cache
            db_path: SQLite database path
        """
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.db_path = db_path
        
        # Initialize Alpaca client
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError(
                'Alpaca API credentials not found. Please set ALPACA_API_KEY and '
                'ALPACA_API_SECRET environment variables.'
            )
        
        # Initialize stock client
        self.stock_client = StockHistoricalDataClient(api_key, api_secret)
        self.conn = self._create_connection()
        
        # Create necessary directories
        for d in [data_dir, cache_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
        
    
    def _create_connection(self):
        """Create a database connection"""
        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            # Create connection with foreign key support
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            
            # Initialize schema
            schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema = f.read()
                conn.executescript(schema)
                conn.commit()
            return conn
        except Error as e:
            logger.error(f'Error creating database connection: {e}')
            raise
            return conn
        except Error as e:
            logger.error(f'Error connecting to database: {e}')
            return None

    def _ensure_ticker_exists(self, ticker):
        """Ensure ticker exists in stocks table"""
        try:
            # First check if the ticker exists
            cursor = self.conn.cursor()
            cursor.execute('SELECT 1 FROM stocks WHERE ticker = ?', (ticker,))
            if not cursor.fetchone():
                # Insert the ticker if it doesn't exist
                cursor.execute(
                    'INSERT INTO stocks (ticker) VALUES (?)',
                    (ticker,)
                )
                self.conn.commit()
                logger.info(f'Added new ticker: {ticker}')
        except Error as e:
            logger.error(f'Error ensuring ticker exists: {e}')

    def save_daily_data(self, ticker: str, data: pd.DataFrame):
        """Save daily price data to database"""
        if data is None or data.empty:
            return

        try:
            # Ensure ticker exists
            self._ensure_ticker_exists(ticker)

            # Prepare data for insertion
            data_tuples = []
            for _, row in data.iterrows():
                try:
                        # Convert timestamp to date string
                    date_str = row['timestamp'].strftime('%Y-%m-%d')
                    
                    # Create data tuple
                    data_tuple = (
                        ticker,
                        date_str,
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    )
                    data_tuples.append(data_tuple)
                except (KeyError, ValueError) as e:
                    logger.warning(f'Error processing row for {ticker}: {e}')
                    continue

            if data_tuples:
                # Insert data
                self.conn.executemany(
                    '''INSERT OR REPLACE INTO daily_prices 
                       (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    data_tuples
                )
                self.conn.commit()
                logger.info(f'Saved {len(data_tuples)} records for {ticker}')
            else:
                logger.warning(f'No valid data to save for {ticker}')
        except Error as e:
            logger.error(f'Error saving daily data: {e}')

    def _create_session_pool(self, num_sessions=5):
        """Create a pool of sessions with different configurations"""
        sessions = []
        for i in range(num_sessions):
            session = requests.Session()
            
            # Set headers
            session.headers.update({
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            })
            
            # Set proxies if available
            if self.proxies:
                if isinstance(self.proxies, list):
                    # If we have a list of proxies, rotate through them
                    proxy = self.proxies[i % len(self.proxies)]
                    if isinstance(proxy, str):
                        session.proxies = {
                            'http': proxy,
                            'https': proxy
                        }
                    else:
                        session.proxies = proxy
                else:
                    # If we have a single proxy config, use it for all sessions
                    session.proxies = self.proxies
            
            sessions.append(session)
        return sessions
    
    def _get_next_session(self):
        """Get the next session from the pool"""
        session = self.sessions[self.current_session_idx]
        self.current_session_idx = (self.current_session_idx + 1) % len(self.sessions)
        
        # Rotate user agent
        session.headers['User-Agent'] = random.choice(self.user_agents)
        return session
    
    @rate_limit(max_calls=2, period=3600)  # Limit to 2 calls per hour
    @cache_result(cache_dir='cache', expire_after=300)  # Cache for 5 minutes
    @rate_limit(max_calls=200, period=60)  # Alpaca allows 200 requests per minute
    def get_market_data(self, symbol: str, start_date: datetime, end_date: datetime = None, 
                       timeframe: TimeFrame = TimeFrame.Day, is_crypto: bool = False) -> Optional[Dict[str, Any]]:
        """Get market data for stocks
        
        Args:
            symbol: Stock symbol (e.g. 'AAPL')
            start_date: Start date for historical data
            end_date: End date (defaults to now)
            timeframe: Data timeframe (Day, Hour, Minute)
            is_crypto: Whether the symbol is a crypto pair (not supported in this version)
        """
        try:
            if is_crypto:
                logger.warning("Crypto not supported in this version")
                return None
                
            end_date = end_date or datetime.now()
            
            # Get stock bars
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=timeframe,
                start=start_date,
                end=end_date
            )
            bars = self.stock_client.get_stock_bars(request)
            
            logger.info(f'Got bars response: {bars}')
            if bars and symbol in bars:
                # Convert bars to list of dictionaries
                data = []
                for bar in bars[symbol]:
                    data.append({
                        'timestamp': bar.timestamp,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume)
                    })
                
                # Convert to DataFrame for saving
                df = pd.DataFrame(data)
                
                # Save to database
                self.save_daily_data(symbol, df)
                
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting data from Alpaca: {e}")
            return None
        try:
            # Try yfinance first
            stock = yf.Ticker(ticker)
            
            # Add delay before request
            time.sleep(2)  # 2 second delay between requests
            
            # Get daily data with more conservative period
            daily_data = stock.history(period='5d')  # Reduced from 1mo to 5 days
            if not daily_data.empty:
                self.save_daily_data(ticker, daily_data)
                time.sleep(1)  # Additional delay after successful request
            info = stock.info
            
            if info:
                stock_data = {
                    'ticker': ticker,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'price': info.get('regularMarketPrice', 'N/A'),
                    'market_cap': info.get('marketCap', 'N/A'),
                    'daily_change': info.get('regularMarketChangePercent', 'N/A'),
                    'volume': info.get('regularMarketVolume', 'N/A')
                }
                logger.info(f'Successfully fetched current data for {ticker} using yfinance')
                return stock_data
            
            # If yfinance fails, try web scraping with exponential backoff
            logger.info(f"yfinance failed for {ticker}, trying web scraping...")
            
            url = f"https://finance.yahoo.com/quote/{ticker}"
            
            for attempt in range(3):  # Try 3 times
                try:
                    time.sleep((2 ** attempt) * 2)  # 2, 4, 8 seconds
                    
                    response = self._get_next_session().get(url)
                    if response.status_code == 429:  # Too Many Requests
                        logger.warning(f'Rate limited on attempt {attempt + 1}. Waiting before retry...')
                        continue
                    elif response.status_code != 200:
                        logger.warning(f'HTTP {response.status_code} on attempt {attempt + 1}')
                        continue
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    stock_data = {
                        'ticker': ticker,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Get current price
                    price = soup.find('fin-streamer', {'data-symbol': ticker, 'data-field': 'regularMarketPrice'})
                    if price and price.get('value'):
                        try:
                            stock_data['price'] = float(price['value'])
                        except (ValueError, TypeError):
                            continue
                    
                    # Get other metrics
                    table = soup.find('table', {'class': 'W(100%)'})
                    if table:
                        rows = table.find_all('tr')
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) == 2:
                                label = cols[0].text.strip().lower()
                                value = cols[1].text.strip().replace(',', '')
                                
                                try:
                                    if 'market cap' in label:
                                        stock_data['market_cap'] = value
                                    elif 'volume' in label:
                                        stock_data['volume'] = int(value)
                                except (ValueError, TypeError):
                                    continue
                    
                    if len(stock_data) >= 3:  # At least ticker, timestamp, and one metric
                        logger.info(f'Successfully fetched current data for {ticker} using web scraping')
                        return stock_data
                    
                except Exception as e:
                    logger.warning(f'Web scraping attempt {attempt + 1} failed for {ticker}: {e}')
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error fetching current data for {ticker}: {str(e)}")
            return None

    @rate_limit(max_calls=2, period=3600)  # Limit to 2 calls per hour
    @cache_result(cache_dir='cache', expire_after=3600)  # Cache for 1 hour
    def get_historical_data(self, ticker: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Get historical stock data using multiple methods with rate limiting and caching"""
        try:
            # Try yfinance first with exponential backoff
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            for attempt in range(3):  # Try 3 times
                try:
                    base_wait = (2 ** attempt) * 60  # 60, 120, 240 seconds
                    # Add random jitter between 0-30 seconds
                    wait_time = base_wait + random.uniform(0, 30)
                    if attempt > 0:
                        logger.info(f'Waiting {wait_time} seconds before attempt {attempt + 1}...')
                        time.sleep(wait_time)
                    
                    df = yf.download(
                        ticker,
                        start=start_date,
                        end=end_date,
                        progress=False
                    )
                    
                    if df is not None and not df.empty:
                        logger.info(f'Successfully fetched historical data for {ticker} using yfinance')
                        return df
                except Exception as e:
                    logger.warning(f'Attempt {attempt + 1} failed for {ticker}: {e}')
                    continue
            
            # If download fails, try Ticker object
            time.sleep(1)
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if not df.empty:
                return df
            
            # If both yfinance methods fail, try web scraping with exponential backoff
            logger.info(f"yfinance methods failed for {ticker}, trying web scraping...")
            
            url = f"https://finance.yahoo.com/quote/{ticker}/history"
            
            for attempt in range(3):  # Try 3 times
                try:
                    time.sleep((2 ** attempt) * 2)  # 2, 4, 8 seconds
                    
                    response = self._get_next_session().get(url)
                    if response.status_code == 429:  # Too Many Requests
                        logger.warning(f'Rate limited on attempt {attempt + 1}. Waiting before retry...')
                        continue
                    elif response.status_code != 200:
                        logger.warning(f'HTTP {response.status_code} on attempt {attempt + 1}')
                        continue
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find the historical data table
                    table = soup.find('table', {'data-test': 'historical-prices'})
                    if not table:
                        logger.warning(f'Historical data table not found for {ticker}')
                        continue
                    
                    # Parse table data
                    data = []
                    rows = table.find_all('tr')[1:]  # Skip header row
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 6:  # Date, Open, High, Low, Close, Volume
                            try:
                                date = pd.to_datetime(cols[0].text)
                                data.append({
                                    'Date': date,
                                    'Open': float(cols[1].text.replace(',', '')),
                                    'High': float(cols[2].text.replace(',', '')),
                                    'Low': float(cols[3].text.replace(',', '')),
                                    'Close': float(cols[4].text.replace(',', '')),
                                    'Volume': int(cols[5].text.replace(',', ''))
                                })
                            except (ValueError, TypeError) as e:
                                logger.debug(f'Error parsing row: {e}')
                                continue
                    
                    if data:
                        df = pd.DataFrame(data)
                        df.set_index('Date', inplace=True)
                        df.sort_index(inplace=True)
                        logger.info(f'Successfully fetched historical data for {ticker} using web scraping')
                        return df
                    
                except Exception as e:
                    logger.warning(f'Web scraping attempt {attempt + 1} failed for {ticker}: {e}')
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error fetching historical data for {ticker}: {str(e)}")
            return None


            
        except Exception as e:
            print(f"Error fetching historical data for {ticker}: {str(e)}")
            return None

        except Exception as e:
            print(f"Error fetching historical data for {ticker}: {str(e)}")
            return None

    def save_data(self, data, ticker, data_type='daily'):
        timestamp = datetime.now().strftime('%Y%m%d')
        
        if data_type == 'daily':
            filename = os.path.join(self.data_dir, 'daily', f'stock_data_{timestamp}.json')
        else:
            filename = os.path.join(self.data_dir, 'historical', 'stock_data_historical.json')
        
        # Add ticker to each data point
        for point in data:
            point['ticker'] = ticker
        
        # Load existing data if file exists
        existing_data = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        # Remove existing data for this ticker
        existing_data = [d for d in existing_data if d.get('ticker') != ticker]
        
        # Add new data
        existing_data.extend(data)
        
        # Sort by date and ticker
        existing_data.sort(key=lambda x: (x['date'], x['ticker']))
        
        # Save combined data
        with open(filename, 'w') as f:
            json.dump(existing_data, f, indent=4)
    
    def close(self):
        self.driver.quit()

def load_historical_data(data_dir, ticker):
    filename = os.path.join(data_dir, 'historical', f'{ticker}_historical.json')
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return None

def analyze_historical_data(data):
    if not data:
        return None
        
    df = pd.DataFrame(data)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date to ensure correct calculations
    df = df.sort_values('date')
    
    # Get the date range for the last 12 months
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(months=12)
    
    # Filter data for last 12 months
    df = df[df['date'] >= start_date]
    
    # Format the date for daily data
    df['formatted_date'] = df['date'].dt.strftime('%Y-%m-%d')
    
    # Get daily summary
    daily_data = df[['formatted_date', 'price', 'volume']].copy()
    daily_data = daily_data.rename(columns={
        'formatted_date': 'date',
        'price': 'close_price',
        'volume': 'volume'
    })
    
    # Create the analysis dictionary
    analysis = {
        'daily_data': daily_data.to_dict('records'),
        'overall_stats': {
            'max_price': df['price'].max(),
            'min_price': df['price'].min(),
            'avg_price': df['price'].mean(),
            'price_change': df['price'].iloc[-1] - df['price'].iloc[0],
            'price_change_percent': ((df['price'].iloc[-1] - df['price'].iloc[0]) / df['price'].iloc[0]) * 100,
            'avg_daily_volume': df['volume'].mean(),
            'total_trading_days': len(df),
            'monthly_volatility': df.groupby(df['date'].dt.strftime('%Y-%m'))['price'].std().mean()
        }
    }
    
    return analysis

def main():
    # Initialize Alpaca scraper with IEX (free) feed
    try:
        # Initialize database schema
        db_path = 'stock_data.db'
        conn = sqlite3.connect(db_path)
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            conn.executescript(schema_sql)
            conn.commit()
        conn.close()
        
        scraper = AlpacaScraper(use_iex=True)
        
        # Example: Get 1 month of daily data for both stocks and crypto
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Stock examples
        stock_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
        for symbol in stock_symbols:
            try:
                logger.info(f'Fetching stock data for {symbol}...')
                data = scraper.get_market_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=TimeFrame.Day
                )
                if data:
                    # Convert data to DataFrame format
                    df = pd.DataFrame([data])
                    df['Date'] = pd.to_datetime(data['timestamp'])
                    df = df.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    })
                    
                    # Save to database
                    scraper.save_daily_data(symbol, df)
                    logger.info(f'Successfully saved stock data for {symbol}')
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f'Error fetching {symbol}: {e}')
        
        # Crypto examples
        crypto_pairs = ['BTC/USD', 'ETH/USD', 'SOL/USD']
        for pair in crypto_pairs:
            try:
                logger.info(f'Fetching crypto data for {pair}...')
                data = scraper.get_market_data(
                    symbol=pair,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=TimeFrame.Day,
                    is_crypto=True
                )
                if data:
                    # Convert data to DataFrame format
                    df = pd.DataFrame([data])
                    df['Date'] = pd.to_datetime(data['timestamp'])
                    df = df.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    })
                    
                    # Save to database using the base symbol (without /USD)
                    symbol = pair.split('/')[0]
                    scraper.save_daily_data(symbol, df)
                    logger.info(f'Successfully saved crypto data for {symbol}')
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.error(f'Error fetching {pair}: {e}')
                
        logger.info('Finished processing all symbols')
        
    except Exception as e:
        logger.error(f'Error initializing scraper: {e}')

    @rate_limit(max_calls=200, period=60)  # Alpaca rate limits
    def fetch_stock_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical stock data from Alpaca
        
        Args:
            symbol: Stock symbol
            start_date: Start date for data fetch
            end_date: End date for data fetch
            
        Returns:
            DataFrame with stock data or None if error
        """
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date
            )
            bars = self.stock_client.get_stock_bars(request)
            
            if bars and hasattr(bars, 'df'):
                df = bars.df
                if not df.empty:
                    df = df.reset_index()
                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.date
                    return df
            return None
        except Exception as e:
            logger.error(f'Error fetching data for {symbol}: {e}')
            return None

    def save_to_database(self, symbol: str, data: pd.DataFrame) -> bool:
        """Save stock data to SQLite database
        
        Args:
            symbol: Stock symbol
            data: DataFrame with stock data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Insert stock if not exists
            self.conn.execute(
                'INSERT OR IGNORE INTO stocks (ticker) VALUES (?)',
                (symbol,)
            )
            
            # Insert daily prices
            for _, row in data.iterrows():
                self.conn.execute(
                    '''
                    INSERT OR REPLACE INTO daily_prices 
                    (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (symbol, row['timestamp'], row['open'], 
                     row['high'], row['low'], row['close'], 
                     row['volume'])
                )
            
            self.conn.commit()
            return True
        except Error as e:
            logger.error(f'Error saving data to database: {e}')
            self.conn.rollback()
            return False

    def update_stock_data(self, symbols: list[str], days_back: int = 365) -> dict[str, bool]:
        """Update stock data for multiple symbols
        
        Args:
            symbols: List of stock symbols
            days_back: Number of days of historical data to fetch
            
        Returns:
            Dictionary of symbols and their success status
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        results = {}
        
        for symbol in symbols:
            logger.info(f'Fetching data for {symbol}')
            data = self.fetch_stock_data(symbol, start_date, end_date)
            
            if data is not None:
                success = self.save_to_database(symbol, data)
                results[symbol] = success
                if success:
                    logger.info(f'Successfully updated data for {symbol}')
                else:
                    logger.error(f'Failed to save data for {symbol}')
            else:
                results[symbol] = False
                logger.error(f'Failed to fetch data for {symbol}')
        
        return results

def main():
    # Initialize scraper
    scraper = AlpacaScraper()
    
    # Example symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    # Update data for symbols
    results = scraper.update_stock_data(symbols)
    
    # Print results
    for symbol, success in results.items():
        status = 'Success' if success else 'Failed'
        print(f'{symbol}: {status}')

    @rate_limit(max_calls=200, period=60)
    def fetch_stock_data(self, symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Fetch historical stock data from Alpaca
        
        Args:
            symbol: Stock symbol
            start_date: Start date for data fetch
            end_date: End date for data fetch
            
        Returns:
            DataFrame with stock data or None if error
        """
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date
            )
            bars = self.stock_client.get_stock_bars(request)
            
            if bars and hasattr(bars, 'df'):
                df = bars.df
                if not df.empty:
                    df = df.reset_index()
                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.date
                    return df
            return None
        except Exception as e:
            logger.error(f'Error fetching data for {symbol}: {e}')
            return None

    def save_to_database(self, symbol: str, data: pd.DataFrame) -> bool:
        """Save stock data to SQLite database
        
        Args:
            symbol: Stock symbol
            data: DataFrame with stock data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Insert stock if not exists
            self.conn.execute(
                'INSERT OR IGNORE INTO stocks (ticker) VALUES (?)',
                (symbol,)
            )
            
            # Insert daily prices
            for _, row in data.iterrows():
                self.conn.execute(
                    '''
                    INSERT OR REPLACE INTO daily_prices 
                    (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (symbol, row['timestamp'], row['open'], 
                     row['high'], row['low'], row['close'], 
                     row['volume'])
                )
            
            self.conn.commit()
            return True
        except Error as e:
            logger.error(f'Error saving data to database: {e}')
            self.conn.rollback()
            return False

    def update_stock_data(self, symbols: list[str], days_back: int = 365) -> dict[str, bool]:
        """Update stock data for multiple symbols
        
        Args:
            symbols: List of stock symbols
            days_back: Number of days of historical data to fetch
            
        Returns:
            Dictionary of symbols and their success status
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        results = {}
        
        for symbol in symbols:
            logger.info(f'Fetching data for {symbol}')
            data = self.fetch_stock_data(symbol, start_date, end_date)
            
            if data is not None:
                success = self.save_to_database(symbol, data)
                results[symbol] = success
                if success:
                    logger.info(f'Successfully updated data for {symbol}')
                else:
                    logger.error(f'Failed to save data for {symbol}')
            else:
                results[symbol] = False
                logger.error(f'Failed to fetch data for {symbol}')
        
        return results

def main():
    # Initialize scraper
    scraper = AlpacaScraper()
    
    # Example symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    # Update data for symbols
    results = scraper.update_stock_data(symbols)
    
    # Print results
    for symbol, success in results.items():
        status = 'Success' if success else 'Failed'
        print(f'{symbol}: {status}')

def main():
    # Initialize scraper
    scraper = AlpacaScraper()
    
    # Example symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    # Update data for symbols
    results = scraper.update_stock_data(symbols)
    
    # Print results
    for symbol, success in results.items():
        status = 'Success' if success else 'Failed'
        print(f'{symbol}: {status}')

if __name__ == "__main__":
    main()
