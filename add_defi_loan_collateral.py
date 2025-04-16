"""
Migration script to add collateral fields to the DefiLoan table.
This adds:
1. has_collateral column (Boolean)
2. collateral_allocation_id column (Foreign Key)
3. collateral_amount column (Float)
4. collateral_liquidated column (Boolean)
5. liquidation_date column (DateTime)
"""
from sqlalchemy import Column, Boolean, Integer, Float, DateTime, ForeignKey, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text
from datetime import datetime
from app import db, app

def add_collateral_columns():
    """Add collateral columns to the DefiLoan table"""
    with app.app_context():
        inspector = inspect(db.engine)
        existing_columns = [column['name'] for column in inspector.get_columns('defi_loan')]
        
        if 'has_collateral' in existing_columns:
            print("Collateral columns already exist in DefiLoan table. Skipping migration.")
            return False
        
        print("Adding collateral columns to DefiLoan table...")
        
        # Using SQLAlchemy session with raw SQL via text()
        with db.engine.connect() as conn:
            # Add has_collateral column
            conn.execute(text("ALTER TABLE defi_loan ADD COLUMN has_collateral BOOLEAN DEFAULT 0"))
            
            # Add collateral_allocation_id column
            conn.execute(text("ALTER TABLE defi_loan ADD COLUMN collateral_allocation_id INTEGER REFERENCES ai_agent_allocation(id)"))
            
            # Add collateral_amount column
            conn.execute(text("ALTER TABLE defi_loan ADD COLUMN collateral_amount FLOAT"))
            
            # Add collateral_liquidated column 
            conn.execute(text("ALTER TABLE defi_loan ADD COLUMN collateral_liquidated BOOLEAN DEFAULT 0"))
            
            # Add liquidation_date column
            conn.execute(text("ALTER TABLE defi_loan ADD COLUMN liquidation_date DATETIME"))
            
            conn.commit()
        
        print("Migration completed successfully!")
        return True

def run_migration():
    """Run the database migration to add collateral functionality to DefiLoans"""
    try:
        result = add_collateral_columns()
        
        if result:
            print("Successfully added collateral fields to DefiLoan table.")
        else:
            print("No changes were needed.")
        
        return True
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    run_migration()