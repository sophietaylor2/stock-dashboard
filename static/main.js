document.addEventListener('DOMContentLoaded', function() {
    const tickerInput = document.getElementById('ticker');
    const submitButton = document.getElementById('submit');
    const loadingIndicator = document.getElementById('loading');
    const errorMessage = document.getElementById('error');
    const candlestickDiv = document.getElementById('candlestick');
    const volumeDiv = document.getElementById('volume');

    async function fetchStockData(ticker) {
        try {
            loadingIndicator.style.display = 'block';
            errorMessage.style.display = 'none';
            candlestickDiv.innerHTML = '';
            volumeDiv.innerHTML = '';

            const response = await fetch(`/api/stock/${ticker}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Create candlestick chart data
            const candlestickData = [{
                type: 'candlestick',
                x: data.map(d => d.date),
                open: data.map(d => d.open),
                high: data.map(d => d.high),
                low: data.map(d => d.low),
                close: data.map(d => d.close)
            }];

            const candlestickLayout = {
                title: `${ticker} Stock Price`,
                yaxis: { title: 'Stock Price (USD)', tickprefix: '$' },
                xaxis: { title: 'Date' },
                template: 'plotly_dark'
            };

            // Create volume chart data
            const volumeData = [{
                type: 'bar',
                x: data.map(d => d.date),
                y: data.map(d => d.volume),
                name: 'Volume'
            }];

            const volumeLayout = {
                title: `${ticker} Trading Volume`,
                yaxis: { title: 'Volume' },
                xaxis: { title: 'Date' },
                template: 'plotly_dark'
            };

            // Plot charts
            Plotly.newPlot('candlestick', candlestickData, candlestickLayout);
            Plotly.newPlot('volume', volumeData, volumeLayout);

        } catch (error) {
            console.error('Error:', error);
            errorMessage.textContent = `Error: ${error.message}`;
            errorMessage.style.display = 'block';
        } finally {
            loadingIndicator.style.display = 'none';
        }
    }

    submitButton.addEventListener('click', function() {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (ticker) {
            fetchStockData(ticker);
        }
    });

    // Also trigger on Enter key
    tickerInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const ticker = tickerInput.value.trim().toUpperCase();
            if (ticker) {
                fetchStockData(ticker);
            }
        }
    });

    // Load initial data for AAPL
    fetchStockData('AAPL');
});
