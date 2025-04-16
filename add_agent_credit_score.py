"""
Migration script to add credit score capabilities to AI Agents.
This adds:
1. Credit score columns to the AIAgent table
2. The new Repayment table
3. A balance_after column to the Transaction table
"""

from sqlalchemy import create_engine, MetaData, Table, Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import text
from datetime import datetime
import logging
import os
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Run the database migration to add credit score functionality to AI Agents"""
    # Get database URL from environment or use a default for development
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/tradeline.db')
    
    # Connect to the database
    logger.info(f"Connecting to database...")
    engine = create_engine(database_url)
    
    # Create a connection
    with engine.connect() as connection:
        # Begin a transaction
        transaction = connection.begin()
        try:
            # Create a metadata object
            metadata = MetaData()
            metadata.reflect(bind=engine)
            
            # 1. Add credit score columns to AIAgent table if they don't exist
            if 'ai_agent' in metadata.tables:
                # Check if the credit_score column already exists
                ai_agent_table = metadata.tables['ai_agent']
                
                # Add credit_score column if it doesn't exist
                if 'credit_score' not in ai_agent_table.c:
                    logger.info("Adding credit_score column to ai_agent table")
                    connection.execute(text(
                        "ALTER TABLE ai_agent ADD COLUMN credit_score INTEGER DEFAULT 600"
                    ))
                    
                # Add credit_score_updated column if it doesn't exist
                if 'credit_score_updated' not in ai_agent_table.c:
                    logger.info("Adding credit_score_updated column to ai_agent table")
                    # SQLite doesn't support DEFAULT CURRENT_TIMESTAMP when adding columns
                    connection.execute(text(
                        "ALTER TABLE ai_agent ADD COLUMN credit_score_updated DATETIME"
                    ))
                    # Set default values for existing rows
                    connection.execute(text(
                        "UPDATE ai_agent SET credit_score_updated = CURRENT_TIMESTAMP"
                    ))
                    
                # Add credit_score_history column if it doesn't exist
                if 'credit_score_history' not in ai_agent_table.c:
                    logger.info("Adding credit_score_history column to ai_agent table")
                    connection.execute(text(
                        "ALTER TABLE ai_agent ADD COLUMN credit_score_history TEXT"
                    ))
            else:
                logger.error("ai_agent table does not exist. Migration cannot proceed.")
                transaction.rollback()
                return
            
            # 2. Add balance_after column to Transaction table if it doesn't exist
            if 'transaction' in metadata.tables:
                # Check if the balance_after column already exists
                transaction_table = metadata.tables['transaction']
                
                if 'balance_after' not in transaction_table.c:
                    logger.info("Adding balance_after column to transaction table")
                    # Use quotes around 'transaction' as it's a reserved keyword in SQLite
                    connection.execute(text(
                        'ALTER TABLE "transaction" ADD COLUMN balance_after FLOAT'
                    ))
            else:
                logger.warning("transaction table does not exist. Skipping transaction table updates.")
            
            # 3. Create the Repayment table if it doesn't exist
            if 'repayment' not in metadata.tables:
                logger.info("Creating repayment table")
                connection.execute(text("""
                    CREATE TABLE repayment (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id INTEGER NOT NULL,
                        tradeline_allocation_id INTEGER NOT NULL,
                        amount FLOAT NOT NULL,
                        due_date DATETIME NOT NULL,
                        payment_date DATETIME,
                        status VARCHAR(50) DEFAULT 'scheduled',
                        description TEXT,
                        FOREIGN KEY (agent_id) REFERENCES ai_agent (id),
                        FOREIGN KEY (tradeline_allocation_id) REFERENCES ai_agent_allocation (id)
                    )
                """))
            else:
                logger.info("repayment table already exists")
            
            # Commit the transaction
            transaction.commit()
            logger.info("Migration completed successfully")
            
        except Exception as e:
            # Roll back the transaction in case of error
            transaction.rollback()
            logger.error(f"An error occurred during migration: {str(e)}")
            raise

if __name__ == "__main__":
    run_migration()