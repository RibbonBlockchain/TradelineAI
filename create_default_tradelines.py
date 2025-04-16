#!/usr/bin/env python3
"""
Creates default tradelines for rental in the marketplace.
Adds options for once-off rental, 3-month, 6-month, and 12-month rentals.
"""

from app import app, db
from models import User, Tradeline, CreditProfile
from datetime import datetime, timedelta

def create_rental_tradelines():
    """
    Creates default tradelines for rental with varying durations.
    """
    print("Creating default rental tradelines...")
    
    # Find the admin user
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Admin user not found. Cannot create tradelines.")
        return
    
    # Check if admin already has tradelines
    existing_tradelines = Tradeline.query.filter_by(owner_id=admin.id).all()
    
    # Get or create admin's credit profile
    credit_profile = CreditProfile.query.filter_by(user_id=admin.id).first()
    if not credit_profile:
        credit_profile = CreditProfile(
            user_id=admin.id,
            credit_score=780,
            verified=True,
            verification_date=datetime.utcnow(),
            available_credit=50000.0,
            total_credit_limit=75000.0
        )
        db.session.add(credit_profile)
        db.session.flush()
        print("Created credit profile for admin")
    
    # Define rental tradeline options
    rental_tradelines = [
        {
            "name": "Premium Credit Card - Once-off Rental",
            "credit_limit": 5000.0,
            "available_limit": 5000.0,
            "interest_rate": 18.99,
            "issuer": "Global Bank",
            "account_type": "Credit Card",
            "description": "Premium credit card tradeline available for a one-time rental. Perfect for boosting your credit score temporarily.",
            "is_for_rent": True,
            "rental_price": 299.0,
            "rental_duration": 1  # One month
        },
        {
            "name": "Gold Card - 3 Month Rental",
            "credit_limit": 7500.0,
            "available_limit": 7500.0,
            "interest_rate": 17.5,
            "issuer": "National Bank",
            "account_type": "Credit Card",
            "description": "Gold credit card tradeline with a generous credit limit. Available for a 3-month rental period.",
            "is_for_rent": True,
            "rental_price": 799.0,
            "rental_duration": 3  # Three months
        },
        {
            "name": "Platinum Line of Credit - 6 Month Rental",
            "credit_limit": 12000.0,
            "available_limit": 12000.0,
            "interest_rate": 14.99,
            "issuer": "Premier Financial",
            "account_type": "Line of Credit",
            "description": "Platinum line of credit tradeline with a substantial limit. Rent for 6 months for sustained credit improvement.",
            "is_for_rent": True,
            "rental_price": 1499.0,
            "rental_duration": 6  # Six months
        },
        {
            "name": "Titanium Credit Card - 9 Month Rental",
            "credit_limit": 15000.0,
            "available_limit": 15000.0,
            "interest_rate": 15.75,
            "issuer": "Global Financial Group",
            "account_type": "Credit Card",
            "description": "Titanium credit card tradeline with an exceptional credit limit. Rent for 9 months for extended credit score benefits.",
            "is_for_rent": True,
            "rental_price": 1999.0,
            "rental_duration": 9  # Nine months
        },
        {
            "name": "Elite Rewards Card - 12 Month Rental",
            "credit_limit": 20000.0,
            "available_limit": 20000.0,
            "interest_rate": 16.25,
            "issuer": "International Finance",
            "account_type": "Credit Card",
            "description": "Elite rewards credit card tradeline with a premium limit. Annual rental for maximum credit score impact.",
            "is_for_rent": True,
            "rental_price": 2799.0,
            "rental_duration": 12  # Twelve months
        },
        {
            "name": "Business Line of Credit - For Sale",
            "credit_limit": 25000.0,
            "available_limit": 25000.0,
            "interest_rate": 12.75,
            "issuer": "Commerce Bank",
            "account_type": "Business Line",
            "description": "Business line of credit tradeline with excellent terms. Available for permanent purchase.",
            "is_for_sale": True,
            "sale_price": 5999.0
        }
    ]
    
    # Create tradelines
    created_count = 0
    for tradeline_data in rental_tradelines:
        # Check if a similar tradeline already exists
        existing = False
        for existing_tradeline in existing_tradelines:
            if existing_tradeline.name == tradeline_data["name"]:
                existing = True
                break
        
        if not existing:
            tradeline = Tradeline(
                owner_id=admin.id,
                name=tradeline_data["name"],
                credit_limit=tradeline_data["credit_limit"],
                available_limit=tradeline_data["available_limit"],
                interest_rate=tradeline_data["interest_rate"],
                issuer=tradeline_data["issuer"],
                account_type=tradeline_data["account_type"],
                description=tradeline_data["description"],
                created_date=datetime.utcnow(),
                is_active=True,
                is_for_sale=tradeline_data.get("is_for_sale", False),
                is_for_rent=tradeline_data.get("is_for_rent", False),
                sale_price=tradeline_data.get("sale_price", None),
                rental_price=tradeline_data.get("rental_price", None),
                rental_duration=tradeline_data.get("rental_duration", 1)
            )
            db.session.add(tradeline)
            created_count += 1
    
    # Commit to the database
    db.session.commit()
    print(f"Created {created_count} new tradelines for rental/sale in the marketplace.")

# Run the script if executed directly
if __name__ == "__main__":
    with app.app_context():
        create_rental_tradelines()