"""
Create a default user for the application.
This script adds a default admin user to the database.
"""
from datetime import datetime
from app import app, db
from models import User, CreditProfile

def create_default_user():
    """Create a default admin user if no users exist."""
    with app.app_context():
        # Check if any users exist
        user_count = User.query.count()
        
        if user_count == 0:
            print("Creating default admin user...")
            
            # Create a new admin user
            default_user = User(
                username="admin",
                email="admin@example.com",
                first_name="Admin",
                last_name="User",
                date_joined=datetime.utcnow(),
                is_active=True
            )
            
            # Set password
            default_user.set_password("admin123")
            
            # Add user to database
            db.session.add(default_user)
            db.session.flush()  # Flush to get the user ID
            
            # Create a credit profile for the user
            credit_profile = CreditProfile(
                user_id=default_user.id,
                credit_score=750,
                verified=True,
                verification_date=datetime.utcnow(),
                verification_source="system",
                address_line1="123 Main Street",
                city="Anytown",
                state="CA",
                zip_code="90210",
                dob="1980-01-01"
            )
            
            # Add credit profile to database
            db.session.add(credit_profile)
            
            # Commit changes
            db.session.commit()
            
            print(f"Default user created successfully with username 'admin' and password 'admin123'")
            return True
        else:
            print("Users already exist in the database, skipping default user creation.")
            return False

if __name__ == "__main__":
    create_default_user()