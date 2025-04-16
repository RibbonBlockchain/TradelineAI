#!/usr/bin/env python3
"""
Migration script to add TradelinePerformance model for tracking tradeline usage metrics.
This script will:
1. Create the TradelinePerformance table
2. Initialize performance records for existing tradelines with activity
"""

from datetime import datetime, timedelta
from app import app, db
from models import Tradeline, AIAgentAllocation, Transaction, Repayment
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradelinePerformance(Base):
    """Historical performance metrics for tradelines"""
    __tablename__ = 'tradeline_performance'
    
    id = Column(Integer, primary_key=True)
    tradeline_id = Column(Integer, ForeignKey('tradeline.id'), nullable=False)
    record_date = Column(DateTime, default=datetime.utcnow)
    
    # Utilization metrics
    current_balance = Column(Float, default=0.0)
    available_credit = Column(Float)
    utilization_rate = Column(Float)  # Balance / Credit Limit
    
    # Transaction metrics
    transaction_count = Column(Integer, default=0)
    transaction_volume = Column(Float, default=0.0)
    avg_transaction_amount = Column(Float)
    
    # Repayment metrics
    total_repayments = Column(Float, default=0.0)
    repayments_on_time = Column(Integer, default=0)
    repayments_late = Column(Integer, default=0)
    payment_ratio = Column(Float)  # Repayments / Balance
    
    # Risk and financial health metrics
    risk_score = Column(Float)  # 0 (lowest risk) to 100 (highest risk)
    days_delinquent = Column(Integer, default=0)
    interest_accrued = Column(Float, default=0.0)


def create_tradeline_performance_table():
    """Create the TradelinePerformance table in the database"""
    try:
        TradelinePerformance.__table__.create(db.engine)
        print("TradelinePerformance table created successfully")
        return True
    except Exception as e:
        print(f"Error creating TradelinePerformance table: {e}")
        return False


def create_performance_records():
    """Create initial performance records for tradelines with activity"""
    tradelines = Tradeline.query.all()
    records_created = 0
    
    for tradeline in tradelines:
        # Only process tradelines that have allocations
        allocations = AIAgentAllocation.query.filter_by(tradeline_id=tradeline.id, is_active=True).all()
        if not allocations:
            continue
        
        allocation_ids = [a.id for a in allocations]
        
        # Get all transactions for this tradeline
        transactions = Transaction.query.filter(
            Transaction.tradeline_allocation_id.in_(allocation_ids),
            Transaction.status == 'completed'
        ).all()
        
        if not transactions:
            continue
        
        # Calculate metrics
        total_balance = sum([t.amount for t in transactions])
        available_credit = tradeline.credit_limit - total_balance
        utilization_rate = (total_balance / tradeline.credit_limit) if tradeline.credit_limit > 0 else 0
        
        # Calculate recent transaction metrics (last 30 days)
        recent_transactions = [t for t in transactions if t.transaction_date >= (datetime.utcnow() - timedelta(days=30))]
        transaction_count = len(recent_transactions)
        transaction_volume = sum([t.amount for t in recent_transactions])
        avg_transaction_amount = transaction_volume / transaction_count if transaction_count > 0 else 0
        
        # Calculate repayment metrics
        repayments = Repayment.query.filter(
            Repayment.tradeline_allocation_id.in_(allocation_ids)
        ).all()
        
        total_repayments = sum([r.amount for r in repayments])
        repayments_on_time = len([r for r in repayments if r.status == 'paid' and not r.is_late()])
        repayments_late = len([r for r in repayments if r.status == 'late' or r.is_late()])
        payment_ratio = total_repayments / total_balance if total_balance > 0 else 1.0
        
        # Calculate risk metrics
        late_repayments = [r for r in repayments if r.status == 'late' or r.is_late()]
        total_days_late = sum([r.days_overdue() for r in late_repayments]) if late_repayments else 0
        
        # Risk score calculation (0-100 scale, higher is riskier)
        risk_utilization = utilization_rate * 30  # 0-30 points
        risk_late_payments = min(40, repayments_late * 10)  # 0-40 points
        risk_payment_ratio = max(0, 30 - payment_ratio * 30)  # 0-30 points
        risk_score = risk_utilization + risk_late_payments + risk_payment_ratio
        
        # Calculate interest accrued (monthly approximation)
        interest_accrued = (total_balance * (tradeline.interest_rate / 100) / 365) * 30
        
        # Create the performance record
        performance = TradelinePerformance(
            tradeline_id=tradeline.id,
            current_balance=total_balance,
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
            days_delinquent=total_days_late,
            interest_accrued=interest_accrued
        )
        
        db.session.add(performance)
        records_created += 1
    
    try:
        db.session.commit()
        print(f"Created {records_created} initial performance records")
        return records_created
    except Exception as e:
        db.session.rollback()
        print(f"Error creating performance records: {e}")
        return 0


def run_migration():
    """Run the complete migration"""
    print("Starting tradeline performance migration...")
    
    if create_tradeline_performance_table():
        create_performance_records()
        
    print("Tradeline performance migration completed")


# Run the migration if this script is executed directly
if __name__ == "__main__":
    with app.app_context():
        run_migration()