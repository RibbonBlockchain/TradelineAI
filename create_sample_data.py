import sys
import os
from datetime import datetime
import random

# Set the application directory to the current directory
sys.path.insert(0, os.path.abspath('.'))

from app import app, db
from models import User, Tradeline, CreditProfile
from werkzeug.security import generate_password_hash

def create_sample_tradeline():
    with app.app_context():
        # Check if we already have a user
        user = User.query.first()
        
        if not user:
            print("No user found. Please register a user first.")
            return
            
        # Check if the user already has tradelines
        existing_tradelines = Tradeline.query.filter_by(owner_id=user.id).count()
        
        if existing_tradelines > 0:
            print(f"User already has {existing_tradelines} tradelines.")
            return
            
        # Create a sample tradeline for the user
        tradeline = Tradeline(
            owner_id=user.id,
            name="Premium Visa Card",
            credit_limit=15000.0,
            available_limit=12500.0,
            interest_rate=14.99,
            issuer="Capital Bank",
            account_type="Credit Card",
            created_date=datetime.utcnow(),
            is_active=True,
            is_for_sale=True,
            is_for_rent=True,
            sale_price=5000.0,
            rental_price=500.0
        )
        
        db.session.add(tradeline)
        
        # Make sure the user has a credit profile
        if not user.credit_profile:
            credit_profile = CreditProfile(
                user_id=user.id,
                identity_number="XXX-XX-1234",  # Masked for privacy
                credit_score=720,
                verified=True,
                verification_date=datetime.utcnow(),
                available_credit=30000.0,
                total_credit_limit=50000.0
            )
            db.session.add(credit_profile)
        
        db.session.commit()
        print(f"Created sample tradeline '{tradeline.name}' for user '{user.username}'")

