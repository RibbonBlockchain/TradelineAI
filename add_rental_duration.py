from app import app, db
import logging
import psycopg2
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_rental_duration_column():
    """Add rental_duration column to Tradeline table"""
    try:
        logger.info("Adding rental_duration column to Tradeline table...")
        
        # Connect directly to the database using psycopg2 rather than SQLAlchemy
        connection_params = {
            'dbname': os.environ.get('PGDATABASE'),
            'user': os.environ.get('PGUSER'),
            'password': os.environ.get('PGPASSWORD'),
            'host': os.environ.get('PGHOST'),
            'port': os.environ.get('PGPORT')
        }
        
        conn = psycopg2.connect(**connection_params)
        conn.autocommit = True  # Set autocommit mode to avoid transaction issues
        
        with conn.cursor() as cursor:
            # Check if column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='tradeline' AND column_name='rental_duration'
            """)
            
            column_exists = cursor.fetchone() is not None
            
            if not column_exists:
                logger.info("Adding rental_duration column...")
                cursor.execute("ALTER TABLE tradeline ADD COLUMN rental_duration INTEGER DEFAULT 1")
                logger.info("rental_duration column added successfully.")
            else:
                logger.info("rental_duration column already exists.")
        
        conn.close()
        logger.info("Database migration completed successfully.")
        
    except Exception as e:
        logger.error(f"Error adding rental_duration column: {str(e)}")
        raise

if __name__ == "__main__":
    add_rental_duration_column()