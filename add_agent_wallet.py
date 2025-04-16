"""
Migration script to add Base Layer 2 blockchain wallet addresses to existing AI Agents.
"""

import os
import sys
import json
import logging
from datetime import datetime
from sqlalchemy import text
from app import app, db
from models import AIAgent
from modules.crypto_wallet import CryptoWalletManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use the database session from app
try:
    session = db.session
    logger.info("Connected to database through app context.")
except Exception as e:
    logger.error(f"Error connecting to database: {e}")
    sys.exit(1)

def add_wallet_columns():
    """Check if wallet columns exist and add them if they don't"""
    try:
        # For SQLite, query the pragma table info to check if column exists
        result = session.execute(text(
            """
            PRAGMA table_info(ai_agent)
            """
        ))
        
        columns = [row[1] for row in result.fetchall()]
        
        if 'wallet_address' not in columns:
            logger.info("Adding wallet columns to AIAgent table...")
            
            # Add the wallet columns one by one (SQLite limitation)
            session.execute(text("ALTER TABLE ai_agent ADD COLUMN wallet_address VARCHAR(128)"))
            session.execute(text("ALTER TABLE ai_agent ADD COLUMN wallet_network VARCHAR(20) DEFAULT 'mainnet'"))
            session.execute(text("ALTER TABLE ai_agent ADD COLUMN wallet_created_date TIMESTAMP"))
            
            session.commit()
            logger.info("Wallet columns added successfully.")
        else:
            logger.info("Wallet columns already exist in AIAgent table.")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding wallet columns: {e}")
        sys.exit(1)

def update_existing_agents():
    """Create wallet addresses for existing AI Agents"""
    try:
        # Get all agents without wallet addresses
        agents = session.query(AIAgent).filter(AIAgent.wallet_address.is_(None)).all()
        
        if not agents:
            logger.info("No agents found without wallet addresses.")
            return
        
        logger.info(f"Found {len(agents)} agents without wallet addresses.")
        
        # Create wallet for each agent
        for agent in agents:
            try:
                network = agent.wallet_network or 'mainnet'
                wallet_address = CryptoWalletManager.create_agent_wallet(network=network)
                
                agent.wallet_address = wallet_address
                agent.wallet_created_date = datetime.utcnow()
                
                logger.info(f"Created {network} wallet for agent {agent.id} ({agent.name}): {wallet_address}")
            except Exception as e:
                logger.warning(f"Error creating wallet for agent {agent.id}: {e}")
                continue
        
        session.commit()
        logger.info("Wallet migration completed successfully.")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating agents with wallets: {e}")
        sys.exit(1)

def run_migration():
    """Run the database migration to add wallet functionality to AI Agents"""
    try:
        with app.app_context():
            add_wallet_columns()
            update_existing_agents()
        
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()