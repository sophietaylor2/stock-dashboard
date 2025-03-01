import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import plotly.graph_objects as go
import plotly.utils
import pandas as pd
import json
from db import get_db_connection, init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Dashboard")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise



def create_candlestick_chart(ticker, days=30):
    """Create a candlestick chart for the given ticker"""
    try:
        engine = get_db_connection()
        logger.info(f"Creating candlestick chart for {ticker} over {days} days")
        
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
    try:
        engine = get_db_connection()
        logger.info(f"Creating volume chart for {ticker} over {days} days")
        
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main page"""
    try:
        logger.info("Rendering index page")
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        raise HTTPException(status_code=500, detail="Error rendering page")

@app.get("/api/chart/{ticker}")
async def get_charts(ticker: str):
    """Get charts for the specified ticker"""
    try:
        logger.info(f"Generating charts for ticker: {ticker}")
        candlestick = create_candlestick_chart(ticker)
        volume = create_volume_chart(ticker)
        
        return {
            'candlestick': candlestick,
            'volume': volume
        }
    except Exception as e:
        logger.error(f"Error generating charts for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating charts: {str(e)}")
