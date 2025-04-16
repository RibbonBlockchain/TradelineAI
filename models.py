from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Import the SQLAlchemy instance from the centralized db.py module
from db import db

class User(UserMixin, db.Model):
    """User model for authentication and profile information"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    accessibility_preferences = db.Column(db.Text, nullable=True)  # JSON string of accessibility preferences
    
    # Password reset fields
    reset_password_token = db.Column(db.String(128), index=True)
    reset_password_expires = db.Column(db.DateTime)
    
    # OAuth fields for Google login
    google_id = db.Column(db.String(128), unique=True, nullable=True)
    is_oauth_user = db.Column(db.Boolean, default=False)
    
    # Relationship to credit profile
    credit_profile = db.relationship('CreditProfile', backref='user', uselist=False)
    # Relationship to tradelines owned by this user
    tradelines = db.relationship('Tradeline', backref='owner', lazy='dynamic')
    # Relationship to tradelines purchased by this user
    purchased_tradelines = db.relationship(
        'TradelinePurchase', 
        backref='purchaser', 
        lazy='dynamic'
    )
    # Relationship to AI agents owned by this user
    ai_agents = db.relationship('AIAgent', backref='owner', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against stored hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        """Generate a secure token for password reset"""
        import secrets
        from datetime import datetime, timedelta
        
        # Generate a secure token
        token = secrets.token_urlsafe(32)
        
        # Set token expiration (24 hours from now)
        self.reset_password_token = token
        self.reset_password_expires = datetime.utcnow() + timedelta(hours=24)
        
        return token
    
    def verify_reset_token(self, token):
        """Verify if the reset token is valid"""
        from datetime import datetime
        
        # Check if token matches and not expired
        if self.reset_password_token == token and self.reset_password_expires > datetime.utcnow():
            return True
        return False
    
    def clear_reset_token(self):
        """Clear the reset token after use"""
        self.reset_password_token = None
        self.reset_password_expires = None
    
    def __repr__(self):
        return f'<User {self.username}>'


class CreditProfile(db.Model):
    """Credit profile with verified credit information"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    identity_number = db.Column(db.String(20))  # SSN or other ID (encrypted)
    credit_score = db.Column(db.Integer)  # Credit score from verification
    verified = db.Column(db.Boolean, default=False)
    verification_date = db.Column(db.DateTime)
    available_credit = db.Column(db.Float, default=0.0)
    total_credit_limit = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f'<CreditProfile for User {self.user_id}>'


class Tradeline(db.Model):
    """Tradeline that can be sold or rented in the marketplace"""
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    credit_limit = db.Column(db.Float, nullable=False)
    available_limit = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float)
    issuer = db.Column(db.String(100))
    account_type = db.Column(db.String(50))  # Credit card, line of credit, etc.
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_for_sale = db.Column(db.Boolean, default=False)
    is_for_rent = db.Column(db.Boolean, default=False)
    sale_price = db.Column(db.Float)
    rental_price = db.Column(db.Float)  # Per month
    rental_duration = db.Column(db.Integer, default=1)  # Default rental duration in months
    description = db.Column(db.Text)  # Description of the tradeline
    
    # Relationships
    purchases = db.relationship('TradelinePurchase', backref='tradeline', lazy='dynamic')
    ai_agent_allocations = db.relationship('AIAgentAllocation', backref='tradeline', lazy='dynamic')
    
    def __repr__(self):
        return f'<Tradeline {self.name} - ${self.credit_limit}>'


