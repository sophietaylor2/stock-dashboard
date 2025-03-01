from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_url():
    """Get database URL from environment variables"""
    host = os.getenv('DB_HOST')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    database = os.getenv('DB_NAME')
    port = os.getenv('DB_PORT', '3306')
    
    # Use connection URL if provided (some providers give a single URL)
    if os.getenv('DATABASE_URL'):
        return os.getenv('DATABASE_URL')
    
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

def get_db_connection():
    """Create database connection"""
    engine = create_engine(get_db_url())
    return engine

def init_db():
    """Initialize database tables"""
    engine = get_db_connection()
    
    # Read schema file
    with open('schema.sql', 'r') as f:
        schema = f.read()
    
    # Execute each statement
    with engine.connect() as conn:
        for statement in schema.split(';'):
            if statement.strip():
                conn.execute(text(statement))
                conn.commit()

def test_connection():
    """Test database connection"""
    try:
        engine = get_db_connection()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Database connection successful!")
            return True
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_connection()
