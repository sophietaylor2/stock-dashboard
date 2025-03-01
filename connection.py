import mysql.connector
from mysql.connector import Error

# Function to create connection to MySQL
def create_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="lucydog1019",  # Replace with your password
            database="market_trends"  # Replace with your database name
        )
        
        if connection.is_connected():
            print("Successfully connected to MySQL database")
            return connection
        else:
            print("Connection failed.")
            return None
            
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

# Function to insert data into the database
def insert_stock_data(connection, stock_data):
    cursor = connection.cursor()
    
    insert_query = """
    INSERT INTO historical_prices (ticker, date, open, high, low, close, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    for ticker, data in stock_data.items():
        for _, row in data.iterrows():
            values = (ticker, row.name, row['Open'], row['High'], row['Low'], row['Close'], row['Volume'])
            cursor.execute(insert_query, values)
    
    connection.commit()
    print("Stock data successfully inserted into the database.")
