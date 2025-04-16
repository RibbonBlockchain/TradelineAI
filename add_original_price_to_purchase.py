"""
Migration script to add original_price column to TradelinePurchase table.
This column stores the original price before any discounts are applied.
"""

import os
import logging
from datetime import datetime

from sqlalchemy import create_engine, MetaData, Table, Column, Float, inspect, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db_connection():
    """Create a direct SQLAlchemy engine connection to the database"""
    db_url = os.environ.get('DATABASE_URL')
    logger.info(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    return engine

def add_original_price_column():
    """Add original_price column to the TradelinePurchase table"""
    engine = create_db_connection()
    metadata = MetaData()
    metadata.reflect(engine)
    
    inspector = inspect(engine)
    table_exists = 'tradeline_purchase' in inspector.get_table_names()
    
    if not table_exists:
        logger.error("The tradeline_purchase table doesn't exist in the database.")
        return False
    
    columns = [col['name'] for col in inspector.get_columns('tradeline_purchase')]
    if 'original_price' in columns:
        logger.info("The 'original_price' column already exists in the tradeline_purchase table.")
        return True
    
    # Add the column
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tradeline_purchase ADD COLUMN original_price FLOAT"))
        
        # Set original_price equal to price_paid for existing records
        conn.execute(text("UPDATE tradeline_purchase SET original_price = price_paid"))
        
    logger.info("Successfully added 'original_price' column to tradeline_purchase table.")
    return True

def run_migration():
    """Run the database migration to add original_price functionality to TradelinePurchase"""
    logger.info("Starting migration to add original_price column to TradelinePurchase table")
    success = add_original_price_column()
    
    if success:
        logger.info("Migration completed successfully!")
    else:
        logger.error("Migration failed!")

if __name__ == "__main__":
    run_migration()