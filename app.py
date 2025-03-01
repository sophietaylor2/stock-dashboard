from flask import Flask, render_template, jsonify
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import plotly.utils
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'lucydog1019'),
    'database': os.getenv('DB_NAME', 'financial_data')
}

def get_db_connection():
    """Create database connection"""
    connection_string = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    engine = create_engine(connection_string)
    return engine

def create_candlestick_chart(ticker, days=30):
    """Create a candlestick chart for the given ticker"""
    engine = get_db_connection()
    
    # Get stock data
    query = text("""
        SELECT date, open, high, low, close, volume
        FROM daily_prices
        WHERE ticker = :ticker
        AND date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        ORDER BY date
    """)
    
    df = pd.read_sql(query, engine, params={'ticker': ticker, 'days': days})
    
    # Create candlestick chart
    fig = go.Figure(data=[go.Candlestick(x=df['date'],
                                        open=df['open'],
                                        high=df['high'],
                                        low=df['low'],
                                        close=df['close'])])
    
    # Update layout
    fig.update_layout(
        title=f'{ticker} Stock Price',
        yaxis_title='Stock Price (USD)',
        xaxis_title='Date',
        template='plotly_dark',
        yaxis_tickprefix='$'
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

def create_volume_chart(ticker, days=30):
    """Create a volume chart for the given ticker"""
    engine = get_db_connection()
    
    # Get stock data
    query = text("""
        SELECT date, volume
        FROM daily_prices
        WHERE ticker = :ticker
        AND date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
        ORDER BY date
    """)
    
    df = pd.read_sql(query, engine, params={'ticker': ticker, 'days': days})
    
    # Create volume chart
    fig = go.Figure(data=[go.Bar(x=df['date'], y=df['volume'], name='Volume')])
    
    # Update layout
    fig.update_layout(
        title=f'{ticker} Trading Volume',
        yaxis_title='Volume',
        xaxis_title='Date',
        template='plotly_dark'
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/chart/<ticker>')
def get_charts(ticker):
    """Get charts for the specified ticker"""
    candlestick = create_candlestick_chart(ticker)
    volume = create_volume_chart(ticker)
    
    return jsonify({
        'candlestick': candlestick,
        'volume': volume
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
