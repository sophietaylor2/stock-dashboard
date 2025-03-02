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

def calculate_moving_averages(data, periods=[20, 50]):
    """Calculate moving averages for the given periods"""
    result = {}
    closes = [d['close'] for d in data]
    for period in periods:
        if len(closes) < period:
            continue
        ma = []
        for i in range(len(closes)):
            if i < period - 1:
                ma.append(None)
            else:
                ma.append(sum(closes[i-period+1:i+1]) / period)
        result[f'MA{period}'] = ma
    return result

def calculate_rsi(data, period=14):
    """Calculate RSI for the given period"""
    closes = [d['close'] for d in data]
    if len(closes) < period + 1:
        return [None] * len(closes)
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi = [None] * period
    
    for i in range(period, len(closes)):
        avg_gain = (avg_gain * (period - 1) + gains[i-1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i-1]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi.append(100 - (100 / (1 + rs)))
    
    return rsi

def calculate_volume_ma(data, period=20):
    """Calculate volume moving average"""
    volumes = [d['volume'] for d in data]
    if len(volumes) < period:
        return [None] * len(volumes)
    
    vol_ma = []
    for i in range(len(volumes)):
        if i < period - 1:
            vol_ma.append(None)
        else:
            vol_ma.append(sum(volumes[i-period+1:i+1]) / period)
    return vol_ma

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
                AND date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
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
            
            # Calculate technical indicators
            moving_averages = calculate_moving_averages(data)
            rsi = calculate_rsi(data)
            volume_ma = calculate_volume_ma(data)
            
            # Add indicators to response
            response_data = {
                'prices': data,
                'indicators': {
                    'moving_averages': moving_averages,
                    'rsi': rsi,
                    'volume_ma': volume_ma
                }
            }
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as e:
            self.send_error(500, str(e))
