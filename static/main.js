document.addEventListener('DOMContentLoaded', function() {
    const tickerInput = document.getElementById('ticker');
    const submitButton = document.getElementById('submit');
    const loadingIndicator = document.getElementById('loading');
    const errorMessage = document.getElementById('error');

    async function fetchStockData(ticker) {
        try {
            loadingIndicator.style.display = 'block';
            errorMessage.style.display = 'none';
            document.getElementById('candlestick').innerHTML = '';
            document.getElementById('rsi').innerHTML = '';
            document.getElementById('volume').innerHTML = '';

            const response = await fetch(`/api/stock/${ticker}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const responseData = await response.json();
            const data = responseData.prices;
            const indicators = responseData.indicators;

            // Create candlestick chart data with moving averages
            const traces = [
                {
                    type: 'candlestick',
                    x: data.map(d => d.date),
                    open: data.map(d => d.open),
                    high: data.map(d => d.high),
                    low: data.map(d => d.low),
                    close: data.map(d => d.close),
                    name: ticker
                }
            ];

            // Add moving averages
            Object.entries(indicators.moving_averages).forEach(([key, values]) => {
                traces.push({
                    type: 'scatter',
                    x: data.map(d => d.date),
                    y: values,
                    name: key,
                    line: { width: 1 }
                });
            });

            const candlestickLayout = {
                title: `${ticker} Stock Price with Moving Averages`,
                yaxis: { title: 'Stock Price (USD)', tickprefix: '$' },
                xaxis: { title: 'Date' },
                template: 'plotly_dark',
                legend: { orientation: 'h', y: -0.2 }
            };

            // Create RSI chart
            const rsiTrace = {
                type: 'scatter',
                x: data.map(d => d.date),
                y: indicators.rsi,
                name: 'RSI'
            };

            const rsiLayout = {
                title: 'Relative Strength Index (RSI)',
                yaxis: { title: 'RSI', range: [0, 100] },
                xaxis: { title: 'Date' },
                template: 'plotly_dark',
                shapes: [
                    { type: 'line', y0: 70, y1: 70, x0: data[0].date, x1: data[data.length-1].date,
                      line: { color: 'red', width: 1, dash: 'dash' } },
                    { type: 'line', y0: 30, y1: 30, x0: data[0].date, x1: data[data.length-1].date,
                      line: { color: 'green', width: 1, dash: 'dash' } }
                ]
            };

            // Create volume chart with moving average
            const volumeTraces = [
                {
                    type: 'bar',
                    x: data.map(d => d.date),
                    y: data.map(d => d.volume),
                    name: 'Volume'
                },
                {
                    type: 'scatter',
                    x: data.map(d => d.date),
                    y: indicators.volume_ma,
                    name: 'Volume MA (20)',
                    line: { color: 'orange', width: 1 }
                }
            ];

            const volumeLayout = {
                title: `${ticker} Trading Volume with Moving Average`,
                yaxis: { title: 'Volume' },
                xaxis: { title: 'Date' },
                template: 'plotly_dark',
                legend: { orientation: 'h', y: -0.2 }
            };

            // Plot all charts
            Plotly.newPlot('candlestick', traces, candlestickLayout);
            Plotly.newPlot('rsi', [rsiTrace], rsiLayout);
            Plotly.newPlot('volume', volumeTraces, volumeLayout);

        } catch (error) {
            console.error('Error:', error);
            errorMessage.textContent = `Error: ${error.message}`;
            errorMessage.style.display = 'block';
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    // Handle form submission
    submitButton.addEventListener('click', function() {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (ticker) {
            fetchStockData(ticker);
        }
    });

    // Handle Enter key
    tickerInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const ticker = tickerInput.value.trim().toUpperCase();
            if (ticker) {
                fetchStockData(ticker);
            }
        }
    });

    // Handle quick ticker buttons
    document.querySelectorAll('.btn-ticker').forEach(button => {
        button.addEventListener('click', function() {
            document.querySelectorAll('.btn-ticker').forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            fetchStockData(this.dataset.ticker);
        });
    });

    // Load initial data for AAPL
    fetchStockData('AAPL');
});
