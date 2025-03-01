from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
import pandas as pd
import time
import random
import os
import json

class StockScraper:
    def __init__(self, data_dir='stock_data', headless=True):
        # Set up Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Initialize the WebDriver
        self.service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=self.service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.data_dir = data_dir
        
        # Create data directory if it doesn't exist
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            os.makedirs(os.path.join(data_dir, 'historical'))
            os.makedirs(os.path.join(data_dir, 'daily'))
    
    def get_current_data(self, ticker):
        try:
            # Determine the exchange (simple logic - can be expanded)
            exchange = 'NASDAQ' if ticker in ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'NVDA'] else 'NYSE'
            url = f"https://www.google.com/finance/quote/{ticker}:{exchange}"
            self.driver.get(url)
            
            # Add random delay between 2-4 seconds to avoid rate limiting
            time.sleep(random.uniform(2, 4))
            
            # Dictionary to store the data
            stock_data = {'ticker': ticker, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            # Get price
            try:
                price_element = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "YMlKec.fxKbKc")))
                stock_data['price'] = price_element.text.replace('$', '').replace(',', '')
            except:
                stock_data['price'] = 'N/A'
            
            # Get market cap
            try:
                market_cap = self.driver.find_elements(By.CLASS_NAME, "P6K39c")[0].text
                stock_data['market_cap'] = market_cap
            except:
                stock_data['market_cap'] = 'N/A'
            
            # Get daily change
            try:
                change = self.driver.find_elements(By.CLASS_NAME, "P2Luy.Ebnabc")[0].text
                stock_data['daily_change'] = change
            except:
                stock_data['daily_change'] = 'N/A'
                
            # Get volume
            try:
                volume = [elem.text for elem in self.driver.find_elements(By.CLASS_NAME, "P6K39c") 
                         if 'Volume' in elem.find_element(By.XPATH, "./preceding-sibling::div").text][0]
                stock_data['volume'] = volume
            except:
                stock_data['volume'] = 'N/A'
            
            return stock_data
            
        except Exception as e:
            print(f"Error fetching current data for {ticker}: {str(e)}")
            return None

    def get_historical_data(self, ticker):
        try:
            # Go to Yahoo Finance historical data page
            url = f"https://finance.yahoo.com/quote/{ticker}/history"
            self.driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Click the time period dropdown
            try:
                time_filter = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Time Period')]")))
                time_filter.click()
                time.sleep(1)
                
                # Click 'Max' option if available, otherwise use '5Y'
                try:
                    max_option = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Max')]").click()
                except:
                    five_year = self.driver.find_element(By.XPATH, "//button[contains(text(), '5Y')]").click()
                
                time.sleep(1)
                done_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Done')]").click()
                time.sleep(2)
            except Exception as e:
                print(f"Time filter not needed: {str(e)}")
            
            # Get the table data
            table = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            historical_data = []
            for row in rows[1:]:  # Skip header row
                try:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 7:  # Ensure we have all needed columns
                        date = cols[0].text
                        open_price = cols[1].text.replace(',', '')
                        high_price = cols[2].text.replace(',', '')
                        low_price = cols[3].text.replace(',', '')
                        close_price = cols[4].text.replace(',', '')
                        adj_close = cols[5].text.replace(',', '')
                        volume = cols[6].text.replace(',', '')
                        
                        # Skip rows with missing data
                        if all(price != '-' for price in [open_price, high_price, low_price, close_price, adj_close, volume]):
                            point_data = {
                                'date': date,
                                'open': float(open_price),
                                'high': float(high_price),
                                'low': float(low_price),
                                'close': float(close_price),
                                'adj_close': float(adj_close),
                                'volume': int(volume.replace(',', ''))
                            }
                            historical_data.append(point_data)
                except Exception as e:
                    continue
                    
            return historical_data
            
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
    # List of stock tickers to scrape (major tech companies)
    tickers = ["AAPL", "GOOGL", "MSFT"]
    
    # Initialize the scraper
    scraper = StockScraper(headless=True)
    
    # Lists to store data
    daily_data = []
    historical_analyses = []
    
    # Scrape current and historical data for each ticker
    for ticker in tickers:
        print(f"\nProcessing {ticker}...")
        
        # Get current data
        print(f"Fetching current data for {ticker}...")
        current_data = scraper.get_current_data(ticker)
        if current_data:
            daily_data.append(current_data)
            scraper.save_data(current_data, ticker, 'daily')
        
        # Get historical data
        print(f"Fetching historical data for {ticker}...")
        historical_data = scraper.get_historical_data(ticker)
        if historical_data:
            scraper.save_data(historical_data, ticker, 'historical')
            
            # Analyze historical data
            analysis = analyze_historical_data(historical_data)
            if analysis:
                analysis['ticker'] = ticker
                historical_analyses.append(analysis)
    
    # Close the browser
    scraper.close()
    
    # Save and display results
    if daily_data:
        # Save current data
        df_daily = pd.DataFrame(daily_data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        daily_filename = f'stock_data_daily_{timestamp}.csv'
        df_daily.to_csv(daily_filename, index=False)
        print(f"\nDaily data saved to {daily_filename}")
        
        # Save historical analysis
        if historical_analyses:
            # Save overall analysis
            overall_stats = []
            daily_history = []
            
            for analysis in historical_analyses:
                ticker = analysis['ticker']
                analysis['overall_stats']['ticker'] = ticker
                overall_stats.append(analysis['overall_stats'])
                
                # Add ticker to daily data
                for day_data in analysis['daily_data']:
                    day_data['ticker'] = ticker
                    daily_history.append(day_data)
            
            # Save overall statistics
            df_overall = pd.DataFrame(overall_stats)
            overall_filename = f'stock_data_overall_analysis_{timestamp}.csv'
            df_overall.to_csv(overall_filename, index=False)
            print(f"Overall analysis saved to {overall_filename}")
            
            # Save daily data
            all_daily_data = []
            for analysis in historical_analyses:
                daily_df = pd.DataFrame(analysis['daily_data'])
                daily_df['ticker'] = analysis['ticker']
                all_daily_data.append(daily_df)
            
            df_all_daily = pd.concat(all_daily_data)
            daily_hist_filename = f'stock_data_daily_history_{timestamp}.csv'
            df_all_daily.to_csv(daily_hist_filename, index=False)
            print(f"Daily historical data saved to {daily_hist_filename}")
        
        # Display summaries
        print("\nCurrent Stock Data Summary:")
        print(df_daily.to_string())
        
        if historical_analyses:
            print("\nOverall Analysis Summary:")
            print(pd.DataFrame(overall_stats).to_string())
            
            print("\nDaily Data Summary (Last 10 days):")
            all_daily_data = []
            for analysis in historical_analyses:
                daily_df = pd.DataFrame(analysis['daily_data'])
                daily_df['ticker'] = analysis['ticker']
                all_daily_data.append(daily_df)
            
            df_all_daily = pd.concat(all_daily_data)
            df_daily_pivot = df_all_daily.pivot(index='date', columns='ticker', values='close_price')
            print(df_daily_pivot.tail(10).to_string())
    else:
        print("No data was collected.")

if __name__ == "__main__":
    main()
