import sqlite3
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
import pandas as pd
from datetime import datetime

def get_sqlite_connection():
    conn = sqlite3.connect('stock_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def migrate_data():
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Connect to SQLite
    sqlite_conn = get_sqlite_connection()
    
    # Migrate stocks table
    print("Migrating stocks table...")
    stocks = pd.read_sql_query("SELECT * FROM stocks", sqlite_conn)
    for _, stock in stocks.iterrows():
        try:
            supabase.table('stocks').insert({
                'ticker': stock['ticker'],
                'created_at': datetime.now().isoformat()
            }).execute()
            print(f"Migrated stock: {stock['ticker']}")
        except Exception as e:
            print(f"Error migrating stock {stock['ticker']}: {e}")
    
    # Migrate daily_prices table
    print("\nMigrating daily_prices table...")
    daily_prices = pd.read_sql_query("SELECT * FROM daily_prices", sqlite_conn)
    
    # Process in batches to avoid memory issues
    batch_size = 1000
    for i in range(0, len(daily_prices), batch_size):
        batch = daily_prices.iloc[i:i+batch_size]
        records = []
        for _, row in batch.iterrows():
            records.append({
                'ticker': row['ticker'],
                'date': row['date'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']),
                'created_at': datetime.now().isoformat()
            })
        
        try:
            supabase.table('daily_prices').insert(records).execute()
            print(f"Migrated {len(records)} price records")
        except Exception as e:
            print(f"Error migrating batch: {e}")
    
    sqlite_conn.close()
    print("\nMigration completed!")

if __name__ == "__main__":
    migrate_data()