class TradelinePurchase(db.Model):
    """Record of a tradeline purchase or rental"""
    id = db.Column(db.Integer, primary_key=True)
    tradeline_id = db.Column(db.Integer, db.ForeignKey('tradeline.id'), nullable=False)
    purchaser_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    purchase_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_rental = db.Column(db.Boolean, default=False)
    rental_start_date = db.Column(db.DateTime)
    rental_end_date = db.Column(db.DateTime)
    price_paid = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)  # Original price before discount
    allocated_limit = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    promo_code_id = db.Column(db.Integer, db.ForeignKey('promo_code.id'), nullable=True)
    
    def get_discount_amount(self):
        """Calculate the discount amount applied to this purchase"""
        if self.original_price and self.price_paid and self.original_price > self.price_paid:
            return self.original_price - self.price_paid
        return 0.0
    
    def get_discount_percentage(self):
        """Calculate the discount percentage applied to this purchase"""
        if self.original_price and self.price_paid and self.original_price > 0:
            discount = self.get_discount_amount()
            return round((discount / self.original_price) * 100, 1)
        return 0.0
    
    def __repr__(self):
        return f'<TradelinePurchase {self.id} - ${self.allocated_limit}>'


class AIAgent(db.Model):
    """AI Agent that can utilize tradelines"""
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    purpose = db.Column(db.String(200))
    risk_profile = db.Column(db.String(50))  # Low, Medium, High
    credit_score = db.Column(db.Integer, default=600)  # Virtual credit score for the AI Agent
    credit_score_updated = db.Column(db.DateTime, default=datetime.utcnow)
    credit_score_history = db.Column(db.Text)  # JSON-serialized history of credit scores
    
    # Crypto wallet information
    wallet_address = db.Column(db.String(128))  # Base Layer 2 blockchain wallet address
    wallet_network = db.Column(db.String(20), default='mainnet')  # 'mainnet' or 'testnet'
    wallet_created_date = db.Column(db.DateTime)
    wallet_balance = db.Column(db.Float, default=0.0)  # Stablecoin balance in USD
    wallet_last_refresh = db.Column(db.DateTime)  # Last time the wallet balance was refreshed
    
    # BASE Name Service (BNS) identification
    bns_identifier = db.Column(db.String(256), unique=True, index=True)  # Format: [agent-name].[purpose-code].[entity-code].base
    purpose_code = db.Column(db.String(20))  # Standardized purpose code (e.g., re01, tr05)
    entity_code = db.Column(db.String(50))  # Entity/organization code
    
    # Agent-to-Agent (A2A) Protocol Integration
    a2a_enabled = db.Column(db.Boolean, default=False)  # Whether agent participates in A2A protocol
    a2a_metadata = db.Column(db.Text)  # JSON string for A2A capabilities and configuration
    a2a_last_seen = db.Column(db.DateTime)  # Last time the agent was active in A2A network
    a2a_interaction_count = db.Column(db.Integer, default=0)  # Count of A2A protocol interactions
    
    # Relationship to tradeline allocations
    tradeline_allocations = db.relationship('AIAgentAllocation', backref='agent', lazy='dynamic')
    # Relationship to transactions
    transactions = db.relationship('Transaction', backref='agent', lazy='dynamic')
    # Relationship to repayments
    repayments = db.relationship('Repayment', backref='agent', lazy='dynamic')
    
    def update_credit_score(self):
        """
        Calculate and update the AI agent's credit score based on its financial activities.
        
        Returns:
            Dictionary with the calculated credit score and component scores
        """
        from modules.agent_credit import AgentCreditScoring
        import json
        
        # Create agent data dictionary for scoring
        agent_data = {
            'id': self.id,
            'created_at': self.created_date,
            'tradelines': [
                {
                    'id': allocation.tradeline_id,
                    'credit_limit': allocation.credit_limit,
                    'type': allocation.tradeline.account_type if allocation.tradeline else None,
                    'issuer': allocation.tradeline.issuer if allocation.tradeline else None,
                    'opened_date': allocation.allocation_date
                }
                for allocation in self.tradeline_allocations
            ],
            'transactions': [
                {
                    'id': tx.id,
                    'amount': tx.amount,
                    'tradeline_id': tx.allocation.tradeline_id if tx.allocation else None,
                    'transaction_date': tx.transaction_date,
                    'status': tx.status,
                    'balance_after': tx.balance_after if hasattr(tx, 'balance_after') else None
                }
                for tx in self.transactions
            ],
            'repayments': [
                {
                    'id': rep.id,
                    'amount': rep.amount,
                    'due_date': rep.due_date,
                    'payment_date': rep.payment_date,
                    'is_late': rep.payment_date > rep.due_date if rep.payment_date and rep.due_date else False
                }
                for rep in self.repayments
            ]
        }
        
        # Calculate the credit score
        scorer = AgentCreditScoring()
        score_data = scorer.calculate_agent_credit_score(agent_data)
        
        # Update the agent's credit score
        self.credit_score = score_data['score']
        self.credit_score_updated = datetime.utcnow()
        
        # Update credit score history
        try:
            history = json.loads(self.credit_score_history) if self.credit_score_history else []
        except (json.JSONDecodeError, TypeError):
            history = []
        
        # Add the new score to history
        history = scorer.track_agent_score_history(str(self.id), score_data, history)
        self.credit_score_history = json.dumps(history)
        
        return score_data
    
    def get_credit_score_trend(self):
        """
        Get the trend analysis of the agent's credit score over time.
        
        Returns:
            Dictionary with trend analysis, or None if insufficient history
        """
        from modules.agent_credit import AgentCreditScoring
        import json
        
        try:
            history = json.loads(self.credit_score_history) if self.credit_score_history else []
        except (json.JSONDecodeError, TypeError):
            history = []
        
        if not history or len(history) < 2:
            return None
        
        scorer = AgentCreditScoring()
        return scorer.analyze_score_trend(history)
    
    def get_credit_rating(self):
        """
        Get the credit rating category based on the agent's credit score.
        
        Returns:
            String rating (Exceptional, Excellent, Good, Fair, Poor)
        """
        from modules.agent_credit import AgentCreditScoring
        
        scorer = AgentCreditScoring()
        return scorer._get_rating_from_score(self.credit_score)
    
    def __repr__(self):
        return f'<AIAgent {self.name}>'


