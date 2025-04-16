"""
This script is used to generate sophisticated ML models for the application.
These models would be properly trained using real data in a production environment,
but for demonstration purposes, we're creating pre-trained models with synthetic data.
"""

import pickle
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestRegressor, GradientBoostingRegressor, 
    RandomForestClassifier, IsolationForest
)
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import logging

def generate_cash_flow_data(n_samples=1000):
    """Generate synthetic data for cash flow prediction model"""
    # Transaction features
    np.random.seed(42)
    data = {
        'monthly_income': np.random.normal(5000, 1000, n_samples),
        'monthly_expenses': np.random.normal(3000, 800, n_samples),
        'savings_rate': np.random.uniform(0.05, 0.25, n_samples),
        'debt_to_income': np.random.uniform(0.1, 0.5, n_samples),
        'avg_transaction_amount': np.random.normal(100, 50, n_samples),
        'num_transactions': np.random.randint(20, 100, n_samples),
        'recurring_expenses': np.random.normal(1500, 300, n_samples),
        'investment_returns': np.random.normal(200, 150, n_samples),
        'month': np.random.randint(1, 13, n_samples),  # Seasonality
    }
    
    df = pd.DataFrame(data)
    
    # Calculate cash flow with some non-linear relationships and noise
    cash_flow = (
        df['monthly_income'] - 
        df['monthly_expenses'] + 
        df['investment_returns'] - 
        df['recurring_expenses'] * (1 + 0.05 * np.sin(df['month'] * np.pi / 6)) +  # Seasonal effect
        np.random.normal(0, 200, n_samples)  # Random noise
    )
    
    return df, cash_flow

def generate_credit_usage_data(n_samples=1000):
    """Generate synthetic data for credit usage prediction model"""
    np.random.seed(43)
    data = {
        'credit_limit': np.random.uniform(5000, 50000, n_samples),
        'current_balance': np.random.uniform(0, 25000, n_samples),
        'payment_history': np.random.uniform(0.7, 1.0, n_samples),  # Percentage of on-time payments
        'monthly_income': np.random.normal(5000, 1000, n_samples),
        'years_of_credit': np.random.uniform(1, 20, n_samples),
        'num_credit_accounts': np.random.randint(1, 10, n_samples),
        'recent_credit_inquiries': np.random.randint(0, 5, n_samples),
        'employment_status': np.random.randint(0, 2, n_samples),  # Binary (0/1)
        'month': np.random.randint(1, 13, n_samples),  # Seasonality
    }
    
    df = pd.DataFrame(data)
    
    # Calculate initial credit usage percentage
    df['current_usage'] = df['current_balance'] / df['credit_limit'] * 100
    
    # Calculate future credit usage with complex factors
    # Higher predicted usage if:
    # - Current usage is high
    # - Payment history is poor
    # - Income is low relative to current balance
    # - Many recent inquiries
    # - Seasonality (holiday months)
    future_credit_usage = (
        df['current_usage'] * 0.7 +  # Base component
        (1 - df['payment_history']) * 20 +  # Payment history impact
        df['current_balance'] / df['monthly_income'] * 15 +  # Debt to income impact
        df['recent_credit_inquiries'] * 3 +  # Credit inquiries impact
        df['num_credit_accounts'] +  # Number of accounts
        np.where((df['month'] == 11) | (df['month'] == 12), 5, 0) +  # Holiday season effect
        np.random.normal(0, 5, n_samples)  # Random noise
    )
    
    # Ensure values are within 0-100 range
    future_credit_usage = np.clip(future_credit_usage, 0, 100)
    
    return df, future_credit_usage

