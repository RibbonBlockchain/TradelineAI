#!/usr/bin/env python3
"""
Script to generate performance records for existing tradelines.
This will create a historical record of tradeline performance
for visualization and analysis.
"""

from datetime import datetime, timedelta
from app import app, db
from models import Tradeline, TradelinePerformance
import random

def generate_historical_performance(tradeline_id, days_back=90):
    """
    Generate historical performance records for a tradeline
    going back a specified number of days.
    
    Args:
        tradeline_id: The ID of the tradeline to generate records for
        days_back: Number of days of history to generate (default 90)
    
    Returns:
        List of created performance records
    """
    with app.app_context():
        # Get the current performance as a baseline
        current_performance = TradelinePerformance.record_tradeline_performance(tradeline_id)
        
        if not current_performance:
            print(f"No current performance data available for tradeline {tradeline_id}")
            return []
        
        created_records = [current_performance]
        
        # Generate historical records with slight variations
        for days_ago in range(1, days_back + 1):
            record_date = datetime.utcnow() - timedelta(days=days_ago)
            
            # Create variations of metrics
            # For more realistic data, we apply random variations to each metric
            # that decrease as we go further back in time (gradual growth model)
            progress_factor = 1 - (days_ago / days_back)
            
            # Balance history - generally increasing over time
            balance_factor = max(0.5, progress_factor)
            balance = current_performance.current_balance * balance_factor
            
            # Credit utilization based on balance
            credit_limit = current_performance.available_credit + current_performance.current_balance
            available_credit = credit_limit - balance
            utilization_rate = balance / credit_limit if credit_limit > 0 else 0
            
            # Transaction history - fewer transactions in the past
            transaction_factor = max(0.3, progress_factor)
            transaction_count = max(0, int(current_performance.transaction_count * transaction_factor))
            transaction_volume = current_performance.transaction_volume * transaction_factor
            
            # Average amount stays relatively consistent with small variations
            avg_transaction_amount = current_performance.avg_transaction_amount * (0.9 + 0.2 * random.random())
            
            # Repayment history
            repayment_factor = max(0.4, progress_factor)
            total_repayments = balance * 0.1 * (0.8 + 0.4 * random.random())  # Approximately 10% of balance with variations
            repayments_on_time = max(0, int(current_performance.repayments_on_time * repayment_factor))
            repayments_late = max(0, int(current_performance.repayments_late * repayment_factor))
            
            # Payment ratio (higher is better)
            payment_ratio = total_repayments / balance if balance > 0 else 1.0
            
            # Risk metrics - risk generally decreases over time (improvement)
            risk_variation = random.uniform(-5, 10)  # Some random variation
            risk_score = max(0, min(100, current_performance.risk_score + risk_variation * (1 - progress_factor)))
            
            days_delinquent = max(0, int(current_performance.days_delinquent * (1 - progress_factor) * random.uniform(0.8, 1.2)))
            
            # Interest accrued based on balance
            interest_accrued = (balance * (0.12 / 365)) * 30  # Assume annual 12% interest rate
            
            # Create the historical record
            historical_record = TradelinePerformance(
                tradeline_id=tradeline_id,
                record_date=record_date,
                current_balance=balance,
                available_credit=available_credit,
                utilization_rate=utilization_rate,
                transaction_count=transaction_count,
                transaction_volume=transaction_volume,
                avg_transaction_amount=avg_transaction_amount,
                total_repayments=total_repayments,
                repayments_on_time=repayments_on_time,
                repayments_late=repayments_late,
                payment_ratio=payment_ratio,
                risk_score=risk_score,
                days_delinquent=days_delinquent,
                interest_accrued=interest_accrued
            )
            
            db.session.add(historical_record)
            created_records.append(historical_record)
        
        db.session.commit()
        return created_records

def generate_all_tradeline_performance_records(days_back=90):
    """
    Generate performance records for all tradelines in the system.
    
    Args:
        days_back: Number of days of history to generate (default 90)
    
    Returns:
        Dictionary with tradeline IDs as keys and number of records created as values
    """
    with app.app_context():
        results = {}
        tradelines = Tradeline.query.all()
        
        total_tradelines = len(tradelines)
        processed = 0
        
        for tradeline in tradelines:
            print(f"Generating performance records for tradeline {tradeline.id} ({processed+1}/{total_tradelines})")
            records = generate_historical_performance(tradeline.id, days_back)
            results[tradeline.id] = len(records)
            processed += 1
        
        return results

if __name__ == "__main__":
    print("Generating tradeline performance records...")
    results = generate_all_tradeline_performance_records()
    
    total_records = sum(results.values())
    tradelines_processed = len(results)
    
    print(f"Generation complete! Created {total_records} performance records for {tradelines_processed} tradelines.")