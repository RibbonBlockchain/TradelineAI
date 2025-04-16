import datetime
from app import app, db
from models import AIAgent
import sqlalchemy as sa

def run():
    """
    Adds wallet_last_refresh column to AIAgent table
    """
    with app.app_context():
        print("Adding wallet_last_refresh column to AIAgent table...")
        # Check if column exists
        inspector = sa.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('ai_agent')]
        
        if 'wallet_last_refresh' not in columns:
            # Add the column
            with db.engine.begin() as conn:
                conn.execute(sa.text('ALTER TABLE ai_agent ADD COLUMN wallet_last_refresh TIMESTAMP'))
                print("Column added successfully!")
            
            # Update existing records with current time
            now = datetime.datetime.utcnow()
            AIAgent.query.update({AIAgent.wallet_last_refresh: now})
            db.session.commit()
            print(f"Updated {AIAgent.query.count()} existing records with current timestamp")
        else:
            print("Column wallet_last_refresh already exists, skipping...")
        
        print("Migration complete!")

if __name__ == "__main__":
    run()