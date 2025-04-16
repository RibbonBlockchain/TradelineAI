"""
Migration script to add wallet_balance column to AIAgent table.
This balance will be used to track stablecoin holdings from DeFi loans.
"""
import sys
import logging
from datetime import datetime
from app import db, app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_wallet_balance_column():
    """Add wallet_balance column to the AIAgent table"""
    try:
        with app.app_context():
            # Check if column exists first
            conn = db.engine.connect()
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('ai_agent')
            column_names = [column['name'] for column in columns]
            
            if 'wallet_balance' not in column_names:
                logger.info("Adding wallet_balance column to AIAgent table...")
                conn.execute(db.text("ALTER TABLE ai_agent ADD COLUMN wallet_balance FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("wallet_balance column added successfully.")
            else:
                logger.info("wallet_balance column already exists.")
            
            conn.close()
            return True
    except Exception as e:
        logger.error(f"Error adding wallet_balance column: {str(e)}")
        return False

def run_migration():
    """Run the database migration to add wallet balance functionality to AI Agents"""
    success = add_wallet_balance_column()
    if success:
        logger.info("Migration completed successfully!")
    else:
        logger.error("Migration failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()