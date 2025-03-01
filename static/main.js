document.addEventListener('DOMContentLoaded', function() {
    const tickerInput = document.getElementById('ticker');
    const submitButton = document.getElementById('submit');
    const loadingIndicator = document.getElementById('loading');
    const errorMessage = document.getElementById('error');
    const candlestickDiv = document.getElementById('candlestick');
    const volumeDiv = document.getElementById('volume');

    async function fetchCharts(ticker) {
        try {
            loadingIndicator.style.display = 'block';
            errorMessage.style.display = 'none';
            candlestickDiv.innerHTML = '';
            volumeDiv.innerHTML = '';

            const response = await fetch(`/api/chart/${ticker}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            // Plot candlestick chart
            const candlestickChart = JSON.parse(data.candlestick);
            Plotly.newPlot('candlestick', candlestickChart.data, candlestickChart.layout);

            // Plot volume chart
            const volumeChart = JSON.parse(data.volume);
            Plotly.newPlot('volume', volumeChart.data, volumeChart.layout);

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
            fetchCharts(ticker);
        }
    });

    // Also trigger on Enter key
    tickerInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const ticker = tickerInput.value.trim().toUpperCase();
            if (ticker) {
                fetchCharts(ticker);
            }
        }
    });

    // Load initial data for AAPL
    fetchCharts('AAPL');
});
