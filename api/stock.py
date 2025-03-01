from http.server import BaseHTTPRequestHandler
from sqlalchemy import create_engine, text
import json
import os
from urllib.parse import parse_qs, urlparse

def get_db_connection():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return create_engine(db_url)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse the path to get the ticker
            path_parts = self.path.split('/')
            if len(path_parts) < 3:
                self.send_error(400, "Invalid request")
                return
                
            ticker = path_parts[2].upper()
            
            # Get stock data
            engine = get_db_connection()
            query = text("""
                SELECT date, open, high, low, close, volume
                FROM daily_prices
                WHERE ticker = :ticker
                AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                ORDER BY date
            """)
            
            with engine.connect() as conn:
                result = conn.execute(query, {'ticker': ticker})
                data = []
                for row in result:
                    data.append({
                        'date': row.date.strftime('%Y-%m-%d'),
                        'open': float(row.open),
                        'high': float(row.high),
                        'low': float(row.low),
                        'close': float(row.close),
                        'volume': int(row.volume)
                    })
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            
        except Exception as e:
            self.send_error(500, str(e))
