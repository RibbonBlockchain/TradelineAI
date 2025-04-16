"""
Migration script to add accessibility preferences column to User table.
"""

import json
from app import app, db
from models import User
from modules.accessibility import AccessibilityPreferences

def add_accessibility_column():
    """Add accessibility_preferences column to the User table"""
    with app.app_context():
        # Check if we need to add the column (should already be there from models.py update)
        try:
            # Try to access the column to see if it exists
            users = User.query.limit(1).all()
            if users and hasattr(users[0], 'accessibility_preferences'):
                print("Column 'accessibility_preferences' already exists in User table")
            else:
                raise Exception("Column does not exist")
        except Exception as e:
            print(f"Error checking column: {str(e)}")
            # Column doesn't exist or other error, try to add it through SQL (just in case)
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text('ALTER TABLE user ADD COLUMN accessibility_preferences TEXT'))
                    conn.commit()
                print("Added 'accessibility_preferences' column to User table")
            except Exception as e:
                print(f"Error adding column: {str(e)}")
                print("The column may already exist or there was an error adding it.")
        
        # Set default accessibility preferences for all users
        try:
            # Default preferences dictionary
            default_prefs = {
                'high_contrast_mode': False,
                'large_text_mode': False,
                'screen_reader_optimized': False,
                'reduce_animations': False,
                'keyboard_navigation': False,
                'auto_announce_changes': False
            }
            
            # Update all users with default preferences
            users = User.query.all()
            for user in users:
                if not user.accessibility_preferences:
                    user.accessibility_preferences = json.dumps(default_prefs)
            
            db.session.commit()
            print(f"Set default accessibility preferences for {len(users)} users")
        except Exception as e:
            db.session.rollback()
            print(f"Error setting default preferences: {str(e)}")

if __name__ == "__main__":
    add_accessibility_column()
    print("Accessibility migration completed")