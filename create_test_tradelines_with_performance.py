#!/usr/bin/env python3
"""
Creates test tradelines with performance data for the marketplace.
This allows users to test the system with tradelines that have performance metrics.
"""

from app import app, db
from models import User, Tradeline, CreditProfile, TradelinePerformance
from datetime import datetime, timedelta
import random

def create_test_tradelines_with_performance():
    """
    Creates test tradelines with performance data in the marketplace.
    """
    print("Creating test tradelines with performance data...")
    
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
        
        # Define test tradelines with varied characteristics
        test_tradelines = [
            {
                "name": "Test Basic Credit Card",
                "credit_limit": 3500.0,
                "available_limit": 2800.0,
                "interest_rate": 19.99,
                "issuer": "Test Bank",
                "account_type": "Credit Card",
                "description": "A basic credit card for testing the tradeline performance visualization features.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 1200.0,
                "rental_price": 120.0,
                "performance": {
                    "balance_range": (500, 800),
                    "transaction_count_range": (10, 20),
                    "risk_score_range": (20, 40)
                }
            },
            {
                "name": "Test Gold Rewards Card",
                "credit_limit": 8000.0,
                "available_limit": 5500.0,
                "interest_rate": 17.99,
                "issuer": "Test Rewards Bank",
                "account_type": "Credit Card",
                "description": "A gold rewards card for testing performance charts with higher utilization.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 2500.0,
                "rental_price": 250.0,
                "performance": {
                    "balance_range": (2000, 2500),
                    "transaction_count_range": (15, 25),
                    "risk_score_range": (30, 50)
                }
            },
            {
                "name": "Test Business Line of Credit",
                "credit_limit": 15000.0,
                "available_limit": 9000.0,
                "interest_rate": 14.99,
                "issuer": "Test Business Finance",
                "account_type": "Line of Credit",
                "description": "A business line of credit for testing complex performance metrics and visualization.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 4500.0,
                "rental_price": 450.0,
                "performance": {
                    "balance_range": (5000, 6000),
                    "transaction_count_range": (25, 40),
                    "risk_score_range": (40, 60)
                }
            },
            {
                "name": "Test Platinum Rewards Card",
                "credit_limit": 12000.0,
                "available_limit": 8400.0,
                "interest_rate": 16.49,
                "issuer": "Test Premium Bank",
                "account_type": "Credit Card",
                "description": "A platinum rewards card for testing premium performance visualizations.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 3600.0,
                "rental_price": 360.0,
                "performance": {
                    "balance_range": (3000, 3600),
                    "transaction_count_range": (20, 30),
                    "risk_score_range": (25, 45)
                }
            },
            {
                "name": "Test High-Risk Credit Card",
                "credit_limit": 5000.0,
                "available_limit": 1500.0,
                "interest_rate": 22.99,
                "issuer": "Test Risk Finance",
                "account_type": "Credit Card",
                "description": "A high-risk credit card for testing poor performance metrics visualization.",
                "is_for_sale": True,
                "is_for_rent": True,
                "sale_price": 1500.0,
                "rental_price": 150.0,
                "performance": {
                    "balance_range": (3200, 3500),
                    "transaction_count_range": (5, 10),
                    "risk_score_range": (70, 85)
                }
            }
        ]
        
        created_count = 0
        for tradeline_data in test_tradelines:
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
                rental_price=tradeline_data["rental_price"]
            )
            db.session.add(tradeline)
            db.session.flush()  # Flush to get the ID
            created_count += 1
            
            # Generate performance data for this tradeline
            print(f"Generating performance data for '{tradeline_data['name']}'")
            generate_performance_data(
                tradeline.id, 
                tradeline_data["credit_limit"],
                tradeline_data["performance"]
            )
        
        # Commit all changes
        db.session.commit()
        print(f"Created {created_count} new test tradelines with performance data.")

def generate_performance_data(tradeline_id, credit_limit, performance_params, days_back=90):
    """
    Generate performance data for a tradeline
    
    Args:
        tradeline_id: The ID of the tradeline
        credit_limit: The credit limit of the tradeline
        performance_params: Dictionary with balance_range, transaction_count_range, risk_score_range
        days_back: Number of days of history to generate
    """
    records_created = 0
    
    # Start with current date and work backwards
    for days_ago in range(0, days_back + 1):
        record_date = datetime.utcnow() - timedelta(days=days_ago)
        
        # Add some random variation based on time
        progress_factor = 1 - (days_ago / days_back)
        
        # Calculate metrics based on parameters with random variation
        min_balance, max_balance = performance_params["balance_range"]
        base_balance = min_balance + (max_balance - min_balance) * progress_factor
        # Add some random noise (±10%)
        balance = base_balance * random.uniform(0.9, 1.1)
        
        # Calculate available credit and utilization rate
        available_credit = credit_limit - balance
        utilization_rate = balance / credit_limit if credit_limit > 0 else 0
        
        # Transaction metrics
        min_txn, max_txn = performance_params["transaction_count_range"]
        base_txn_count = min_txn + (max_txn - min_txn) * progress_factor
        transaction_count = max(0, int(base_txn_count * random.uniform(0.8, 1.2)))
        
        # Calculate transaction volume (average $50-150 per transaction)
        avg_transaction = random.uniform(50, 150)
        transaction_volume = transaction_count * avg_transaction
        
        # Repayment metrics
        # Assume about 10-20% of the balance is paid each month
        repayment_percent = random.uniform(0.1, 0.2)
        total_repayments = balance * repayment_percent
        
        # On-time vs late payments
        total_payments = max(1, int(transaction_count * 0.3))  # About 30% of transactions result in payments
        on_time_ratio = random.uniform(0.7, 0.95)  # 70-95% are on time
        repayments_on_time = int(total_payments * on_time_ratio)
        repayments_late = total_payments - repayments_on_time
        
        # Payment ratio
        payment_ratio = total_repayments / balance if balance > 0 else 1.0
        
        # Risk score
        min_risk, max_risk = performance_params["risk_score_range"]
        base_risk = min_risk + (max_risk - min_risk) * (1 - progress_factor)  # Risk decreases over time
        risk_score = base_risk * random.uniform(0.9, 1.1)  # Add some noise
        
        # Days delinquent (based on risk score)
        days_delinquent = int((risk_score / 100) * 30 * random.uniform(0.8, 1.2))
        
        # Interest accrued (assuming 12-24% annual interest rate)
        annual_rate = random.uniform(0.12, 0.24)
        interest_accrued = (balance * (annual_rate / 365)) * 30  # Monthly interest
        
        # Create the performance record
        performance = TradelinePerformance(
            tradeline_id=tradeline_id,
            record_date=record_date,
            current_balance=balance,
            available_credit=available_credit,
            utilization_rate=utilization_rate,
            transaction_count=transaction_count,
            transaction_volume=transaction_volume,
            avg_transaction_amount=avg_transaction,
            total_repayments=total_repayments,
            repayments_on_time=repayments_on_time,
            repayments_late=repayments_late,
            payment_ratio=payment_ratio,
            risk_score=risk_score,
            days_delinquent=days_delinquent,
            interest_accrued=interest_accrued
        )
        
        db.session.add(performance)
        records_created += 1
    
    print(f"Created {records_created} performance records for tradeline ID {tradeline_id}")
    return records_created

# Run the script if executed directly
if __name__ == "__main__":
    create_test_tradelines_with_performance()