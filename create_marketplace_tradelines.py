#!/usr/bin/env python3
"""
Creates diverse tradelines for the marketplace that are available for both rental and sale.
This script provides a wide range of tradelines with different characteristics to test the marketplace.
"""

from app import app, db
from models import User, Tradeline, CreditProfile
from datetime import datetime, timedelta
import random

def create_marketplace_tradelines():
    """
    Creates diverse tradelines in the marketplace for users to buy or rent.
    """
    print("Creating diverse marketplace tradelines...")
    
    with app.app_context():
        # Find the admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Admin user not found. Cannot create tradelines.")
            return
        
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
        
        # Define marketplace tradelines with varied characteristics
        marketplace_tradelines = [
            # Premium tradelines (high credit limits, low interest rates)
            {
                "name": "Elite Platinum Card",
                "credit_limit": 50000.0,
                "available_limit": 50000.0,
                "interest_rate": 12.99,
                "issuer": "Premium Financial Group",
                "account_type": "Credit Card",
                "description": "Exclusive platinum card with exceptional benefits and a high credit limit. Perfect for high-net-worth individuals.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 15000.0,
                "rental_price": 1500.0,
                "rental_duration": 3  # 3 months
            },
            {
                "name": "Sapphire Business Line",
                "credit_limit": 75000.0,
                "available_limit": 75000.0,
                "interest_rate": 9.99,
                "issuer": "Corporate Financial Services",
                "account_type": "Business Line of Credit",
                "description": "Premium business line of credit for established businesses with significant credit needs.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 22500.0,
                "rental_price": 2250.0,
                "rental_duration": 6  # 6 months
            },
            
            # Mid-tier tradelines (moderate credit limits, competitive interest rates)
            {
                "name": "Gold Rewards Plus",
                "credit_limit": 15000.0,
                "available_limit": 15000.0,
                "interest_rate": 15.99,
                "issuer": "National Bank",
                "account_type": "Credit Card",
                "description": "Gold-tier rewards card with great travel and dining benefits. 3% cashback on select categories.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 4500.0,
                "rental_price": 450.0,
                "rental_duration": 1  # 1 month
            },
            {
                "name": "Merchant Credit Line",
                "credit_limit": 25000.0,
                "available_limit": 25000.0,
                "interest_rate": 12.49,
                "issuer": "Commerce Financial",
                "account_type": "Line of Credit",
                "description": "Flexible line of credit perfect for small business owners and retail operations.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 7500.0,
                "rental_price": 750.0,
                "rental_duration": 3  # 3 months
            },
            
            # Budget-friendly tradelines (lower credit limits, accessible pricing)
            {
                "name": "Everyday Essentials Card",
                "credit_limit": 5000.0,
                "available_limit": 5000.0,
                "interest_rate": 18.99,
                "issuer": "Community Credit Union",
                "account_type": "Credit Card",
                "description": "Perfect starter card with reasonable terms and no annual fee. 1% cashback on all purchases.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 1500.0,
                "rental_price": 150.0,
                "rental_duration": 1  # 1 month
            },
            {
                "name": "Student Builder Card",
                "credit_limit": 2500.0,
                "available_limit": 2500.0,
                "interest_rate": 17.49,
                "issuer": "Education Financial",
                "account_type": "Student Credit Card",
                "description": "Designed specifically for students looking to build credit history with responsible use.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 750.0,
                "rental_price": 75.0,
                "rental_duration": 1  # 1 month
            },
            
            # Specialized tradelines (unique benefits or purposes)
            {
                "name": "Travel Elite Card",
                "credit_limit": 20000.0,
                "available_limit": 20000.0,
                "interest_rate": 16.99,
                "issuer": "Global Travel Bank",
                "account_type": "Travel Credit Card",
                "description": "Premium travel card with airport lounge access, travel insurance, and no foreign transaction fees.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 6000.0,
                "rental_price": 600.0,
                "rental_duration": 3  # 3 months
            },
            {
                "name": "Cashback Max Card",
                "credit_limit": 10000.0,
                "available_limit": 10000.0,
                "interest_rate": 16.49,
                "issuer": "Rewards Financial",
                "account_type": "Cashback Credit Card",
                "description": "Maximize your returns with 5% cashback in rotating categories and 2% on everything else.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 3000.0,
                "rental_price": 300.0,
                "rental_duration": 1  # 1 month
            },
            
            # Long-term rental options (lower monthly cost, longer commitment)
            {
                "name": "Signature Credit Line - 12 Month",
                "credit_limit": 30000.0,
                "available_limit": 30000.0,
                "interest_rate": 14.99,
                "issuer": "Long-Term Financial",
                "account_type": "Line of Credit",
                "description": "Premium credit line available for a 12-month rental period. Great value for long-term credit needs.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 9000.0,
                "rental_price": 750.0,
                "rental_duration": 12  # 12 months
            },
            {
                "name": "Premium Card - 9 Month",
                "credit_limit": 18000.0,
                "available_limit": 18000.0,
                "interest_rate": 15.99,
                "issuer": "Extended Credit Bank",
                "account_type": "Credit Card",
                "description": "Premium card available for a 9-month rental. Ideal for extended credit improvement projects.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 5400.0,
                "rental_price": 500.0,
                "rental_duration": 9  # 9 months
            }
        ]
        
        created_count = 0
        for tradeline_data in marketplace_tradelines:
            # Check if a similar tradeline already exists
            existing = Tradeline.query.filter_by(
                owner_id=admin.id, 
                name=tradeline_data["name"]
            ).first()
            
            if existing:
                print(f"Tradeline '{tradeline_data['name']}' already exists, skipping.")
                continue
            
            # Create the tradeline
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
                is_for_sale=tradeline_data["is_for_sale"],
                is_for_rent=tradeline_data["is_for_rent"],
                sale_price=tradeline_data["sale_price"],
                rental_price=tradeline_data["rental_price"],
                rental_duration=tradeline_data.get("rental_duration", 1)
            )
            db.session.add(tradeline)
            created_count += 1
        
        # Commit all changes
        db.session.commit()
        print(f"Created {created_count} new marketplace tradelines for sale and rental.")

# Run the script if executed directly
if __name__ == "__main__":
    create_marketplace_tradelines()