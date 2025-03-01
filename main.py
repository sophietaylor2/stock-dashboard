from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import json
from datetime import datetime, timedelta
from db import get_db_connection

app = FastAPI()

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



def get_stock_data(ticker, days=30):
    """Get stock data for the given ticker"""
    try:
        engine = get_db_connection()
        
        # Get stock data
        query = text("""
            SELECT date, open, high, low, close, volume
            FROM daily_prices
            WHERE ticker = :ticker
            AND date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
            ORDER BY date
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {'ticker': ticker, 'days': days})
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
            return data
    except Exception as e:
        print(f"Error getting stock data: {str(e)}")
        return []

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
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/stock/{ticker}")
async def get_stock_info(ticker: str):
    """Get stock data for the specified ticker"""
    data = get_stock_data(ticker)
    return JSONResponse(content=data)
