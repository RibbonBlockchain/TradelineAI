"""
Migration script to add promo_code_id column to TradelinePurchase table.
This column stores the ID of the promo code used for the purchase.
"""

import os
import logging
from datetime import datetime

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, inspect, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_db_connection():
    """Create a direct SQLAlchemy engine connection to the database"""
    db_url = os.environ.get('DATABASE_URL')
    logger.info(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    return engine

def add_promo_code_id_column():
    """Add promo_code_id column to the TradelinePurchase table"""
    engine = create_db_connection()
    metadata = MetaData()
    metadata.reflect(engine)
    
    inspector = inspect(engine)
    table_exists = 'tradeline_purchase' in inspector.get_table_names()
    
    if not table_exists:
        logger.error("The tradeline_purchase table doesn't exist in the database.")
        return False
    
    columns = [col['name'] for col in inspector.get_columns('tradeline_purchase')]
    if 'promo_code_id' in columns:
        logger.info("The 'promo_code_id' column already exists in the tradeline_purchase table.")
        return True
    
    # Add the column
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tradeline_purchase ADD COLUMN promo_code_id INTEGER"))
        
        # Set default value to null
        conn.execute(text("UPDATE tradeline_purchase SET promo_code_id = NULL"))
        
    logger.info("Successfully added 'promo_code_id' column to tradeline_purchase table.")
    return True

def run_migration():
    """Run the database migration to add promo_code_id functionality to TradelinePurchase"""
    logger.info("Starting migration to add promo_code_id column to TradelinePurchase table")
    success = add_promo_code_id_column()
    
    if success:
        logger.info("Migration completed successfully!")
    else:
        logger.error("Migration failed!")

if __name__ == "__main__":
    run_migration()