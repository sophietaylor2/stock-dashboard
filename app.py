from flask import Flask, render_template, jsonify, send_from_directory
from datetime import datetime, timedelta
import json
import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app with explicit template and static folders
app = Flask(__name__,
           template_folder=os.path.abspath('templates'),
           static_folder=os.path.abspath('static'))

# Enable debug logging
app.logger.setLevel('DEBUG')

# Get Supabase credentials from environment variables
SUPABASE_URL = os.getenv('SUPABASE_URL')

# Log environment information
app.logger.debug(f'Current directory: {os.getcwd()}')
app.logger.debug(f'Template folder: {app.template_folder}')
app.logger.debug(f'Static folder: {app.static_folder}')
app.logger.debug(f'Available templates: {os.listdir(app.template_folder) if os.path.exists(app.template_folder) else "Not found"}')
app.logger.debug(f'Supabase URL: {SUPABASE_URL if SUPABASE_URL else "Not found"}')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    app.logger.error('Supabase credentials not found in environment variables')

try:
    # Initialize Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    app.logger.debug('Supabase client initialized successfully')
except Exception as e:
    app.logger.error(f'Failed to initialize Supabase client: {e}')

@app.route('/test')
def test():
    """Test route to verify the app is running"""
    return jsonify({
        'status': 'ok',
        'environment': {
            'cwd': os.getcwd(),
            'template_folder': app.template_folder,
            'static_folder': app.static_folder,
            'templates_exist': os.path.exists(app.template_folder),
            'templates': os.listdir(app.template_folder) if os.path.exists(app.template_folder) else [],
            'supabase_url_set': bool(SUPABASE_URL),
            'supabase_key_set': bool(SUPABASE_KEY)
        }
    })

def get_stock_data(ticker, days=30):
    """Get stock data for the given ticker"""
    from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # Get price data
    price_data = supabase.table('moving_averages')\
        .select('*')\
        .eq('ticker', ticker)\
        .gte('date', from_date)\
        .order('date')\
        .execute()
    
    # Get volume data
    volume_data = supabase.table('volume_analysis')\
        .select('*')\
        .eq('ticker', ticker)\
        .gte('date', from_date)\
        .order('date')\
        .execute()
    
    return {
        'price_data': price_data.data,
        'volume_data': volume_data.data
    }

def get_stock_summary(ticker):
    """Get summary statistics for the given ticker"""
    # Get latest performance data
    performance = supabase.table('stock_performance')\
        .select('*')\
        .eq('ticker', ticker)\
        .execute()
    
    # Get latest price statistics
    stats = supabase.table('price_statistics')\
        .select('*')\
        .eq('ticker', ticker)\
        .order('date', desc=True)\
        .limit(1)\
        .execute()
    
    performance = performance.data[0] if performance.data else None
    stats = stats.data[0] if stats.data else None
    
    if performance and stats:
        return {
            'ticker': ticker,
            'latest_price': stats['close'],
            'weekly_return': performance['weekly_return'],
            'monthly_return': performance['monthly_return'],
            'yearly_return': performance['yearly_return'],
            '52_week_low': stats['period_low'],
            '52_week_high': stats['period_high'],
            'price_position': stats['price_position_percent'],
            'avg_volume': stats['avg_volume']
        }
    return None

@app.errorhandler(500)
def handle_500(error):
    app.logger.error(f'Server error: {error}')
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500

@app.route('/')
def index():
    """Render the main page"""
    try:
        # Get list of available tickers
        response = supabase.table('stocks')\
            .select('ticker')\
            .order('ticker')\
            .execute()
        
        tickers = [row['ticker'] for row in response.data]
        return render_template('index.html', tickers=tickers)
    except Exception as e:
        app.logger.error(f'Error in index route: {e}')
        return jsonify({
            'error': 'Failed to fetch tickers',
            'message': str(e)
        }), 500

@app.route('/api/data/<ticker>')
def get_data(ticker):
    """Get stock data and summary for the specified ticker"""
    try:
        data = get_stock_data(ticker)
        summary = get_stock_summary(ticker)
        
        return jsonify({
            'data': data,
            'summary': summary
        })
    except Exception as e:
        app.logger.error(f'Error fetching data for {ticker}: {e}')
        return jsonify({
            'error': f'Failed to fetch data for {ticker}',
            'message': str(e)
        }), 500

@app.route('/api/stocks/gainers')
def get_top_gainers():
    """Get top gaining stocks"""
    response = supabase.table('daily_returns')\
        .select('*')\
        .order('date', desc=True)\
        .limit(1)\
        .execute()
    
    latest_date = response.data[0]['date'] if response.data else None
    
    if latest_date:
        response = supabase.table('daily_returns')\
            .select('*')\
            .eq('date', latest_date)\
            .order('daily_return_percent', desc=True)\
            .limit(5)\
            .execute()
        
        return jsonify(response.data)
    return jsonify([])

@app.route('/api/stocks/volume')
def get_high_volume():
    """Get stocks with unusually high volume"""
    response = supabase.table('volume_analysis')\
        .select('*')\
        .order('date', desc=True)\
        .limit(1)\
        .execute()
    
    latest_date = response.data[0]['date'] if response.data else None
    
    if latest_date:
        response = supabase.table('volume_analysis')\
            .select('ticker, volume, avg_20day_volume')\
            .eq('date', latest_date)\
            .gt('volume', supabase.table('volume_analysis').sql('avg_20day_volume * 2'))\
            .order('volume', desc=True)\
            .limit(5)\
            .execute()
        
        results = []
        for row in response.data:
            volume_increase = ((row['volume'] - row['avg_20day_volume']) / row['avg_20day_volume']) * 100
            results.append({
                'ticker': row['ticker'],
                'volume': row['volume'],
                'avg_20day_volume': row['avg_20day_volume'],
                'volume_increase_percent': round(volume_increase, 2)
            })
        
        return jsonify(results)
    return jsonify([])
            AND volume > avg_20day_volume
        ORDER BY volume_increase_percent DESC
        LIMIT 5
    """
    
    results = conn.execute(query).fetchall()
    return jsonify([dict(row) for row in results])

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
