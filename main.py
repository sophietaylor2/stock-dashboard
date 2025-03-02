from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import json
import os
from datetime import datetime, timedelta
from db import get_db_connection, init_stock_data

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories if they don't exist
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")



def get_stock_data(ticker, days=30):
    """Get stock data for the given ticker"""
    try:
        engine = get_db_connection()
        
        # Get stock data
        query = text("""
            SELECT date, open, high, low, close, volume
            FROM daily_prices
            WHERE ticker = :ticker
            AND date >= date('now', '-' || :days || ' days')
            ORDER BY date
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {'ticker': ticker, 'days': days})
            data = []
            for row in result:
                data.append({
                    'date': row.date,
                    'open': float(row.open),
                    'high': float(row.high),
                    'low': float(row.low),
                    'close': float(row.close),
                    'volume': int(row.volume)
                })
            return data
    except Exception as e:
        print(f"Error getting stock data: {str(e)}")
        return []

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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/stock/{ticker}")
async def get_stock_info(ticker: str):
    # Initialize stock data
    if not init_stock_data(ticker):
        return JSONResponse(
            status_code=404,
            content={"error": f"No data found for ticker {ticker}"}
        )
    
    # Get stock data for the past 60 days
    data = get_stock_data(ticker, days=60)
    
    if not data:
        return JSONResponse(
            status_code=404,
            content={"error": f"No data found for ticker {ticker}"}
        )
    
    # Calculate technical indicators
    moving_averages = calculate_moving_averages(data)
    rsi = calculate_rsi(data)
    volume_ma = calculate_volume_ma(data)
    
    # Return data with indicators
    return {
        "prices": data,
        "indicators": {
            "moving_averages": moving_averages,
            "rsi": rsi,
            "volume_ma": volume_ma
        }
    }
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/stock/{ticker}")
async def get_stock_info(ticker: str):
    """Get stock data for the specified ticker"""
    data = get_stock_data(ticker)
    return JSONResponse(content=data)
