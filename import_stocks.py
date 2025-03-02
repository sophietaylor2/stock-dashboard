from db import get_db_connection, init_stock_data
import time
import random
import sys

def main():
    # Get ticker from command line or use default
    if len(sys.argv) > 1:
        stocks = [sys.argv[1].upper()]
    else:
        stocks = ['AAPL']
    
    for stock in stocks:
        retries = 3
        while retries > 0:
            print(f"Fetching data for {stock}...")
            if init_stock_data(stock):
                print(f"Successfully imported data for {stock}")
                break
            retries -= 1
            if retries > 0:
                # Longer delay between retries
                delay = random.uniform(10, 15)
                print(f"Retrying {stock} in {delay:.1f} seconds...")
                time.sleep(delay)

if __name__ == "__main__":
    main()