def create_default_tradelines():
    """Create default tradelines in the marketplace for new users to purchase"""
    with app.app_context():
        # Check if we already have a marketplace user
        marketplace_user = User.query.filter_by(username='marketplace').first()
        
        if not marketplace_user:
            # Create a marketplace user
            marketplace_user = User(
                username='marketplace',
                email='marketplace@tradeline-system.com',
                password_hash=generate_password_hash('marketplace-secure-pw'),
                first_name='System',
                last_name='Marketplace',
                date_joined=datetime.utcnow(),
                is_active=True
            )
            db.session.add(marketplace_user)
            db.session.commit()
            
            # Create a credit profile for the marketplace user
            credit_profile = CreditProfile(
                user_id=marketplace_user.id,
                identity_number="SYSTEM-MARKETPLACE",
                credit_score=850,  # Perfect credit score
                verified=True,
                verification_date=datetime.utcnow(),
                available_credit=10000000.0,  # $10 million
                total_credit_limit=10000000.0  # $10 million
            )
            db.session.add(credit_profile)
            db.session.commit()
            
            print(f"Created marketplace user with ID {marketplace_user.id}")
        
        # Check if we already have default tradelines
        existing_tradelines = Tradeline.query.filter_by(owner_id=marketplace_user.id).count()
        
        if existing_tradelines > 0:
            print(f"Marketplace already has {existing_tradelines} default tradelines.")
            return
        
        # Create default tradelines with different characteristics for different use cases
        
        # Credit card tradelines (different tiers and purposes)
        credit_cards = [
            {
                "name": "Starter Credit Card",
                "credit_limit": 2000.0,
                "available_limit": 2000.0,
                "interest_rate": 19.99,
                "issuer": "First Bank",
                "account_type": "Credit Card",
                "sale_price": 500.0,
                "rental_price": 50.0,
                "description": "Perfect for beginners with low credit needs"
            },
            {
                "name": "Everyday Rewards Card",
                "credit_limit": 5000.0,
                "available_limit": 5000.0,
                "interest_rate": 16.99,
                "issuer": "Everyday Bank",
                "account_type": "Credit Card",
                "sale_price": 1500.0,
                "rental_price": 150.0,
                "description": "Great for everyday purchases with cashback rewards"
            },
            {
                "name": "Premium Travel Card",
                "credit_limit": 10000.0,
                "available_limit": 10000.0,
                "interest_rate": 17.99,
                "issuer": "World Bank",
                "account_type": "Credit Card",
                "sale_price": 3000.0,
                "rental_price": 300.0,
                "description": "Designed for travel expenses with travel insurance and perks"
            },
            {
                "name": "Business Expense Card",
                "credit_limit": 15000.0,
                "available_limit": 15000.0,
                "interest_rate": 15.99,
                "issuer": "Business Capital Bank",
                "account_type": "Credit Card",
                "sale_price": 4500.0,
                "rental_price": 450.0,
                "description": "Ideal for business expenses with detailed reporting features"
            },
            {
                "name": "Luxury Platinum Card",
                "credit_limit": 25000.0,
                "available_limit": 25000.0,
                "interest_rate": 14.99,
                "issuer": "Prestige Financial",
                "account_type": "Credit Card",
                "sale_price": 7500.0,
                "rental_price": 750.0,
                "description": "Premium card with concierge services and high spending limits"
            }
        ]
        
        # Line of credit tradelines (different purposes)
        lines_of_credit = [
            {
                "name": "Personal Line of Credit",
                "credit_limit": 10000.0,
                "available_limit": 10000.0,
                "interest_rate": 9.99,
                "issuer": "Personal Finance Co.",
                "account_type": "Line of Credit",
                "sale_price": 3000.0,
                "rental_price": 300.0,
                "description": "Flexible credit line for personal expenses"
            },
            {
                "name": "Home Improvement Credit Line",
                "credit_limit": 20000.0,
                "available_limit": 20000.0,
                "interest_rate": 8.99,
                "issuer": "Home Bank",
                "account_type": "Line of Credit",
                "sale_price": 6000.0,
                "rental_price": 600.0,
                "description": "Specifically for home improvement and renovation expenses"
            },
            {
                "name": "Investment Credit Line",
                "credit_limit": 50000.0,
                "available_limit": 50000.0,
                "interest_rate": 7.99,
                "issuer": "Investment Capital Group",
                "account_type": "Line of Credit",
                "sale_price": 15000.0,
                "rental_price": 1500.0,
                "description": "For investment opportunities with lower interest rates"
            },
            {
                "name": "Business Expansion Credit",
                "credit_limit": 100000.0,
                "available_limit": 100000.0,
                "interest_rate": 7.49,
                "issuer": "Enterprise Financial",
                "account_type": "Line of Credit",
                "sale_price": 30000.0,
                "rental_price": 3000.0,
                "description": "Designed for business expansion and major investments"
            }
        ]
        
        # Business credit card tradelines (business-specific)
        business_cards = [
            {
                "name": "Small Business Card",
                "credit_limit": 10000.0,
                "available_limit": 10000.0,
                "interest_rate": 16.49,
                "issuer": "SMB Financial",
                "account_type": "Business Credit Card",
                "sale_price": 3000.0,
                "rental_price": 300.0,
                "description": "For small business expenses with category-based rewards"
            },
            {
                "name": "Corporate Expense Card",
                "credit_limit": 30000.0,
                "available_limit": 30000.0,
                "interest_rate": 15.49,
                "issuer": "Corporate Bank",
                "account_type": "Business Credit Card",
                "sale_price": 9000.0,
                "rental_price": 900.0,
                "description": "For corporate expenses with multi-user management"
            },
            {
                "name": "E-commerce Business Card",
                "credit_limit": 20000.0,
                "available_limit": 20000.0,
                "interest_rate": 15.99,
                "issuer": "Digital Commerce Bank",
                "account_type": "Business Credit Card",
                "sale_price": 6000.0,
                "rental_price": 600.0,
                "description": "Optimized for online business expenses and digital subscriptions"
            }
        ]
        
        # Specialty tradelines (specific uses)
        specialty_cards = [
            {
                "name": "Retail Shopping Card",
                "credit_limit": 8000.0,
                "available_limit": 8000.0,
                "interest_rate": 18.99,
                "issuer": "Retail Finance Group",
                "account_type": "Retail Credit Card",
                "sale_price": 2400.0,
                "rental_price": 240.0,
                "description": "Optimized for retail purchases with store-specific rewards"
            },
            {
                "name": "Entertainment & Dining Card",
                "credit_limit": 6000.0,
                "available_limit": 6000.0,
                "interest_rate": 17.99,
                "issuer": "Lifestyle Bank",
                "account_type": "Entertainment Credit Card",
                "sale_price": 1800.0,
                "rental_price": 180.0,
                "description": "Perfect for entertainment, dining, and leisure spending"
            },
            {
                "name": "Utility & Bill Payment Card",
                "credit_limit": 5000.0,
                "available_limit": 5000.0,
                "interest_rate": 16.49,
                "issuer": "Everyday Finance",
                "account_type": "Bill Payment Card",
                "sale_price": 1500.0,
                "rental_price": 150.0,
                "description": "Specialized for utility bills and subscription payments"
            }
        ]
        
        # Combine all tradeline types
        all_tradelines = credit_cards + lines_of_credit + business_cards + specialty_cards
        
        # Add all tradelines to the database
        for tl_data in all_tradelines:
            tradeline = Tradeline(
                owner_id=marketplace_user.id,
                name=tl_data["name"],
                credit_limit=tl_data["credit_limit"],
                available_limit=tl_data["available_limit"],
                interest_rate=tl_data["interest_rate"],
                issuer=tl_data["issuer"],
                account_type=tl_data["account_type"],
                created_date=datetime.utcnow(),
                is_active=True,
                is_for_sale=True,
                is_for_rent=True,
                sale_price=tl_data["sale_price"],
                rental_price=tl_data["rental_price"],
                description=tl_data["description"]
            )
            db.session.add(tradeline)
        
        db.session.commit()
        print(f"Created {len(all_tradelines)} default tradelines in the marketplace")

if __name__ == "__main__":
    # Uncomment the function you want to run
    # create_sample_tradeline()
    create_default_tradelines()