class AIAgentAllocation(db.Model):
    """Allocation of a tradeline to an AI agent"""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agent.id'), nullable=False)
    tradeline_id = db.Column(db.Integer, db.ForeignKey('tradeline.id'), nullable=False)
    allocation_date = db.Column(db.DateTime, default=datetime.utcnow)
    credit_limit = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    spending_rules = db.Column(db.Text)  # JSON rules for spending
    
    def __repr__(self):
        return f'<AIAgentAllocation Agent={self.agent_id} Tradeline={self.tradeline_id}>'


class Transaction(db.Model):
    """Transactions made by AI agents using tradelines"""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agent.id'), nullable=False)
    tradeline_allocation_id = db.Column(db.Integer, db.ForeignKey('ai_agent_allocation.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    merchant = db.Column(db.String(200), nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='completed')  # completed, pending, declined
    balance_after = db.Column(db.Float)  # Balance after transaction
    
    # Relationship to allocation
    allocation = db.relationship('AIAgentAllocation', backref='transactions')
    
    def __repr__(self):
        return f'<Transaction ${self.amount} - {self.merchant}>'


class Repayment(db.Model):
    """Repayments made by AI agents for their tradeline transactions"""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agent.id'), nullable=False)
    tradeline_allocation_id = db.Column(db.Integer, db.ForeignKey('ai_agent_allocation.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    payment_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='scheduled')  # scheduled, paid, late, missed
    description = db.Column(db.Text)
    
    # Relationship to allocation
    allocation = db.relationship('AIAgentAllocation', backref='repayments')
    
    def is_late(self):
        """Check if payment is late but has been made"""
        if self.payment_date and self.due_date:
            return self.payment_date > self.due_date
        return False
    
    def is_missed(self):
        """Check if payment is missed (past due date with no payment)"""
        if not self.payment_date and self.due_date:
            return datetime.utcnow() > self.due_date
        return False
    
    def update_status(self):
        """Update the status based on payment state"""
        if self.payment_date:
            self.status = 'late' if self.is_late() else 'paid'
        else:
            self.status = 'missed' if self.is_missed() else 'scheduled'
    
    def __repr__(self):
        return f'<Repayment ${self.amount} - {self.status}>'


class PromoCode(db.Model):
    """Promotion code for tradeline rentals"""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)  # Discount percentage (1-100)
    is_active = db.Column(db.Boolean, default=True)
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime, nullable=True)  # NULL means no expiration
    max_uses = db.Column(db.Integer, nullable=True)  # NULL means unlimited uses
    current_uses = db.Column(db.Integer, default=0)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))  # Description of the promo code
    
    # Relationship with TradelinePurchase
    purchases = db.relationship('TradelinePurchase', backref='promo_code', lazy='dynamic')
    
    def is_valid(self):
        """Check if the promo code is valid and can be used"""
        now = datetime.utcnow()
        
        # Check if code is active
        if not self.is_active:
            return False
            
        # Check if code is within valid date range
        if self.valid_until is not None and now > self.valid_until:
            return False
            
        # Check if code has reached max uses
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False
            
        return True
    
    def apply_discount(self, original_price):
        """Apply the discount to the original price"""
        if not self.is_valid():
            return original_price
            
        discount_amount = (original_price * self.discount_percentage) / 100
        return original_price - discount_amount
    
    def increment_usage(self):
        """Increment the usage count of this promo code"""
        self.current_uses += 1
        
    def __repr__(self):
        return f'<PromoCode {self.code} - {self.discount_percentage}% off>'


