import os
from sqlalchemy import create_engine, text

# Database connection URL
DATABASE_URL = "mysql://root:CjnVuCPQDUUjVFKqnLVCywJFswPtgcAq@maglev.proxy.rlwy.net:26984/railway"

def test_connection():
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Database connection successful!")
            
            # Create tables
            with open('schema.sql', 'r') as f:
                schema = f.read()
                
            # Execute each statement
            for statement in schema.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
                    conn.commit()
            
            print("Database schema created successfully!")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_connection()