def generate_fraud_detection_data(n_samples=1000):
    """Generate synthetic data for fraud detection model"""
    np.random.seed(44)
    
    # Generate legitimate transaction features
    legitimate_samples = int(n_samples * 0.95)  # 95% legitimate
    fraud_samples = n_samples - legitimate_samples  # 5% fraudulent
    
    # Common features for all transactions
    data = {
        'transaction_amount': np.concatenate([
            np.random.lognormal(5, 1, legitimate_samples),  # Most legitimate transactions
            np.random.lognormal(7, 2, fraud_samples)  # Fraud often has higher amounts
        ]),
        'hour_of_day': np.concatenate([
            np.random.normal(12, 5, legitimate_samples),  # Typical hours for legitimate
            np.random.normal(3, 2, fraud_samples)  # Fraudulent more common in early morning
        ]),
        'distance_from_home': np.concatenate([
            np.random.exponential(10, legitimate_samples),  # Most legitimate transactions near home
            np.random.uniform(50, 500, fraud_samples)  # Fraudulent often far from home
        ]),
        'previous_transactions_count': np.concatenate([
            np.random.poisson(20, legitimate_samples),  # Regular customers have history
            np.random.poisson(3, fraud_samples)  # Fraudulent often have less history
        ]),
        'merchant_category_risk': np.concatenate([
            np.random.beta(2, 5, legitimate_samples),  # Most legitimate in lower risk categories
            np.random.beta(5, 2, fraud_samples)  # Fraudulent more common in higher risk categories
        ]),
        'time_since_last_transaction': np.concatenate([
            np.random.exponential(24, legitimate_samples),  # Regular intervals for legitimate
            np.random.exponential(2, fraud_samples)  # Fraudulent often in bursts
        ]),
        'card_present': np.concatenate([
            np.random.binomial(1, 0.7, legitimate_samples),  # Most legitimate are card-present
            np.random.binomial(1, 0.2, fraud_samples)  # Most fraudulent are card-not-present
        ])
    }
    
    df = pd.DataFrame(data)
    
    # Add some derived features
    df['amount_vs_history'] = df['transaction_amount'] / (df['previous_transactions_count'] + 1)
    df['late_night'] = (df['hour_of_day'] < 6).astype(int)
    
    # Create labels (0: legitimate, 1: fraud)
    labels = np.concatenate([
        np.zeros(legitimate_samples), 
        np.ones(fraud_samples)
    ])
    
    # Shuffle the data
    indices = np.arange(n_samples)
    np.random.shuffle(indices)
    
    return df.iloc[indices], labels[indices]

def generate_tradeline_risk_data(n_samples=1000):
    """Generate synthetic data for tradeline risk prediction model"""
    np.random.seed(45)
    
    data = {
        'credit_score': np.random.normal(700, 100, n_samples),
        'years_of_credit_history': np.random.lognormal(2, 0.5, n_samples),
        'payment_history_percent': np.random.beta(8, 2, n_samples) * 100,  # Mostly good payment history
        'credit_utilization': np.random.beta(2, 4, n_samples) * 100,
        'recent_inquiries': np.random.poisson(1, n_samples),
        'delinquencies_last_year': np.random.poisson(0.2, n_samples),
        'total_debt': np.random.lognormal(10, 1, n_samples) * 1000,
        'income_to_debt_ratio': np.random.lognormal(0, 0.5, n_samples),
        'age': np.random.normal(40, 10, n_samples),
        'employment_years': np.random.lognormal(1.5, 0.7, n_samples),
        'has_mortgage': np.random.binomial(1, 0.5, n_samples),
        'has_auto_loan': np.random.binomial(1, 0.4, n_samples),
    }
    
    df = pd.DataFrame(data)
    
    # Calculate tradeline risk score (0-100, higher = riskier)
    risk_score = (
        100 - (df['credit_score'] - 300) / 5 +  # Credit score component (300-850 scale)
        df['delinquencies_last_year'] * 15 +  # Delinquencies heavily increase risk
        df['credit_utilization'] * 0.3 +  # Higher utilization increases risk
        df['recent_inquiries'] * 3 -  # Recent inquiries increase risk
        df['years_of_credit_history'] * 2 -  # Longer history reduces risk
        df['payment_history_percent'] * 0.2 +  # Good payment history reduces risk
        10 * (1 - df['income_to_debt_ratio']).clip(0, 1) +  # Low income to debt ratio increases risk
        np.random.normal(0, 5, n_samples)  # Random noise
    )
    
    # Ensure values are within 0-100 range
    risk_score = np.clip(risk_score, 0, 100)
    
    return df, risk_score