class DefiLoan(db.Model):
    """DeFi loan taken by an AI Agent"""
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('ai_agent.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # DeFi protocol provider (e.g., Aave, Compound)
    token = db.Column(db.String(10), nullable=False)     # Stablecoin token (e.g., USDC, USDT)
    amount = db.Column(db.Float, nullable=False)         # Principal amount borrowed
    term_days = db.Column(db.Integer, nullable=False)    # Loan term in days
    interest_rate = db.Column(db.Float, nullable=False)  # APY in percent
    total_interest = db.Column(db.Float, nullable=False) # Total interest over term
    total_repayment = db.Column(db.Float, nullable=False) # Total amount to repay (principal + interest)
    status = db.Column(db.String(20), default='pending') # pending, active, repaid, defaulted
    loan_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Collateral fields
    has_collateral = db.Column(db.Boolean, default=False)  # Whether this loan uses tradeline collateral
    collateral_allocation_id = db.Column(db.Integer, db.ForeignKey('ai_agent_allocation.id'))  # Tradeline used as collateral
    collateral_amount = db.Column(db.Float)  # Amount of tradeline credit used as collateral
    collateral_liquidated = db.Column(db.Boolean, default=False)  # Whether collateral was liquidated due to default
    liquidation_date = db.Column(db.DateTime)  # When collateral was liquidated
    
    # Relationships
    agent = db.relationship('AIAgent', backref=db.backref('defi_loans', lazy='dynamic'))
    repayments = db.relationship('DefiRepayment', backref='loan', lazy='dynamic', cascade='all, delete-orphan')
    collateral_allocation = db.relationship('AIAgentAllocation', backref='collateralized_loans', foreign_keys=[collateral_allocation_id])
    
    def calculate_current_balance(self):
        """Calculate the current outstanding balance"""
        paid = sum([r.amount for r in self.repayments.filter_by(status='paid').all()])
        return self.total_repayment - paid
    
    def next_payment(self):
        """Get the next scheduled payment"""
        return self.repayments.filter_by(status='scheduled').order_by(DefiRepayment.due_date).first()
    
    def payment_progress(self):
        """Calculate the payment progress as a percentage"""
        paid = sum([r.amount for r in self.repayments.filter_by(status='paid').all()])
        if self.total_repayment > 0:
            return round((paid / self.total_repayment) * 100, 1)
        return 0
    
    def collateral_to_loan_ratio(self):
        """Calculate the collateral-to-loan ratio as a percentage"""
        if not self.has_collateral or not self.collateral_amount or self.amount <= 0:
            return 0
        return round((self.collateral_amount / self.amount) * 100, 1)
    
    def is_collateral_sufficient(self):
        """Check if collateral is sufficient based on current outstanding balance"""
        if not self.has_collateral or self.collateral_liquidated:
            return False
        
        current_balance = self.calculate_current_balance()
        return self.collateral_amount >= current_balance
    
    def liquidate_collateral(self):
        """Process collateral liquidation for defaulted loans"""
        if not self.has_collateral or self.collateral_liquidated:
            return False
            
        # Mark as liquidated
        self.collateral_liquidated = True
        self.liquidation_date = datetime.utcnow()
        self.status = 'defaulted'
        
        # Update any remaining scheduled payments as missed
        for repayment in self.repayments.filter_by(status='scheduled').all():
            repayment.status = 'missed'
        
        return True
        
    def __repr__(self):
        return f'<DefiLoan {self.id}: {self.amount} {self.token} from {self.provider}>'


class DefiRepayment(db.Model):
    """Scheduled repayment for a DeFi loan"""
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('defi_loan.id'), nullable=False)
    payment_number = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    payment_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, paid, late, missed
    transaction_hash = db.Column(db.String(100))  # Blockchain transaction hash if applicable
    
    def is_late(self):
        """Check if this payment is late"""
        if not self.payment_date and self.due_date < datetime.utcnow():
            return True
        return False
        
    def days_overdue(self):
        """Calculate days overdue for this payment"""
        if self.is_late():
            delta = datetime.utcnow() - self.due_date
            return delta.days
        return 0
        
    def update_status(self):
        """Update the status based on payment state"""
        if self.payment_date:
            self.status = 'paid'
        else:
            if self.is_late():
                self.status = 'late'
                if self.days_overdue() > 30:  # Over 30 days late is considered missed
                    self.status = 'missed'
            else:
                self.status = 'scheduled'
                
    def __repr__(self):
        return f'<DefiRepayment {self.id}: {self.amount} due {self.due_date}>'


class TradelinePerformance(db.Model):
    """Historical performance metrics for tradelines"""
    id = db.Column(db.Integer, primary_key=True)
    tradeline_id = db.Column(db.Integer, db.ForeignKey('tradeline.id'), nullable=False)
    record_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Utilization metrics
    current_balance = db.Column(db.Float, default=0.0)
    available_credit = db.Column(db.Float)
    utilization_rate = db.Column(db.Float)  # Balance / Credit Limit
    
    # Transaction metrics
    transaction_count = db.Column(db.Integer, default=0)
    transaction_volume = db.Column(db.Float, default=0.0)
    avg_transaction_amount = db.Column(db.Float)
    
    # Repayment metrics
    total_repayments = db.Column(db.Float, default=0.0)
    repayments_on_time = db.Column(db.Integer, default=0)
    repayments_late = db.Column(db.Integer, default=0)
    payment_ratio = db.Column(db.Float)  # Repayments / Balance
    
    # Risk and financial health metrics
    risk_score = db.Column(db.Float)  # 0 (lowest risk) to 100 (highest risk)
    days_delinquent = db.Column(db.Integer, default=0)
    interest_accrued = db.Column(db.Float, default=0.0)
    
    # Relationship to tradeline
    tradeline = db.relationship('Tradeline', backref=db.backref('performance_records', lazy='dynamic'))
    
    @classmethod
    def record_tradeline_performance(cls, tradeline_id):
        """Creates a new performance record for a tradeline"""
        from sqlalchemy import func
        
        tradeline = Tradeline.query.get(tradeline_id)
        
        if not tradeline:
            return None
            
        # Gather all agent allocations for this tradeline
        allocations = AIAgentAllocation.query.filter_by(tradeline_id=tradeline_id, is_active=True).all()
        allocation_ids = [a.id for a in allocations]
        
        # Prepare performance metrics
        metrics = {}
        
        # Skip if no allocations
        if not allocation_ids:
            return None
            
        # Calculate utilization metrics
        transactions = Transaction.query.filter(
            Transaction.tradeline_allocation_id.in_(allocation_ids),
            Transaction.status == 'completed'
        ).all()
        
        total_balance = sum([t.amount for t in transactions])
        metrics['current_balance'] = total_balance
        metrics['available_credit'] = tradeline.credit_limit - total_balance
        metrics['utilization_rate'] = (total_balance / tradeline.credit_limit) if tradeline.credit_limit > 0 else 0
        
        # Calculate transaction metrics
        recent_transactions = Transaction.query.filter(
            Transaction.tradeline_allocation_id.in_(allocation_ids),
            Transaction.status == 'completed',
            Transaction.transaction_date >= (datetime.utcnow() - timedelta(days=30))
        ).all()
        
        metrics['transaction_count'] = len(recent_transactions)
        metrics['transaction_volume'] = sum([t.amount for t in recent_transactions])
        metrics['avg_transaction_amount'] = metrics['transaction_volume'] / metrics['transaction_count'] if metrics['transaction_count'] > 0 else 0
        
        # Calculate repayment metrics
        repayments = Repayment.query.filter(
            Repayment.tradeline_allocation_id.in_(allocation_ids),
            Repayment.status.in_(['paid', 'late'])
        ).all()
        
        metrics['total_repayments'] = sum([r.amount for r in repayments])
        metrics['repayments_on_time'] = len([r for r in repayments if r.status == 'paid' and not r.is_late()])
        metrics['repayments_late'] = len([r for r in repayments if r.status == 'late' or r.is_late()])
        metrics['payment_ratio'] = metrics['total_repayments'] / total_balance if total_balance > 0 else 1.0
        
        # Calculate risk and financial health metrics
        late_repayments = [r for r in repayments if r.status == 'late' or r.is_late()]
        total_days_late = sum([r.days_overdue() for r in late_repayments]) if late_repayments else 0
        
        metrics['days_delinquent'] = total_days_late
        
        # Risk score calculation (0-100 scale, higher is riskier)
        # Factors: utilization rate, late payments, payment ratio
        risk_utilization = metrics['utilization_rate'] * 30  # 0-30 points
        risk_late_payments = min(40, metrics['repayments_late'] * 10)  # 0-40 points
        risk_payment_ratio = max(0, 30 - metrics['payment_ratio'] * 30)  # 0-30 points
        
        metrics['risk_score'] = risk_utilization + risk_late_payments + risk_payment_ratio
        
        # Calculate interest accrued
        # Simple interest calculation based on balance, interest rate and time
        metrics['interest_accrued'] = (total_balance * (tradeline.interest_rate / 100) / 365) * 30  # Approximate monthly interest
        
        # Create and save the performance record
        performance = cls(
            tradeline_id=tradeline_id,
            current_balance=metrics['current_balance'],
            available_credit=metrics['available_credit'],
            utilization_rate=metrics['utilization_rate'],
            transaction_count=metrics['transaction_count'],
            transaction_volume=metrics['transaction_volume'],
            avg_transaction_amount=metrics['avg_transaction_amount'],
            total_repayments=metrics['total_repayments'],
            repayments_on_time=metrics['repayments_on_time'],
            repayments_late=metrics['repayments_late'],
            payment_ratio=metrics['payment_ratio'],
            risk_score=metrics['risk_score'],
            days_delinquent=metrics['days_delinquent'],
            interest_accrued=metrics['interest_accrued']
        )
        
        db.session.add(performance)
        db.session.commit()
        
        return performance
    
    def __repr__(self):
        return f'<TradelinePerformance {self.tradeline_id} - {self.record_date}>'