def create_mock_models():
    """Create and save sophisticated ML models for demonstration purposes"""
    logging.info("Creating advanced ML models...")
    
    # Create models directory if it doesn't exist
    os.makedirs('models', exist_ok=True)
    
    # ----- Cash Flow Prediction Model -----
    X_cash_flow, y_cash_flow = generate_cash_flow_data()
    X_train, X_test, y_train, y_test = train_test_split(X_cash_flow, y_cash_flow, test_size=0.2)
    
    # Create a pipeline with preprocessing and ensemble model
    cash_flow_model = Pipeline([
        ('scaler', StandardScaler()),
        ('model', GradientBoostingRegressor(
            n_estimators=100, 
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        ))
    ])
    
    cash_flow_model.fit(X_train, y_train)
    
    # Evaluate model
    train_score = cash_flow_model.score(X_train, y_train)
    test_score = cash_flow_model.score(X_test, y_test)
    logging.info(f"Cash Flow Model - R² score: Train={train_score:.4f}, Test={test_score:.4f}")
    
    # Save model
    with open('models/cash_flow_model.pkl', 'wb') as f:
        pickle.dump(cash_flow_model, f)
    
    # ----- Credit Usage Prediction Model -----
    X_credit_usage, y_credit_usage = generate_credit_usage_data()
    X_train, X_test, y_train, y_test = train_test_split(X_credit_usage, y_credit_usage, test_size=0.2)
    
    # Neural network for credit usage prediction
    credit_usage_model = Pipeline([
        ('scaler', StandardScaler()),
        ('model', MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation='relu',
            solver='adam',
            alpha=0.001,
            max_iter=500,
            random_state=42
        ))
    ])
    
    credit_usage_model.fit(X_train, y_train)
    
    # Evaluate model
    train_score = credit_usage_model.score(X_train, y_train)
    test_score = credit_usage_model.score(X_test, y_test)
    logging.info(f"Credit Usage Model - R² score: Train={train_score:.4f}, Test={test_score:.4f}")
    
    # Save model
    with open('models/credit_usage_model.pkl', 'wb') as f:
        pickle.dump(credit_usage_model, f)
    
    # ----- Fraud Detection Model -----
    X_fraud, y_fraud = generate_fraud_detection_data()
    X_train, X_test, y_train, y_test = train_test_split(X_fraud, y_fraud, test_size=0.2)
    
    # Random Forest for fraud detection
    fraud_model = Pipeline([
        ('scaler', StandardScaler()),
        ('model', RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight='balanced',
            random_state=42
        ))
    ])
    
    fraud_model.fit(X_train, y_train)
    
    # Evaluate model
    train_score = fraud_model.score(X_train, y_train)
    test_score = fraud_model.score(X_test, y_test)
    logging.info(f"Fraud Detection Model - Accuracy: Train={train_score:.4f}, Test={test_score:.4f}")
    
    # Save model
    with open('models/fraud_model.pkl', 'wb') as f:
        pickle.dump(fraud_model, f)
    
    # ----- Tradeline Risk Assessment Model (New) -----
    X_risk, y_risk = generate_tradeline_risk_data()
    X_train, X_test, y_train, y_test = train_test_split(X_risk, y_risk, test_size=0.2)
    
    # Gradient Boosting for risk assessment
    risk_model = Pipeline([
        ('scaler', StandardScaler()),
        ('model', GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        ))
    ])
    
    risk_model.fit(X_train, y_train)
    
    # Evaluate model
    train_score = risk_model.score(X_train, y_train)
    test_score = risk_model.score(X_test, y_test)
    logging.info(f"Tradeline Risk Model - R² score: Train={train_score:.4f}, Test={test_score:.4f}")
    
    # Save model
    with open('models/tradeline_risk_model.pkl', 'wb') as f:
        pickle.dump(risk_model, f)
    
    logging.info("Advanced models created successfully")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_mock_models()
