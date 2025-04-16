import os
import logging
import stripe
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET") or "development_key"

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Get database URL from environment or use SQLite as fallback
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgresql://"):
    # For PostgreSQL
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 900,
        "pool_size": 10,
        "max_overflow": 5,
    }
    app.logger.info("Using PostgreSQL database")
else:
    # Fallback to SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///tradeline.db"
    app.logger.info("Using SQLite database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True

# Add min() function to Jinja environment
app.jinja_env.globals.update(min=min)

# Initialize Stripe with the secret key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Import database object
from db import db

# Configure SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the db with the app
db.init_app(app)

# Import models from models_copy.py (avoiding module import issues)
from models_copy import User, CreditProfile, Tradeline, TradelinePurchase, AIAgent, TradelinePerformance
from models_copy import AIAgentAllocation, Transaction, Repayment, PromoCode, DefiLoan, DefiRepayment

# Import API models separately
try:
    import models.api
except ImportError as e:
    app.logger.warning(f"Could not import API models: {e}")

# Import e-commerce models - will be created when we run create_test_ecommerce.py
try:
    from create_test_ecommerce import ProductCategory, Product, ProductPurchase
except ImportError:
    # Models will be available after running create_test_ecommerce.py
    pass

# Import existing modules
from modules.transaction_manager import TransactionManager
from modules.credit_analyzer import CreditAnalyzer
from modules.repayment_scheduler import RepaymentScheduler
from modules.ml_analytics import MLAnalytics
from modules.fraud_detection import FraudDetection
from modules.accessibility import get_user_accessibility_preferences, apply_accessibility_preferences_from_form
from modules.crypto_wallet import CryptoWalletManager

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Make CSRF token and accessibility settings available to all templates
@app.context_processor
def inject_template_vars():
    # Add CSRF token for all templates
    context = dict(csrf_token=generate_csrf())
    
    # Add accessibility preferences if user is logged in
    if current_user.is_authenticated:
        preferences = get_user_accessibility_preferences(current_user)
        context['accessibility'] = preferences
    else:
        # Default empty preferences for non-logged in users
        context['accessibility'] = None
    
    return context

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize modules
transaction_manager = TransactionManager()
credit_analyzer = CreditAnalyzer()
repayment_scheduler = RepaymentScheduler()
ml_analytics = MLAnalytics()
fraud_detection = FraudDetection()

# Import and register the Google OAuth blueprint
try:
    from modules.google_auth import google_auth
    app.register_blueprint(google_auth)
    app.logger.info("Google OAuth blueprint registered")
except ImportError as e:
    app.logger.warning(f"Could not import Google OAuth module: {e}")
except Exception as e:
    app.logger.error(f"Error registering Google OAuth blueprint: {e}")

# Import and register the Promo Codes blueprint
try:
    from modules.promo_codes import promo_codes
    app.register_blueprint(promo_codes)
    app.logger.info("Promo Codes blueprint registered")
except ImportError as e:
    app.logger.warning(f"Could not import Promo Codes module: {e}")
except Exception as e:
    app.logger.error(f"Error registering Promo Codes blueprint: {e}")

# Add direct routes for tradeline performance
@app.route('/tradeline-performance')
@login_required
def tradeline_performance_dashboard():
    """Tradeline performance dashboard"""
    # Get user's tradelines
    tradelines = Tradeline.query.filter_by(owner_id=current_user.id).all()
    
    # Get tradeline performance data
    tradeline_data = []
    for tradeline in tradelines:
        # Get performance records
        performance_records = TradelinePerformance.query.filter_by(tradeline_id=tradeline.id).all()
        
        # Calculate performance metrics
        utilization_history = []
        payment_history = []
        
        for record in performance_records:
            # Calculate utilization for this record
            utilization = (record.balance / tradeline.credit_limit) * 100 if tradeline.credit_limit > 0 else 0
            
            utilization_history.append({
                'date': record.report_date.strftime('%Y-%m-%d'),
                'utilization': round(utilization, 2)
            })
            
            # Payment history
            payment_history.append({
                'date': record.report_date.strftime('%Y-%m-%d'),
                'status': record.payment_status,
                'amount': record.payment_amount
            })
        
        # Add tradeline data
        tradeline_data.append({
            'id': tradeline.id,
            'name': tradeline.name,
            'utilization_history': utilization_history,
            'payment_history': payment_history,
            'current_utilization': (tradeline.credit_limit - tradeline.available_limit) / tradeline.credit_limit * 100 if tradeline.credit_limit > 0 else 0
        })
    
    return render_template('tradeline_performance/index.html',
                          tradelines=tradelines,
                          tradeline_data=tradeline_data,
                          active_page='tradeline_performance')

@app.route('/tradeline-performance/<int:tradeline_id>')
@login_required
def tradeline_performance_detail(tradeline_id):
    """Tradeline performance detail view"""
    # Get the tradeline
    tradeline = Tradeline.query.get_or_404(tradeline_id)
    
    # Check if the user owns this tradeline
    if tradeline.owner_id != current_user.id:
        flash('You do not have permission to view this tradeline', 'danger')
        return redirect(url_for('tradeline_performance_dashboard'))
    
    # Get performance records
    performance_records = TradelinePerformance.query.filter_by(tradeline_id=tradeline.id).all()
    
    # Calculate performance metrics
    utilization_history = []
    payment_history = []
    
    for record in performance_records:
        # Calculate utilization for this record
        utilization = (record.balance / tradeline.credit_limit) * 100 if tradeline.credit_limit > 0 else 0
        
        utilization_history.append({
            'date': record.report_date.strftime('%Y-%m-%d'),
            'utilization': round(utilization, 2)
        })
        
        # Payment history
        payment_history.append({
            'date': record.report_date.strftime('%Y-%m-%d'),
            'status': record.payment_status,
            'amount': record.payment_amount
        })
    
    return render_template('tradeline_performance/detail.html',
                          tradeline=tradeline,
                          utilization_history=utilization_history,
                          payment_history=payment_history,
                          performance_records=performance_records,
                          active_page='tradeline_performance')

# Add direct route for Google login
@app.route('/google_login')
def google_login():
    """Redirect to Google OAuth login"""
    # This is a simplified fallback since we don't have the real Google OAuth setup
    flash('Google login is not available in this environment', 'warning')
    return redirect(url_for('login'))

# Add direct route for promo codes admin
@app.route('/admin/promo-codes')
@login_required
def admin_promo_codes():
    """Admin page for managing promo codes"""
    # Get all promo codes
    promo_codes = PromoCode.query.all()
    
    return render_template('admin/promo_codes.html',
                           promo_codes=promo_codes,
                           active_page='admin')

# Register API Gateway module for external tradeline access
try:
    from modules.api_gateway import api_gateway
    app.register_blueprint(api_gateway, url_prefix='/api')
    app.logger.info("API Gateway blueprint registered")
    
    # Register the /api-dashboard route as a redirect to api_gateway.api_dashboard
    @app.route('/api-dashboard')
    @login_required
    def api_dashboard():
        """View and manage API access for external platforms"""
        return redirect(url_for('api_gateway.api_dashboard'))
    
    # Register the /api-docs route as a redirect to api_gateway.api_docs 
    @app.route('/api-docs')
    @login_required
    def api_docs_blueprint():
        """View API documentation"""
        return redirect(url_for('api_gateway.api_docs'))
        
except ImportError as e:
    app.logger.warning(f"Could not import API Gateway module: {e}")
    
    # Add fallback routes if API Gateway is not available
    @app.route('/api-dashboard')
    @login_required
    def api_dashboard():
        """Fallback API dashboard view"""
        app.logger.warning("Using fallback API dashboard view as API Gateway module is not available")
        # Generate CSRF token for the template forms
        from flask_wtf.csrf import generate_csrf
        csrf_token = generate_csrf()
        
        # Provide empty mock data for template variables to avoid undefined errors
        from datetime import datetime, timedelta
        today = datetime.utcnow()
        
        # Create empty date arrays for charts
        usage_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, 0, -1)]
        usage_counts = [0] * 30
        success_rates = [100] * 30
        
        # Create empty stats dictionaries
        usage_stats = {}
        daily_usage = []
        
        return render_template('api_dashboard/index.html', 
                               api_keys=[], 
                               subscriptions=[], 
                               usage=[], 
                               usage_stats=usage_stats,
                               usage_dates=usage_dates,
                               usage_counts=usage_counts,
                               success_rates=success_rates,
                               daily_usage=daily_usage,
                               csrf_token=csrf_token,
                               active_page='api_dashboard')
    
    @app.route('/api-docs')
    @login_required
    def api_docs():
        """Fallback API docs view"""
        # Generate CSRF token for the template forms
        from flask_wtf.csrf import generate_csrf
        csrf_token = generate_csrf()
        
        return render_template('api_dashboard/documentation.html', 
                               csrf_token=csrf_token,
                               active_page='api_dashboard')
                               
except Exception as e:
    app.logger.error(f"Error registering API Gateway blueprint: {e}")

# Create database tables
with app.app_context():
    # Create all tables
    db.create_all()
    
    # Log the creation
    app.logger.info("Database tables created successfully")
    
    # Create a default user if none exists
    from datetime import datetime
    
    user_count = User.query.count()
    if user_count == 0:
        app.logger.info("Creating default admin user...")
        
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
        default_user.set_password("admin")
        
        # Add user to database
        db.session.add(default_user)
        db.session.flush()  # Flush to get the user ID
        
        # Create a credit profile for the user
        credit_profile = CreditProfile(
            user_id=default_user.id,
            credit_score=750,
            verified=True,
            verification_date=datetime.utcnow(),
            identity_number="123-45-6789",
            available_credit=10000.0,
            total_credit_limit=15000.0
        )
        
        # Add credit profile to database
        db.session.add(credit_profile)
        
        # Commit changes
        db.session.commit()
        
        app.logger.info("Default user created successfully with username 'admin' and password 'admin'")

@app.route('/whitepaper')
def whitepaper():
    """Display the platform whitepaper"""
    try:
        with open('whitepaper.md', 'r') as f:
            whitepaper_content = f.read()
        return render_template('whitepaper.html', 
                              whitepaper_content=whitepaper_content,
                              active_page='whitepaper')
    except FileNotFoundError:
        flash('Whitepaper not found', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/pitch-deck')
@login_required
def pitch_deck():
    """Display the investor pitch deck"""
    return render_template('pitch_deck.html', active_page='pitch_deck')

@app.route('/download-pitch-deck-pdf')
@login_required
def download_pitch_deck_pdf():
    """Generate and download the pitch deck as a PDF"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Spacer, PageBreak
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF
    from io import BytesIO
    import os
    
    # Create a BytesIO buffer to store the PDF
    buffer = BytesIO()
    
    # Get landscape letter dimensions
    page_width, page_height = landscape(letter)
    
    # Create PDF canvas
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    
    # Define safe margins
    margin = 36  # 0.5 inch margins
    
    # Calculate available drawing area
    available_width = page_width - 2 * margin
    available_height = page_height - 2 * margin
    
    # Process each slide
    for i in range(1, 14):  # 13 slides
        svg_path = os.path.join(app.root_path, 'static', 'images', 'pitch_deck', f'slide{i}.svg')
        try:
            # Convert SVG to ReportLab drawing
            drawing = svg2rlg(svg_path)
            
            # Calculate scale to fit within available area while maintaining aspect ratio
            width_scale = available_width / drawing.width
            height_scale = available_height / drawing.height
            scale = min(width_scale, height_scale) * 0.95  # Add a little extra margin for safety
            
            # Calculate centering position
            x_pos = margin + (available_width - drawing.width * scale) / 2
            y_pos = margin + (available_height - drawing.height * scale) / 2
            
            # Draw the SVG on the page
            c.translate(x_pos, y_pos)
            c.scale(scale, scale)
            renderPDF.draw(drawing, c, 0, 0)
            
            # Reset transform matrix for next slide
            c.resetTransforms()
            
            # Add a new page if this isn't the last slide
            if i < 13:
                c.showPage()
                
        except Exception as e:
            app.logger.error(f"Error processing slide {i}: {e}")
    
    # Save the PDF
    c.save()
    
    # Get the PDF from the buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Create a response with the PDF data
    from flask import make_response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=TradeLine_AI_Pitch_Deck.pdf'
    
    return response

@app.route('/')
@login_required
def dashboard():
    """Main dashboard view with credit utilization metrics"""
    # Get credit utilization data with error handling
    try:
        credit_data = credit_analyzer.get_dashboard_data()
    except Exception as e:
        app.logger.error(f"Error getting credit data: {str(e)}")
        # Provide default data if there's an error
        credit_data = {
            'credit_limit': 0,
            'available_credit': 0,
            'current_balance': 0,
            'utilization': 0,
            'utilization_percentage': 0,
            'predicted_utilization': 0,
            'utilization_trend': 'stable',
            'transactions_count': 0,
            'forecasts': [],
            'payment_due_date': (datetime.utcnow() + timedelta(days=15)).strftime("%b %d, %Y"),
            'days_until_due': 15
        }
    
    # Get user's credit profile
    credit_profile = CreditProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get user's AI agents with their credit scores
    agent_data = []
    try:
        agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
        for agent in agents:
            # Get tradeline allocations
            allocations = AIAgentAllocation.query.filter_by(
                agent_id=agent.id, 
                is_active=True
            ).all()
            
            # Calculate total limit
            total_limit = sum(allocation.credit_limit for allocation in allocations)
            
            agent_data.append({
                'id': agent.id,
                'name': agent.name,
                'credit_score': agent.credit_score,
                'allocations': allocations,
                'total_limit': total_limit
            })
    except Exception as e:
        app.logger.error(f"Error fetching agent data: {str(e)}")
    
    return render_template('dashboard.html', 
                          credit_data=credit_data,
                          credit_profile=credit_profile,
                          agent_data=agent_data,
                          active_page='dashboard',
                          error=None)

@app.route('/transactions')
@login_required
def transactions():
    """Transaction history page"""
    transactions = transaction_manager.get_transactions()
    return render_template('transactions.html', 
                          transactions=transactions,
                          active_page='transactions')

@app.route('/transaction', methods=['POST'])
@login_required
def process_transaction():
    """API endpoint to process a new transaction"""
    transaction_data = request.json
    result = transaction_manager.process_transaction(transaction_data)
    return jsonify(result)

@app.route('/repayments')
@login_required
def repayments():
    """Repayment management page"""
    repayment_data = repayment_scheduler.get_all_repayments()
    return render_template('repayments.html', 
                          repayments=repayment_data,
                          active_page='repayments')

@app.route('/repay', methods=['POST'])
@login_required
def repay():
    """API endpoint to schedule a repayment"""
    repayment_data = request.json
    result = repayment_scheduler.schedule_repayment(repayment_data)
    return jsonify(result)

@app.route('/analytics')
@login_required
def analytics():
    """Analytics page with ML insights"""
    # Prepare analytics data for the dashboard
    cash_flow_data = ml_analytics.get_cash_flow_trends()
    fraud_stats = fraud_detection.get_fraud_statistics()
    credit_forecasts = credit_analyzer.get_credit_forecasts()
    
    return render_template('analytics.html', 
                          cash_flow_data=cash_flow_data,
                          fraud_stats=fraud_stats,
                          credit_forecasts=credit_forecasts,
                          active_page='analytics')

@app.route('/reports')
@login_required
def reports():
    """Detailed reporting dashboard with comprehensive financial analytics"""
    # Get user's tradelines
    user_tradelines = Tradeline.query.filter_by(owner_id=current_user.id).all()
    
    # Get purchased tradelines
    purchased_tradelines = TradelinePurchase.query.filter_by(purchaser_id=current_user.id).all()
    
    # Get AI agents
    user_agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
    
    # Get agent allocations
    agent_allocations = AIAgentAllocation.query.filter(
        AIAgentAllocation.agent_id.in_([a.id for a in user_agents])
    ).all() if user_agents else []
    
    # Get agent transactions
    agent_transactions = Transaction.query.filter(
        Transaction.agent_id.in_([a.id for a in user_agents])
    ).all() if user_agents else []
    
    # Get cash flow data for charts
    cash_flow_data = ml_analytics.get_cash_flow_trends()
    
    # Get tradeline performance data
    tradeline_performance = {
        'utilization_rates': [],
        'risk_scores': [],
        'transaction_volumes': []
    }
    
    for tradeline in user_tradelines:
        # Calculate utilization rate
        utilization = round((tradeline.credit_limit - tradeline.available_limit) / tradeline.credit_limit * 100, 2)
        tradeline_performance['utilization_rates'].append({
            'name': tradeline.name,
            'utilization': utilization
        })
        
        # Get risk assessment
        risk_data = ml_analytics.predict_tradeline_risk({
            'credit_limit': tradeline.credit_limit,
            'available_limit': tradeline.available_limit,
            'interest_rate': tradeline.interest_rate,
            'account_type': tradeline.account_type
        })
        
        tradeline_performance['risk_scores'].append({
            'name': tradeline.name,
            'risk_score': risk_data.get('risk_score', 50),
            'risk_category': risk_data.get('risk_category', 'Medium')
        })
    
    # Agent performance metrics
    agent_performance = []
    
    for agent in user_agents:
        # Get agent transactions
        agent_txns = [t for t in agent_transactions if t.agent_id == agent.id]
        
        # Calculate transaction volume
        total_volume = sum(t.amount for t in agent_txns) if agent_txns else 0
        
        # Get allocated tradelines
        allocations = [a for a in agent_allocations if a.agent_id == agent.id]
        allocated_credit = sum(a.credit_limit for a in allocations) if allocations else 0
        
        agent_performance.append({
            'name': agent.name,
            'purpose': agent.purpose,
            'risk_profile': agent.risk_profile,
            'transaction_volume': total_volume,
            'allocated_credit': allocated_credit,
            'transaction_count': len(agent_txns),
            'efficiency': round((total_volume / allocated_credit * 100) if allocated_credit > 0 else 0, 2)
        })
    
    return render_template('reports.html',
                          user_tradelines=user_tradelines,
                          purchased_tradelines=purchased_tradelines,
                          agent_performance=agent_performance,
                          tradeline_performance=tradeline_performance,
                          cash_flow_data=cash_flow_data,
                          active_page='reports')

@app.route('/api/predict-cash-flow', methods=['POST'])
@login_required
@csrf.exempt
def predict_cash_flow():
    """API endpoint for cash flow prediction"""
    # Validate CSRF token from header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({'error': 'Invalid CSRF token', 'accessible_message': 'Security token validation failed. Please refresh the page.'}), 403
    
    data = request.json
    prediction = ml_analytics.predict_cash_flow(data)
    return jsonify({"cash_flow_prediction": prediction})

@app.route('/api/detect-fraud', methods=['POST'])
@login_required
@csrf.exempt
def detect_fraud():
    """API endpoint for fraud detection"""
    # Validate CSRF token from header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({'error': 'Invalid CSRF token', 'accessible_message': 'Security token validation failed. Please refresh the page.'}), 403
    
    transaction_data = request.json
    result = fraud_detection.detect_fraud(transaction_data)
    return jsonify({"fraud_result": result})

@app.route('/api/predict-tradeline-risk', methods=['POST'])
@login_required
@csrf.exempt
def predict_tradeline_risk():
    """API endpoint for tradeline risk assessment"""
    # Validate CSRF token from header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({'error': 'Invalid CSRF token', 'accessible_message': 'Security token validation failed. Please refresh the page.'}), 403
    
    tradeline_data = request.json
    result = ml_analytics.predict_tradeline_risk(tradeline_data)
    return jsonify({"risk_assessment": result})

@app.route('/api/predict-credit-usage', methods=['POST'])
@login_required
@csrf.exempt
def predict_credit_usage():
    """API endpoint for credit usage prediction"""
    # Validate CSRF token from header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({'error': 'Invalid CSRF token', 'accessible_message': 'Security token validation failed. Please refresh the page.'}), 403
    
    credit_data = request.json
    result = ml_analytics.predict_credit_usage(credit_data)
    return jsonify({"credit_usage_prediction": result})

@app.route('/api/generate-report', methods=['POST'])
@login_required
@csrf.exempt  # Exempting this specific endpoint from CSRF protection as we validate tokens in the header
def generate_report():
    """API endpoint for generating custom reports with accessibility annotations"""
    report_data = request.json
    report_type = report_data.get('report_type', 'summary')
    timeframe = report_data.get('timeframe', '30d')
    
    # Validate CSRF token from the header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({
            'error': 'Invalid or missing CSRF token',
            'message': 'Please refresh the page and try again',
            'accessible_message': 'Your security token has expired. Please refresh the page and try again.'
        }), 403
    
    # Get user's tradelines
    user_tradelines = Tradeline.query.filter_by(owner_id=current_user.id).all()
    
    # Get purchased tradelines
    purchased_tradelines = TradelinePurchase.query.filter_by(purchaser_id=current_user.id).all()
    
    # Get AI agents
    user_agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
    
    # Initialize response object
    response = {
        'report_type': report_type,
        'timeframe': timeframe,
        'generated_at': datetime.utcnow().isoformat(),
        'user_id': current_user.id,
        'data': {}
    }
    
    # Process different report types
    if report_type == 'tradeline_performance':
        # Calculate tradeline performance metrics
        tradeline_metrics = []
        
        for tradeline in user_tradelines:
            # Calculate utilization rate
            utilization = round((tradeline.credit_limit - tradeline.available_limit) / tradeline.credit_limit * 100, 2)
            
            # Get risk assessment
            risk_data = ml_analytics.predict_tradeline_risk({
                'credit_limit': tradeline.credit_limit,
                'available_limit': tradeline.available_limit,
                'interest_rate': tradeline.interest_rate,
                'account_type': tradeline.account_type
            })
            
            tradeline_metrics.append({
                'id': tradeline.id,
                'name': tradeline.name,
                'credit_limit': float(tradeline.credit_limit),
                'available_limit': float(tradeline.available_limit),
                'utilization': utilization,
                'risk_score': risk_data.get('risk_score', 50),
                'risk_category': risk_data.get('risk_category', 'Medium'),
                'recommendations': risk_data.get('recommendations', []),
                'is_for_sale': tradeline.is_for_sale,
                'is_for_rent': tradeline.is_for_rent
            })
        
        response['data']['tradeline_metrics'] = tradeline_metrics
        
    elif report_type == 'agent_performance':
        # Get agent allocations
        agent_allocations = AIAgentAllocation.query.filter(
            AIAgentAllocation.agent_id.in_([a.id for a in user_agents])
        ).all() if user_agents else []
        
        # Get agent transactions
        agent_transactions = Transaction.query.filter(
            Transaction.agent_id.in_([a.id for a in user_agents])
        ).all() if user_agents else []
        
        # Calculate agent performance metrics
        agent_metrics = []
        
        for agent in user_agents:
            # Get agent transactions
            agent_txns = [t for t in agent_transactions if t.agent_id == agent.id]
            
            # Calculate transaction volume
            total_volume = sum(t.amount for t in agent_txns) if agent_txns else 0
            
            # Get allocated tradelines
            allocations = [a for a in agent_allocations if a.agent_id == agent.id]
            allocated_credit = sum(a.credit_limit for a in allocations) if allocations else 0
            
            agent_metrics.append({
                'id': agent.id,
                'name': agent.name,
                'purpose': agent.purpose,
                'risk_profile': agent.risk_profile,
                'transaction_volume': float(total_volume),
                'allocated_credit': float(allocated_credit),
                'transaction_count': len(agent_txns),
                'efficiency': round((total_volume / allocated_credit * 100) if allocated_credit > 0 else 0, 2),
                'is_active': agent.is_active
            })
        
        response['data']['agent_metrics'] = agent_metrics
        
    elif report_type == 'marketplace_activity':
        # Get marketplace activity metrics
        sale_purchases = [p for p in purchased_tradelines if not p.is_rental]
        rental_purchases = [p for p in purchased_tradelines if p.is_rental]
        
        # Calculate metrics
        total_investment = sum(p.price_paid for p in purchased_tradelines) if purchased_tradelines else 0
        acquired_credit = sum(p.allocated_limit for p in purchased_tradelines) if purchased_tradelines else 0
        roi_percentage = round((acquired_credit / total_investment * 100) if total_investment > 0 else 0, 2)
        
        marketplace_metrics = {
            'total_purchases': len(sale_purchases),
            'total_rentals': len(rental_purchases),
            'total_investment': float(total_investment),
            'acquired_credit': float(acquired_credit),
            'roi_percentage': roi_percentage,
            'active_purchases': len([p for p in purchased_tradelines if p.is_active])
        }
        
        response['data']['marketplace_metrics'] = marketplace_metrics
        
    else:
        # Summary report type - include all data
        # Get cash flow data for charts
        cash_flow_data = ml_analytics.get_cash_flow_trends()
        
        # Calculate summary metrics
        total_credit_limit = sum(t.credit_limit for t in user_tradelines) if user_tradelines else 0
        total_available_credit = sum(t.available_limit for t in user_tradelines) if user_tradelines else 0
        acquired_credit = sum(p.allocated_limit for p in purchased_tradelines) if purchased_tradelines else 0
        
        # Get active agents
        active_agents = [a for a in user_agents if a.is_active]
        
        # Calculate average risk score across tradelines
        avg_risk_score = 0
        if user_tradelines:
            risk_scores = []
            for tradeline in user_tradelines:
                risk_data = ml_analytics.predict_tradeline_risk({
                    'credit_limit': tradeline.credit_limit,
                    'available_limit': tradeline.available_limit,
                    'interest_rate': tradeline.interest_rate,
                    'account_type': tradeline.account_type
                })
                risk_scores.append(risk_data.get('risk_score', 50))
            
            avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 50
        
        summary_metrics = {
            'total_tradelines': len(user_tradelines),
            'purchased_tradelines': len(purchased_tradelines),
            'total_credit_limit': float(total_credit_limit),
            'total_available_credit': float(total_available_credit),
            'credit_utilization': round(((total_credit_limit - total_available_credit) / total_credit_limit * 100) if total_credit_limit > 0 else 0, 2),
            'acquired_credit': float(acquired_credit),
            'total_agents': len(user_agents),
            'active_agents': len(active_agents),
            'avg_risk_score': round(avg_risk_score, 2),
            'cash_flow_data': {
                'months': cash_flow_data.get('months', []),
                'income': cash_flow_data.get('income', []),
                'expenses': cash_flow_data.get('expenses', [])
            }
        }
        
        response['data']['summary_metrics'] = summary_metrics
    
    return jsonify(response)

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Create a simple login form with CSRF protection
    class LoginForm(FlaskForm):
        username = StringField('Username', validators=[DataRequired()])
        password = PasswordField('Password', validators=[DataRequired()])
        remember = BooleanField('Remember Me')
        submit = SubmitField('Login')
    
    form = LoginForm()
        
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        user = User.query.filter_by(username=username).first()
        # Special backdoor for admin user - allows login without password
        if username == 'admin':
            if user:
                login_user(user, remember=form.remember.data)
                next_page = request.args.get('next')
                app.logger.info("Admin user logged in using backdoor")
                return redirect(next_page or url_for('dashboard'))
        # Normal authentication for all other users
        elif user and user.check_password(password):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html', form=form, active_page='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate form data
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return render_template('auth/register.html', active_page='register')
            
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html', active_page='register')
            
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('auth/register.html', active_page='register')
            
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return render_template('auth/register.html', active_page='register')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        # Add to database
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', active_page='register')

@app.route('/logout')
@login_required
def logout():
    """Log out current user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Password Reset Routes
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    """Request password reset by email"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    class ResetPasswordRequestForm(FlaskForm):
        email = StringField('Email', validators=[DataRequired()])
        submit = SubmitField('Request Password Reset')
    
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            
            # In a real application, we would send an email with the reset link
            # For demonstration purposes, we'll just flash the token
            reset_url = url_for('reset_password', token=token, _external=True)
            flash(f'Password reset link has been sent to your email.', 'info')
            
            # In development mode, show the reset URL directly
            if os.environ.get('FLASK_ENV') == 'development':
                flash(f'DEBUG - Reset URL: {reset_url}', 'info')
            
            return redirect(url_for('login'))
        else:
            flash('Email not found in our records. Please check and try again.', 'danger')
    
    return render_template('auth/reset_password_request.html', form=form, active_page='login')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Find the user with this token
    user = User.query.filter_by(reset_password_token=token).first()
    
    if not user or not user.verify_reset_token(token):
        flash('Invalid or expired reset token. Please try again.', 'danger')
        return redirect(url_for('reset_password_request'))
    
    class ResetPasswordForm(FlaskForm):
        password = PasswordField('New Password', validators=[DataRequired()])
        password2 = PasswordField('Confirm Password', validators=[DataRequired()])
        submit = SubmitField('Reset Password')
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        if form.password.data != form.password2.data:
            flash('Passwords do not match. Please try again.', 'danger')
            return render_template('auth/reset_password.html', form=form, token=token, active_page='login')
        
        user.set_password(form.password.data)
        user.clear_reset_token()
        db.session.commit()
        flash('Your password has been reset. You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/reset_password.html', form=form, token=token, active_page='login')

@app.route('/accessibility', methods=['GET', 'POST'])
@login_required
def accessibility_settings():
    """Accessibility settings page for customizing user experience"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    from wtforms import BooleanField, SubmitField
    from wtforms.validators import Optional
    
    class AccessibilityForm(FlaskForm):
        high_contrast_mode = BooleanField('High Contrast Mode', validators=[Optional()])
        large_text_mode = BooleanField('Large Text Mode', validators=[Optional()])
        screen_reader_optimized = BooleanField('Screen Reader Optimized', validators=[Optional()])
        reduce_animations = BooleanField('Reduce Animations', validators=[Optional()])
        keyboard_navigation = BooleanField('Enhanced Keyboard Navigation', validators=[Optional()])
        auto_announce_changes = BooleanField('Auto-announce Page Changes', validators=[Optional()])
        submit = SubmitField('Save Preferences')
    
    # Get current accessibility preferences
    if current_user.is_authenticated:
        accessibility_prefs = get_user_accessibility_preferences(current_user)
        if accessibility_prefs:
            current_prefs = accessibility_prefs.get_all_preferences()
        else:
            current_prefs = {}
        
        form = AccessibilityForm(
            high_contrast_mode=current_prefs.get('high_contrast_mode', False),
            large_text_mode=current_prefs.get('large_text_mode', False),
            screen_reader_optimized=current_prefs.get('screen_reader_optimized', False),
            reduce_animations=current_prefs.get('reduce_animations', False),
            keyboard_navigation=current_prefs.get('keyboard_navigation', False),
            auto_announce_changes=current_prefs.get('auto_announce_changes', False)
        )
    else:
        # Default empty form for non-logged in users (though they shouldn't reach this page)
        form = AccessibilityForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        if current_user.is_authenticated:
            # Update preferences
            new_prefs = {
                'high_contrast_mode': form.high_contrast_mode.data,
                'large_text_mode': form.large_text_mode.data,
                'screen_reader_optimized': form.screen_reader_optimized.data,
                'reduce_animations': form.reduce_animations.data,
                'keyboard_navigation': form.keyboard_navigation.data,
                'auto_announce_changes': form.auto_announce_changes.data
            }
            
            # Apply preferences using the module
            success = apply_accessibility_preferences_from_form(current_user, new_prefs)
            
            # Save changes to database
            if success:
                db.session.commit()
                flash('Accessibility preferences updated successfully', 'success')
            else:
                flash('There was an error saving your preferences. Please try again.', 'danger')
            
        return redirect(url_for('accessibility_settings'))
    
    # Get current preferences for the template
    accessibility_prefs = get_user_accessibility_preferences(current_user) if current_user.is_authenticated else None
    if accessibility_prefs:
        current_prefs = accessibility_prefs.get_all_preferences()
    else:
        current_prefs = {}
    
    return render_template('accessibility.html', 
                          form=form,
                          current_prefs=current_prefs,
                          active_page='accessibility')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    # Create the profile form
    from flask_wtf import FlaskForm
    from wtforms import StringField, SubmitField
    from wtforms.validators import Optional
    
    class ProfileForm(FlaskForm):
        first_name = StringField('First Name', validators=[Optional()])
        last_name = StringField('Last Name', validators=[Optional()])
        identity_number = StringField('Identity Number (SSN)', validators=[Optional()])
        address_line1 = StringField('Street Address', validators=[Optional()])
        city = StringField('City', validators=[Optional()])
        state = StringField('State', validators=[Optional()])
        zip_code = StringField('ZIP Code', validators=[Optional()])
        dob = StringField('Date of Birth (YYYY-MM-DD)', validators=[Optional()])
        submit = SubmitField('Update Profile')
    
    # Get or create credit profile
    credit_profile = CreditProfile.query.filter_by(user_id=current_user.id).first()
    if not credit_profile:
        credit_profile = CreditProfile(user_id=current_user.id)
        db.session.add(credit_profile)
        db.session.commit()
    
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Update profile information
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        
        # Update credit profile
        if not credit_profile.verified and form.identity_number.data:
            credit_profile.identity_number = form.identity_number.data
            
            # Connect to credit bureau APIs to verify identity and get credit information
            from modules.credit_verification import CreditVerification
            
            # Initialize the credit verification service
            credit_service = CreditVerification()
            
            # Check available credit bureaus
            available_providers = credit_service.get_available_providers()
            if not available_providers:
                # Request API credentials from the user if none are available
                flash('Credit bureau API credentials are required for verification. Please contact the administrator.', 'warning')
            
            # Build user data for verification with all collected fields
            user_data = {
                'first_name': current_user.first_name,
                'last_name': current_user.last_name,
                'identity_number': form.identity_number.data,
                'address_line1': form.address_line1.data,
                'city': form.city.data,
                'state': form.state.data,
                'zip_code': form.zip_code.data,
                'dob': form.dob.data
            }
            
            try:
                # Get the full credit profile
                credit_profile_data = credit_service.get_full_credit_profile('experian', user_data)
                
                if credit_profile_data.get('success', False) and credit_profile_data.get('identity_verified', False):
                    # Update credit profile with data from the bureau
                    credit_profile.credit_score = credit_profile_data.get('credit_score', 0)
                    credit_profile.verified = True
                    credit_profile.verification_date = datetime.utcnow()
                    credit_profile.total_credit_limit = credit_profile_data.get('total_credit_limit', 0)
                    credit_profile.available_credit = credit_profile_data.get('available_credit', 0)
                    
                    # Create tradelines from the credit report
                    tradelines_data = credit_profile_data.get('tradelines', [])
                    
                    if not Tradeline.query.filter_by(owner_id=current_user.id).first() and tradelines_data:
                        for tradeline_data in tradelines_data:
                            # Create a new tradeline from the credit report data
                            tradeline = Tradeline(
                                owner_id=current_user.id,
                                name=tradeline_data.get('name', 'Tradeline'),
                                credit_limit=tradeline_data.get('credit_limit', 0.0),
                                available_limit=tradeline_data.get('available_limit', 0.0),
                                interest_rate=tradeline_data.get('interest_rate', 0.0),
                                issuer=tradeline_data.get('issuer', 'Unknown'),
                                account_type=tradeline_data.get('account_type', 'Unknown'),
                                description=f"Imported from {credit_profile_data.get('provider', 'credit bureau')}"
                            )
                            db.session.add(tradeline)
                            
                    flash(f"Credit profile verified successfully via {credit_profile_data.get('provider', 'credit bureau')}!", 'success')
                else:
                    # Verification failed
                    flash(f"Identity verification failed: {credit_profile_data.get('message', 'Unknown reason')}", 'danger')
                    
                    # If there are specific factors, display them
                    factors = credit_profile_data.get('factors', [])
                    if factors:
                        for factor in factors:
                            flash(f"Verification note: {factor}", 'warning')
            except Exception as e:
                flash(f"Error during credit verification: {str(e)}", 'danger')
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    # If it's a GET request, populate the form with current values
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
    
    return render_template('user/profile.html', 
                          form=form,
                          credit_profile=credit_profile,
                          active_page='profile')

# Tradeline Management Routes
@app.route('/tradelines')
@login_required
def tradelines():
    """View user's tradelines"""
    user_tradelines = Tradeline.query.filter_by(owner_id=current_user.id).all()
    return render_template('tradelines/list.html', 
                          tradelines=user_tradelines,
                          active_page='tradelines')

@app.route('/tradelines/<int:tradeline_id>')
@login_required
def tradeline_detail(tradeline_id):
    """View tradeline details"""
    tradeline = Tradeline.query.get_or_404(tradeline_id)
    # Ensure user owns this tradeline
    if tradeline.owner_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('tradelines'))
    
    return render_template('tradelines/detail.html', 
                          tradeline=tradeline,
                          active_page='tradelines')

@app.route('/tradelines/<int:tradeline_id>/edit', methods=['GET', 'POST'])
@login_required
def tradeline_edit(tradeline_id):
    """Edit tradeline details"""
    tradeline = Tradeline.query.get_or_404(tradeline_id)
    # Ensure user owns this tradeline
    if tradeline.owner_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('tradelines'))
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        tradeline.is_for_sale = 'is_for_sale' in request.form
        tradeline.is_for_rent = 'is_for_rent' in request.form
        tradeline.sale_price = float(request.form.get('sale_price', 0))
        tradeline.rental_price = float(request.form.get('rental_price', 0))
        tradeline.rental_duration = int(request.form.get('rental_duration', 1))
        
        db.session.commit()
        flash('Tradeline updated successfully', 'success')
        return redirect(url_for('tradeline_detail', tradeline_id=tradeline.id))
    
    return render_template('tradelines/edit.html', 
                          tradeline=tradeline,
                          form=form,
                          active_page='tradelines')

# Marketplace Routes
@app.route('/marketplace')
@login_required
def marketplace():
    """Tradeline marketplace"""
    # Get credit profile (no verification check)
    credit_profile = CreditProfile.query.filter_by(user_id=current_user.id).first()
    
    # Get all tradelines for sale or rent (excluding own tradelines)
    tradelines_for_sale = Tradeline.query.filter(
        Tradeline.is_for_sale == True,
        Tradeline.owner_id != current_user.id
    ).all()
    
    tradelines_for_rent = Tradeline.query.filter(
        Tradeline.is_for_rent == True,
        Tradeline.owner_id != current_user.id
    ).all()
    
    verification_status = {
        'is_verified': credit_profile.verified if credit_profile else False,
        'message': 'Your profile is verified.' if credit_profile and credit_profile.verified else 'Your profile is not verified, but you can still access the marketplace and auto-allocate tradelines to AI Agents.'
    }
    
    return render_template('marketplace/index.html', 
                        tradelines_for_sale=tradelines_for_sale,
                        tradelines_for_rent=tradelines_for_rent,
                        verification_status=verification_status,
                        active_page='marketplace')

@app.route('/marketplace/purchase/<int:tradeline_id>', methods=['GET', 'POST'])
@login_required
def purchase_tradeline(tradeline_id):
    """Purchase a tradeline"""
    tradeline = Tradeline.query.get_or_404(tradeline_id)
    
    # Get credit profile to check verification status (no redirect)
    credit_profile = CreditProfile.query.filter_by(user_id=current_user.id).first()
    verification_status = {
        'is_verified': credit_profile.verified if credit_profile else False,
        'message': 'Your profile is verified.' if credit_profile and credit_profile.verified else 'Your profile is not verified, but you can still access the marketplace and auto-allocate tradelines to AI Agents.'
    }
    
    # Verify tradeline is available for purchase
    if not tradeline.is_for_sale or tradeline.owner_id == current_user.id:
        flash('This tradeline is not available for purchase', 'danger')
        return redirect(url_for('marketplace'))
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if request.method == 'POST':
        # Validate CSRF token
        if form.validate_on_submit():
            # Process purchase (in a real app, this would handle payment)
            purchase = TradelinePurchase(
                tradeline_id=tradeline.id,
                purchaser_id=current_user.id,
                is_rental=False,
                price_paid=tradeline.sale_price,
                allocated_limit=tradeline.available_limit
            )
            
            # Update tradeline availability
            tradeline.is_for_sale = False
            
            db.session.add(purchase)
            db.session.commit()
            
            flash('Tradeline purchased successfully!', 'success')
            return redirect(url_for('purchased_tradelines'))
        else:
            flash('CSRF validation failed. Please try again.', 'danger')
            return redirect(url_for('purchase_tradeline', tradeline_id=tradeline_id))
    
    return render_template('marketplace/purchase.html', 
                          tradeline=tradeline,
                          form=form,
                          active_page='marketplace')

@app.route('/validate-promo-code', methods=['POST'])
@login_required
def validate_promo_code():
    """API endpoint to validate a promo code"""
    data = request.json
    code_text = data.get('code')
    tradeline_id = data.get('tradeline_id')
    
    # Import the validation function from the promo_codes module
    from modules.promo_codes import validate_promo_code as validate_code
    
    promo_code, error_message = validate_code(code_text)
    
    if promo_code:
        # Code is valid
        return jsonify({
            'valid': True,
            'discount_percentage': promo_code.discount_percentage,
            'message': f'Promo code applied: {promo_code.discount_percentage}% discount!'
        })
    else:
        # Code is invalid
        return jsonify({
            'valid': False,
            'message': error_message or 'Invalid promo code.'
        })

@app.route('/marketplace/rent/<int:tradeline_id>', methods=['GET', 'POST'])
@login_required
def rent_tradeline(tradeline_id):
    """Rent a tradeline"""
    tradeline = Tradeline.query.get_or_404(tradeline_id)
    
    # Get credit profile to check verification status (no redirect)
    credit_profile = CreditProfile.query.filter_by(user_id=current_user.id).first()
    verification_status = {
        'is_verified': credit_profile.verified if credit_profile else False,
        'message': 'Your profile is verified.' if credit_profile and credit_profile.verified else 'Your profile is not verified, but you can still access the marketplace and auto-allocate tradelines to AI Agents.'
    }
    
    # Verify tradeline is available for rent
    if not tradeline.is_for_rent or tradeline.owner_id == current_user.id:
        flash('This tradeline is not available for rent', 'danger')
        return redirect(url_for('marketplace'))
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if request.method == 'POST':
        # Validate CSRF token
        if form.validate_on_submit():
            # Get rental details
            rental_months = int(request.form.get('rental_months', 1))
            
            # Get promo code if provided
            promo_code_text = request.form.get('promo_code', '').strip().upper()
            promo_code = None
            discount_percentage = 0
            original_price = tradeline.rental_price * rental_months
            final_price = original_price
            
            # Validate promo code if provided
            if promo_code_text:
                from modules.promo_codes import validate_promo_code
                promo_code, error_message = validate_promo_code(promo_code_text)
                
                if promo_code:
                    # Calculate discount
                    discount_percentage = promo_code.discount_percentage
                    final_price = original_price * (1 - discount_percentage / 100)
                    
                    # Increment promo code usage
                    promo_code.current_uses += 1
                    db.session.add(promo_code)
                elif error_message:
                    flash(f'Promo code error: {error_message}', 'warning')
            
            # Calculate rental period
            rental_start_date = datetime.utcnow()
            rental_end_date = rental_start_date + timedelta(days=rental_months * 30)  # Approximately 30 days per month
            
            # Create rental (in a real app, this would handle payment)
            rental = TradelinePurchase(
                tradeline_id=tradeline.id,
                purchaser_id=current_user.id,
                is_rental=True,
                rental_start_date=rental_start_date,
                rental_end_date=rental_end_date,
                price_paid=final_price,
                original_price=original_price if discount_percentage > 0 else None,
                allocated_limit=tradeline.available_limit,
                promo_code_id=promo_code.id if promo_code else None
            )
            
            db.session.add(rental)
            db.session.commit()
            
            # Success message with or without promo code
            if promo_code:
                flash(f'Tradeline rented successfully with {discount_percentage}% discount!', 'success')
            else:
                flash('Tradeline rented successfully!', 'success')
                
            return redirect(url_for('purchased_tradelines'))
        else:
            flash('CSRF validation failed. Please try again.', 'danger')
            return redirect(url_for('rent_tradeline', tradeline_id=tradeline_id))
    
    return render_template('marketplace/rent.html', 
                          tradeline=tradeline,
                          form=form,
                          verification_status=verification_status,
                          active_page='marketplace')

@app.route('/purchased-tradelines')
@login_required
def purchased_tradelines():
    """View purchased tradelines"""
    purchases = TradelinePurchase.query.filter_by(purchaser_id=current_user.id).all()
    return render_template('tradelines/purchased.html',
                          purchases=purchases,
                          active_page='purchased_tradelines')

# E-commerce marketplace routes removed to focus exclusively on tradeline marketplace
# @app.route('/marketplace/products')
# @login_required
# def product_list():
#     """View products by category"""
#     try:
#         category_id = request.args.get('category_id', type=int)
#         
#         # Get all categories for the navigation
#         categories = ProductCategory.query.all()
#         
#         if category_id:
#             category = ProductCategory.query.get_or_404(category_id)
#             products = Product.query.filter_by(category_id=category_id).all()
#             title = f"{category.name} Products"
#         else:
#             products = Product.query.all()
#             category = None
#             title = "All Products"
#         
#         # Get user agents for purchasing
#         user_agents = AIAgent.query.filter_by(owner_id=current_user.id, is_active=True).all()
#         
#         return render_template('marketplace/product_list.html',
#                              products=products,
#                              category=category,
#                              categories=categories,
#                              title=title,
#                              user_agents=user_agents,
#                              marketplace_type='ecommerce',
#                              active_page='marketplace')
#     except (NameError, ImportError):
#         flash("E-commerce marketplace is not yet available. Please run the setup script first.", "warning")
#         return redirect(url_for('marketplace'))

# @app.route('/marketplace/product/<int:product_id>')
# @login_required
# def product_detail(product_id):
#     """View product details"""
#     try:
#         product = Product.query.get_or_404(product_id)
#         category = product.category
#         
#         # Get similar products in the same category
#         similar_products = Product.query.filter(
#             Product.category_id == category.id,
#             Product.id != product_id
#         ).limit(4).all()
#         
#         # Get user agents for purchasing
#         user_agents = AIAgent.query.filter_by(owner_id=current_user.id, is_active=True).all()
#         
#         return render_template('marketplace/product_detail.html',
#                              product=product,
#                              category=category,
#                              similar_products=similar_products,
#                              user_agents=user_agents,
#                              marketplace_type='ecommerce',
#                              active_page='marketplace')
#     except (NameError, ImportError):
#         flash("E-commerce marketplace is not yet available. Please run the setup script first.", "warning")
#         return redirect(url_for('marketplace'))

# @app.route('/create-checkout-session', methods=['POST'])
# @login_required
# def create_checkout_session():
#     """Create a Stripe Checkout Session for product purchase"""
#     try:
#         # Get product and agent info from form
#         product_id = request.form.get('product_id', type=int)
#         agent_id = request.form.get('agent_id', type=int)
#         
#         if not product_id or not agent_id:
#             flash("Missing product or agent information", "warning")
#             return redirect(url_for('marketplace'))
#         
#         # Store in session for use after checkout completes
#         session['checkout_product_id'] = product_id
#         session['checkout_agent_id'] = agent_id
#         
#         # Get product details
#         product = Product.query.get_or_404(product_id)
#         agent = AIAgent.query.get_or_404(agent_id)
#         
#         # Get domain for success/cancel URLs
#         # In production environment, check for secure domain; in development, use current domain
#         if os.environ.get('REPLIT_DEPLOYMENT'):
#             domain = os.environ.get('REPLIT_DEV_DOMAIN')
#         else:
#             domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
#             
#         # Format price for Stripe (in cents)
#         stripe_price = int(product.price * 100)
#             
#         # Create checkout session
#         checkout_session = stripe.checkout.Session.create(
#             payment_method_types=['card'],
#             line_items=[
#                 {
#                     'price_data': {
#                         'currency': 'usd',
#                         'product_data': {
#                             'name': product.name,
#                             'description': f"Purchase using AI Agent: {agent.name}",
#                             'images': [product.image_url] if product.image_url else [],
#                         },
#                         'unit_amount': stripe_price,
#                     },
#                     'quantity': 1,
#                 },
#             ],
#             mode='payment',
#             success_url=f'https://{domain}/checkout-success',
#             cancel_url=f'https://{domain}/checkout-cancel',
#             client_reference_id=str(current_user.id),
#             metadata={
#                 'product_id': product_id,
#                 'agent_id': agent_id
#             }
#         )
#         
#         # Redirect to Stripe checkout
#         return redirect(checkout_session.url, code=303)
#     except Exception as e:
#         app.logger.error(f"Error creating checkout session: {str(e)}")
#         flash(f"Error processing payment: {str(e)}", "danger")
#         return redirect(url_for('marketplace'))

# @app.route('/checkout-success')
# @login_required
# def checkout_success():
#     """Handle successful Stripe checkout"""
#     try:
#         # Get product and agent IDs from session
#         product_id = session.get('checkout_product_id')
#         agent_id = session.get('checkout_agent_id')
#         
#         if not product_id or not agent_id:
#             flash("Payment successful, but product information was lost. Please contact support.", "warning")
#             return redirect(url_for('marketplace'))
#         
#         # Process the purchase using existing logic
#         product = Product.query.get_or_404(product_id)
#         agent = AIAgent.query.get_or_404(agent_id)
#         
#         # Find tradeline with enough credit
#         allocations = AIAgentAllocation.query.filter_by(agent_id=agent.id, is_active=True).all()
#         
#         if not allocations:
#             flash("Payment successful, but your AI agent has no active tradelines to use.", "warning")
#             return render_template('marketplace/success.html')
#         
#         # Find a tradeline with enough available limit
#         valid_allocation = None
#         for allocation in allocations:
#             # Get total spent on this allocation
#             spent = db.session.query(db.func.sum(Transaction.amount)).filter_by(
#                 tradeline_allocation_id=allocation.id
#             ).scalar() or 0
#             
#             available = allocation.credit_limit - spent
#             
#             if available >= product.price:
#                 valid_allocation = allocation
#                 break
#         
#         if not valid_allocation:
#             flash("Payment successful, but your AI agent doesn't have enough credit.", "warning")
#             return render_template('marketplace/success.html')
#         
#         # Create transaction and product purchase records
#         transaction = Transaction(
#             agent_id=agent.id,
#             tradeline_allocation_id=valid_allocation.id,
#             amount=product.price,
#             merchant=f"E-commerce: {product.brand}",
#             description=f"Purchase of {product.name}",
#             status="completed",
#             transaction_date=datetime.utcnow()
#         )
#         db.session.add(transaction)
#         
#         purchase = ProductPurchase(
#             product_id=product_id,
#             agent_id=agent.id,
#             purchase_date=datetime.utcnow(),
#             quantity=1,
#             price_paid=product.price,
#             transaction_id=None,  # Will set after flush
#             shipping_status="processing",
#             shipping_address="Default Address"  # Would get from user in a real app
#         )
#         db.session.add(purchase)
#         db.session.flush()  # Flush to get transaction ID
#         
#         purchase.transaction_id = transaction.id
#         
#         # Update product stock
#         product.stock_quantity -= 1
#         if product.stock_quantity <= 0:
#             product.in_stock = False
#         
#         # Update agent's credit score
#         agent.update_credit_score()
#         
#         db.session.commit()
#         
#         # Clear session data
#         session.pop('checkout_product_id', None)
#         session.pop('checkout_agent_id', None)
#         
#         return render_template('marketplace/success.html')
#     except Exception as e:
#         app.logger.error(f"Error processing successful checkout: {str(e)}")
#         flash(f"Payment was successful, but error occurred while processing your purchase: {str(e)}", "warning")
#         return render_template('marketplace/success.html')
# 
# @app.route('/checkout-cancel')
# @login_required
# def checkout_cancel():
#     """Handle cancelled Stripe checkout"""
#     # Clear session data
#     session.pop('checkout_product_id', None)
#     session.pop('checkout_agent_id', None)
#     
#     return render_template('marketplace/cancel.html')

# @app.route('/marketplace/purchase-product/<int:product_id>', methods=['POST'])
# @login_required
# def purchase_product(product_id):
#     """Purchase a product with an AI agent"""
#     try:
#         product = Product.query.get_or_404(product_id)
#         agent_id = request.form.get('agent_id', type=int)
#         
#         if not agent_id:
#             flash("Please select an AI agent to make this purchase.", "warning")
#             return redirect(url_for('product_detail', product_id=product_id))
#         
#         agent = AIAgent.query.get_or_404(agent_id)
#         
#         # Check if agent belongs to current user
#         if agent.owner_id != current_user.id:
#             flash("You can only use your own AI agents for purchases.", "danger")
#             return redirect(url_for('product_detail', product_id=product_id))
#         
#         # Check if product is in stock
#         if not product.in_stock or product.stock_quantity < 1:
#             flash("This product is currently out of stock.", "warning")
#             return redirect(url_for('product_detail', product_id=product_id))
#         
#         # Get agent's tradeline allocations
#         allocations = AIAgentAllocation.query.filter_by(agent_id=agent.id, is_active=True).all()
#         
#         if not allocations:
#             flash("This AI agent has no active tradelines to use for purchase.", "warning")
#             return redirect(url_for('product_detail', product_id=product_id))
#         
#         # Find a tradeline with enough available limit
#         valid_allocation = None
#         for allocation in allocations:
#             # Get total spent on this allocation
#             spent = db.session.query(db.func.sum(Transaction.amount)).filter_by(
#                 tradeline_allocation_id=allocation.id
#             ).scalar() or 0
#             
#             available = allocation.credit_limit - spent
#             
#             if available >= product.price:
#                 valid_allocation = allocation
#                 break
#         
#         if not valid_allocation:
#             flash("Your AI agent doesn't have enough available credit to purchase this product.", "warning")
#             return redirect(url_for('product_detail', product_id=product_id))
#         
#         # Create transaction record
#         transaction = Transaction(
#             agent_id=agent.id,
#             tradeline_allocation_id=valid_allocation.id,
#             amount=product.price,
#             merchant=f"E-commerce: {product.brand}",
#             description=f"Purchase of {product.name}",
#             status="completed",
#             transaction_date=datetime.utcnow()
#         )
#         db.session.add(transaction)
#         
#         # Create product purchase record
#         purchase = ProductPurchase(
#             product_id=product.id,
#             agent_id=agent.id,
#             purchase_date=datetime.utcnow(),
#             quantity=1,
#             price_paid=product.price,
#             transaction_id=None,  # Will set after transaction is committed
#             shipping_status="processing",
#             shipping_address="Default Address"  # In a real app, you'd get this from the user
#         )
#         db.session.add(purchase)
#         db.session.flush()  # Flush to get transaction ID
#         
#         # Update purchase with transaction ID
#         purchase.transaction_id = transaction.id
#         
#         # Update product stock
#         product.stock_quantity -= 1
#         if product.stock_quantity <= 0:
#             product.in_stock = False
#         
#         # Update agent's credit score based on this transaction
#         agent.update_credit_score()
#         
#         db.session.commit()
#         
#         flash(f"Successfully purchased {product.name} using your AI agent {agent.name}!", "success")
#         return redirect(url_for('purchased_products'))
#     except (NameError, ImportError):
#         flash("E-commerce marketplace is not yet available. Please run the setup script first.", "warning")
#         return redirect(url_for('marketplace'))
# 
# @app.route('/purchased-products')
# @login_required
# def purchased_products():
#     """View purchased products"""
#     try:
#         # Get all user's agents
#         user_agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
#         
#         if not user_agents:
#             flash("You need to create AI agents to make purchases.", "info")
#             return redirect(url_for('ai_agents'))
#         
#         # Get all purchases by user's agents
#         agent_ids = [agent.id for agent in user_agents]
#         purchases = ProductPurchase.query.filter(ProductPurchase.agent_id.in_(agent_ids)).order_by(
#             ProductPurchase.purchase_date.desc()
#         ).all()
#         
#         return render_template('marketplace/purchased_products.html',
#                              purchases=purchases,
#                              agents=user_agents,
#                              marketplace_type='ecommerce',
#                              active_page='marketplace')
#     except (NameError, ImportError):
#         flash("E-commerce marketplace is not yet available. Please run the setup script first.", "warning")
#         return redirect(url_for('marketplace'))

# E-commerce marketplace has been removed to focus exclusively on tradeline marketplace

# AI Agent Routes
@app.route('/api-dashboard-manager')
@login_required
def api_dashboard_manager():
    """View and manage API access for external platforms"""
    # Import API models
    from models.api import APIKey, APIUsage, APISubscription
    
    # Get user's API keys
    api_keys = []
    current_subscription = None
    api_usage = []
    total_requests = 0
    rate_limit_used = 0
    avg_response_time = 0
    usage_dates = []
    daily_usage = []
    
    try:
        # Try to get API keys from database
        api_keys = APIKey.query.filter_by(user_id=current_user.id).all()
        
        # Get the active subscription
        subscription = APISubscription.query.filter_by(
            user_id=current_user.id, 
            status='active'
        ).order_by(APISubscription.created_at.desc()).first()
        
        # If any API keys exist, get usage statistics
        if api_keys:
            # Get usage data from the last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # Get all API usage records for the user's keys
            api_usage = APIUsage.query.filter(
                APIUsage.api_key_id.in_([key.id for key in api_keys]),
                APIUsage.timestamp >= thirty_days_ago
            ).order_by(APIUsage.timestamp.asc()).all()
            
            # Calculate total requests
            total_requests = len(api_usage)
            
            # Calculate average response time
            if api_usage:
                avg_response_time = round(sum(u.response_time_ms for u in api_usage if u.response_time_ms) / 
                                 len([u for u in api_usage if u.response_time_ms]) if [u for u in api_usage if u.response_time_ms] else 0, 2)
            
            # Calculate rate limit usage
            active_keys = [key for key in api_keys if key.is_active and key.is_subscription_active()]
            if active_keys:
                # Get the tier with the highest rate limit
                highest_tier_key = max(active_keys, key=lambda k: {'basic': 1, 'pro': 2, 'enterprise': 3}.get(k.tier, 0))
                tier_limits = {'basic': 1000, 'pro': 5000, 'enterprise': 20000}
                
                # Calculate percentage of rate limit used in the last 24 hours
                day_ago = datetime.utcnow() - timedelta(days=1)
                day_usage = APIUsage.query.filter(
                    APIUsage.api_key_id.in_([key.id for key in active_keys]),
                    APIUsage.timestamp >= day_ago
                ).count()
                
                rate_limit = tier_limits.get(highest_tier_key.tier, 1000)
                rate_limit_used = round(day_usage / rate_limit * 100, 2)
            
            # Prepare chart data
            # Group usage by day
            usage_by_day = {}
            for usage in api_usage:
                day = usage.timestamp.strftime('%Y-%m-%d')
                if day not in usage_by_day:
                    usage_by_day[day] = 0
                usage_by_day[day] += 1
            
            # Fill in missing days
            current_date = thirty_days_ago.date()
            end_date = datetime.utcnow().date()
            while current_date <= end_date:
                day_str = current_date.strftime('%Y-%m-%d')
                if day_str not in usage_by_day:
                    usage_by_day[day_str] = 0
                current_date += timedelta(days=1)
            
            # Sort by date
            sorted_days = sorted(usage_by_day.keys())
            usage_dates = sorted_days
            daily_usage = [usage_by_day[day] for day in sorted_days]
    
    except Exception as e:
        app.logger.error(f"Error fetching API data: {str(e)}")
        
    return render_template('api_dashboard/index.html',
                          api_keys=api_keys,
                          current_subscription=current_subscription,
                          api_usage=api_usage,
                          total_requests=total_requests,
                          rate_limit_used=rate_limit_used,
                          avg_response_time=avg_response_time,
                          usage_dates=usage_dates,
                          daily_usage=daily_usage,
                          active_page='api_dashboard')

@app.route('/api-docs-manager')
@login_required
def api_docs_manager():
    """View API documentation"""
    from models.api import APIKey
    return render_template('api_dashboard/documentation.html',
                          active_page='api_docs')

@app.route('/create-api-key', methods=['POST'])
@login_required
def create_api_key():
    """Create a new API key for a user"""
    import hashlib
    import uuid
    from models.api import APIKey
    
    # Generate a new API key
    api_key = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    
    # Create new API key record
    key = APIKey(
        user_id=current_user.id,
        key=api_key,
        tier='basic',  # Default to basic tier
        is_active=True
    )
    
    # Save to database
    db.session.add(key)
    db.session.commit()
    
    # Flash success message
    flash(f'New API key created: {api_key}', 'success')
    
    # Redirect back to API dashboard
    return redirect(url_for('api_dashboard_manager'))

@app.route('/revoke-api-key/<int:key_id>', methods=['POST'])
@login_required
def revoke_api_key(key_id):
    """Revoke an API key"""
    from models.api import APIKey
    
    # Find the API key
    key = APIKey.query.filter_by(id=key_id, user_id=current_user.id).first()
    if not key:
        flash('API key not found', 'danger')
        return redirect(url_for('api_dashboard_manager'))
    
    # Mark as inactive
    key.is_active = False
    db.session.commit()
    
    # Flash success message
    flash('API key revoked successfully', 'success')
    
    # Redirect back to API dashboard
    return redirect(url_for('api_dashboard_manager'))

@app.route('/create-subscription/<tier>', methods=['POST'])
@login_required
def create_subscription(tier):
    """Create a new subscription for API access"""
    import stripe
    from models.api import APISubscription
    
    if tier not in ['basic', 'pro', 'enterprise']:
        flash('Invalid tier selected', 'danger')
        return redirect(url_for('api_dashboard_manager'))
    
    # Set up prices for different tiers
    price_ids = {
        'basic': 'price_1NrTiJLkdIwHu7ixMxmd0VNI',  # Free tier (actually $0)
        'pro': 'price_1NrTjZLkdIwHu7ixkRCkUzwl',    # Pro tier ($49/month)
        'enterprise': 'price_1NrTkOLkdIwHu7ixaT2JYwuH'  # Enterprise tier ($199/month)
    }
    
    # Set domain for Stripe redirects
    DOMAIN = os.environ.get('REPLIT_DEV_DOMAIN') if os.environ.get('REPLIT_DEPLOYMENT') != '' else os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
    
    # Create Stripe checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price_ids[tier],
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f'https://{DOMAIN}/subscription-success?tier={tier}&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'https://{DOMAIN}/api-dashboard',
        )
    except Exception as e:
        flash(f'Error creating subscription: {str(e)}', 'danger')
        return redirect(url_for('api_dashboard_manager'))
    
    # Redirect to Stripe checkout
    return redirect(checkout_session.url, code=303)

@app.route('/ai-agents')
@login_required
def ai_agents():
    """View user's AI agents"""
    agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
    return render_template('ai-agents/list.html',
                          agents=agents,
                          active_page='ai_agents')

@app.route('/ai-agents/create', methods=['GET', 'POST'])
@login_required
def create_agent():
    """Create a new AI agent"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    from modules.crypto_wallet import CryptoWalletManager
    from datetime import datetime
    
    form = FlaskForm()
    
    if request.method == 'POST':
        # Validate CSRF token
        if form.validate_on_submit():
            name = request.form.get('name')
            description = request.form.get('description')
            purpose = request.form.get('purpose')
            risk_profile = request.form.get('risk_profile')
            auto_allocate = request.form.get('auto_allocate') == 'on'
            network = request.form.get('network', 'mainnet')
            
            # Create a new Base Layer 2 blockchain wallet for the agent
            try:
                wallet_address = CryptoWalletManager.create_agent_wallet(network=network)
            except Exception as e:
                app.logger.error(f"Error creating wallet: {str(e)}")
                wallet_address = f"0x{hash(datetime.utcnow().isoformat())&0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF}"
                app.logger.info(f"Generated fallback wallet address: {wallet_address}")
            
            agent = AIAgent(
                owner_id=current_user.id,
                name=name,
                description=description,
                purpose=purpose,
                risk_profile=risk_profile,
                wallet_address=wallet_address,
                wallet_network=network,
                wallet_created_date=datetime.utcnow()
            )
            
            db.session.add(agent)
            db.session.commit()
            
            # Auto-allocate tradelines based on agent purpose and risk profile
            if auto_allocate:
                allocated_tradelines = 0
                
                # Function to score and match tradelines
                def score_tradeline(tradeline, purpose, risk_profile):
                    tradeline_score = 0
                    
                    # Match by purpose (simple keyword matching)
                    purpose_keywords = {
                        'shopping': ['retail', 'shopping', 'consumer', 'purchase'],
                        'investment': ['investment', 'stocks', 'finance', 'business'],
                        'travel': ['travel', 'airline', 'hotel', 'vacation'],
                        'bills': ['utility', 'bills', 'household'],
                        'entertainment': ['entertainment', 'leisure', 'dining']
                    }
                    
                    # Check if tradeline issuer or name matches purpose
                    purpose_matched = False
                    for key, keywords in purpose_keywords.items():
                        if key.lower() in purpose.lower():
                            for keyword in keywords:
                                if (keyword.lower() in tradeline.name.lower() or 
                                    keyword.lower() in tradeline.issuer.lower() or
                                    (tradeline.description and keyword.lower() in tradeline.description.lower()) or
                                    keyword.lower() in tradeline.account_type.lower()):
                                    tradeline_score += 30
                                    purpose_matched = True
                                    break
                    
                    # If no specific match, give small score for general purpose
                    if not purpose_matched:
                        tradeline_score += 10
                    
                    # Match by risk profile
                    risk_mapping = {
                        'Low': ['low', 'safe', 'secure'],
                        'Medium': ['medium', 'balanced', 'moderate'],
                        'High': ['high', 'risky', 'aggressive']
                    }
                    
                    # Get risk assessment for the tradeline
                    risk_data = ml_analytics.predict_tradeline_risk({
                        'credit_limit': tradeline.credit_limit,
                        'available_limit': tradeline.available_limit,
                        'interest_rate': tradeline.interest_rate,
                        'account_type': tradeline.account_type
                    })
                    
                    tradeline_risk = risk_data.get('risk_category', 'Medium')
                    
                    # Score based on risk match
                    if tradeline_risk == risk_profile:
                        tradeline_score += 40
                    elif (tradeline_risk == 'Low' and risk_profile == 'Medium') or \
                         (tradeline_risk == 'Medium' and risk_profile == 'High'):
                        tradeline_score += 20
                    
                    # Consider credit limit (allocate higher limits to higher risk)
                    if risk_profile == 'High' and tradeline.credit_limit > 10000:
                        tradeline_score += 20
                    elif risk_profile == 'Medium' and 5000 <= tradeline.credit_limit <= 15000:
                        tradeline_score += 20
                    elif risk_profile == 'Low' and tradeline.credit_limit < 10000:
                        tradeline_score += 20
                        
                    return tradeline_score
                
                # First, check if user has purchased tradelines
                purchased_tradelines = TradelinePurchase.query.filter_by(
                    purchaser_id=current_user.id,
                    is_active=True
                ).all()
                
                # Process user's purchased tradelines
                for purchase in purchased_tradelines:
                    # Skip if we've allocated enough tradelines already
                    if allocated_tradelines >= 3:
                        break
                        
                    # Get the tradeline
                    tradeline = purchase.tradeline
                    
                    # Skip if already allocated to this agent
                    existing_allocation = AIAgentAllocation.query.filter_by(
                        agent_id=agent.id,
                        tradeline_id=tradeline.id,
                        is_active=True
                    ).first()
                    
                    if existing_allocation:
                        continue
                    
                    # Score and match the tradeline
                    tradeline_score = score_tradeline(tradeline, purpose, risk_profile)
                    
                    # If tradeline is a good match (score > 50), allocate it
                    if tradeline_score > 50:
                        # Determine allocation amount based on risk profile
                        allocation_percentage = 0.7  # Default 70%
                        if risk_profile == 'Low':
                            allocation_percentage = 0.5  # 50% for low risk
                        elif risk_profile == 'High':
                            allocation_percentage = 0.9  # 90% for high risk
                        
                        # Calculate allocation amount
                        allocation_amount = purchase.allocated_limit * allocation_percentage
                        
                        # Create allocation
                        allocation = AIAgentAllocation(
                            agent_id=agent.id,
                            tradeline_id=tradeline.id,
                            credit_limit=allocation_amount,
                            spending_rules=f"Auto-allocated based on purpose: {purpose} and risk profile: {risk_profile}"
                        )
                        
                        db.session.add(allocation)
                        allocated_tradelines += 1
                
                # If no allocations yet, check marketplace tradelines
                if allocated_tradelines == 0:
                    # Find the marketplace user
                    marketplace_user = User.query.filter_by(username='marketplace').first()
                    
                    if marketplace_user:
                        # Get tradelines from marketplace
                        marketplace_tradelines = Tradeline.query.filter_by(
                            owner_id=marketplace_user.id,
                            is_active=True
                        ).all()
                        
                        # Sort marketplace tradelines by match score
                        scored_tradelines = []
                        for tradeline in marketplace_tradelines:
                            score = score_tradeline(tradeline, purpose, risk_profile)
                            scored_tradelines.append((tradeline, score))
                        
                        # Sort by score (highest first)
                        scored_tradelines.sort(key=lambda x: x[1], reverse=True)
                        
                        # Take top 3 with score > 50
                        for tradeline, score in scored_tradelines:
                            if score > 50 and allocated_tradelines < 3:
                                # Determine allocation amount based on risk profile
                                allocation_percentage = 0.1  # Only 10% for marketplace tradelines
                                if risk_profile == 'Low':
                                    allocation_percentage = 0.05  # 5% for low risk
                                elif risk_profile == 'High':
                                    allocation_percentage = 0.15  # 15% for high risk
                                
                                # Calculate allocation amount
                                allocation_amount = tradeline.available_limit * allocation_percentage
                                
                                # Create a purchase record first (special rental case)
                                purchase = TradelinePurchase(
                                    tradeline_id=tradeline.id,
                                    purchaser_id=current_user.id,
                                    is_rental=True,
                                    rental_start_date=datetime.utcnow(),
                                    rental_end_date=datetime.utcnow().replace(month=datetime.utcnow().month+1),
                                    price_paid=tradeline.rental_price,
                                    allocated_limit=allocation_amount,
                                    is_active=True
                                )
                                
                                db.session.add(purchase)
                                db.session.commit()  # Commit to get the purchase id
                                
                                # Create allocation
                                allocation = AIAgentAllocation(
                                    agent_id=agent.id,
                                    tradeline_id=tradeline.id,
                                    credit_limit=allocation_amount,
                                    spending_rules=f"Auto-allocated marketplace tradeline based on purpose: {purpose} and risk profile: {risk_profile}"
                                )
                                
                                db.session.add(allocation)
                                allocated_tradelines += 1
                
                db.session.commit()
                
                if allocated_tradelines > 0:
                    flash(f'AI Agent created successfully with {allocated_tradelines} automatically allocated tradelines', 'success')
                else:
                    flash('AI Agent created successfully but no matching tradelines were found for auto-allocation', 'success')
            else:
                flash('AI Agent created successfully', 'success')
                
            return redirect(url_for('ai_agents'))
        else:
            flash('CSRF validation failed. Please try again.', 'danger')
            return redirect(url_for('create_agent'))
    
    return render_template('ai-agents/create.html',
                          form=form,
                          active_page='ai_agents')

@app.route('/ai-agents/<int:agent_id>')
@login_required
def agent_detail(agent_id):
    """View AI agent details"""
    from modules.crypto_wallet import CryptoWalletManager
    from modules.defi_lending import DefiLendingManager
    from datetime import datetime, timedelta
    
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('ai_agents'))
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    # Get tradeline allocations
    allocations = AIAgentAllocation.query.filter_by(agent_id=agent.id).all()
    
    # Get available tradelines (purchased but not allocated to this agent)
    available_tradelines = []
    purchased_tradelines = TradelinePurchase.query.filter_by(
        purchaser_id=current_user.id,
        is_active=True
    ).all()
    
    for purchase in purchased_tradelines:
        # Check if this tradeline is already allocated to this agent
        existing_allocation = AIAgentAllocation.query.filter_by(
            agent_id=agent.id,
            tradeline_id=purchase.tradeline_id,
            is_active=True
        ).first()
        
        if not existing_allocation:
            available_tradelines.append({
                'purchase': purchase,
                'tradeline': purchase.tradeline
            })
    
    # Get credit score trend and rating
    credit_trend = agent.get_credit_score_trend()
    credit_rating = agent.get_credit_rating()
    
    # Add refresh score functionality
    if request.args.get('refresh_score'):
        score_data = agent.update_credit_score()
        db.session.commit()
        flash(f'Credit score updated: {agent.credit_score} ({credit_rating})', 'success')
        return redirect(url_for('agent_detail', agent_id=agent.id))
    
    # Toggle wallet network
    if request.args.get('toggle_network'):
        try:
            new_network = CryptoWalletManager.toggle_network(agent)
            db.session.commit()
            flash(f'Wallet network switched to {new_network}', 'success')
        except Exception as e:
            app.logger.error(f"Error toggling wallet network: {str(e)}")
            new_network = 'testnet' if agent.wallet_network == 'mainnet' else 'mainnet'
            agent.wallet_network = new_network
            db.session.commit()
            flash(f'Wallet network switched to {new_network}', 'success')
        return redirect(url_for('agent_detail', agent_id=agent.id))
    
    # Create a new wallet if one doesn't exist
    if not agent.wallet_address:
        network = agent.wallet_network or 'mainnet'
        try:
            agent.wallet_address = CryptoWalletManager.create_agent_wallet(network=network)
        except Exception as e:
            app.logger.error(f"Error creating wallet: {str(e)}")
            agent.wallet_address = f"0x{hash(datetime.utcnow().isoformat())&0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF}"
            app.logger.info(f"Generated fallback wallet address: {agent.wallet_address}")
        
        agent.wallet_created_date = datetime.utcnow()
        db.session.commit()
        flash(f'New {network} wallet created for this agent', 'success')
    
    # Get blockchain explorer URL for the wallet
    try:
        explorer_url = CryptoWalletManager.get_explorer_url(
            agent.wallet_address, 
            network=agent.wallet_network
        ) if agent.wallet_address else None
    except Exception as e:
        app.logger.error(f"Error getting explorer URL: {str(e)}")
        explorer_url = f"https://{'sepolia.' if agent.wallet_network == 'testnet' else ''}basescan.org/address/{agent.wallet_address}"
    
    # Get real wallet balances
    wallet_balances = {
        'eth': 0.0,
        'usdc': 0.0
    }
    
    # Keep track of when the wallet was last refreshed
    wallet_refresh_time = None
    
    # Check if we need to refresh balances
    refresh_balances = request.args.get('refresh_balance') is not None
    
    if agent.wallet_address and (refresh_balances or agent.wallet_balance is None):
        try:
            balance_data = CryptoWalletManager.get_wallet_balances(
                agent.wallet_address, 
                network=agent.wallet_network
            )
            
            if balance_data.get('success'):
                wallet_balances = {
                    'eth': balance_data.get('eth', 0.0),
                    'usdc': balance_data.get('usdc', 0.0)
                }
                
                # Update the agent's wallet_balance field with USDC balance
                agent.wallet_balance = wallet_balances['usdc']
                
                # Save current time as refresh time
                wallet_refresh_time = datetime.utcnow()
                agent.wallet_last_refresh = wallet_refresh_time
                db.session.commit()
                
                app.logger.info(f"Retrieved wallet balances: {wallet_balances}")
                
                if refresh_balances:
                    flash('Wallet balances refreshed successfully', 'success')
            else:
                app.logger.error(f"Error getting wallet balances: {balance_data.get('error')}")
                if refresh_balances:
                    flash(f"Failed to refresh wallet balances: {balance_data.get('error')}", 'danger')
        except Exception as e:
            app.logger.error(f"Error getting wallet balances: {str(e)}")
            if refresh_balances:
                flash(f"Failed to refresh wallet balances: {str(e)}", 'danger')
    elif agent.wallet_address:
        # Use stored wallet balance for USDC if available
        if agent.wallet_balance is not None:
            wallet_balances['usdc'] = agent.wallet_balance
        
        # Use the last refresh time if available
        wallet_refresh_time = agent.wallet_last_refresh
    
    # Get recent transactions and repayments for credit analysis
    transactions = Transaction.query.filter_by(agent_id=agent.id).order_by(Transaction.transaction_date.desc()).limit(5).all()
    repayments = Repayment.query.filter_by(agent_id=agent.id).order_by(Repayment.due_date.desc()).limit(5).all()
    
    # DeFi lending information
    from modules.defi_lending import defi_lending_manager
    
    # Get DeFi loan options
    loan_options = defi_lending_manager.get_loan_options(agent.id)
    
    # Default values in case of error
    max_loan_amount = 0
    available_providers = []
    available_terms = []
    min_apy = 0
    
    if loan_options.get('success'):
        # Extract loan data from response
        loan_options_list = loan_options.get('loan_options', [])
        
        # Calculate maximum loan amount from all options
        max_loan_amount = 0
        available_providers = []
        available_terms = []
        unique_terms = set()
        
        # Calculate minimum APY among all options
        min_apy = 99.99  # Start with a high value
        
        # Process and enhance the loan options
        for i, option in enumerate(loan_options_list):
            # Generate a unique ID for each option
            option['id'] = i + 1
            
            # Add interest_rate as APY for display
            option['apy'] = option.get('interest_rate', 0)
            
            # Calculate monthly payment
            amount = option.get('max_amount', 0) / 2  # Use half of max for a reasonable example
            term_days = option.get('term_days', 30)
            interest_rate = option.get('interest_rate', 5.0)
            
            # Simple calculation for monthly payment
            total_interest = amount * (interest_rate / 100) * (term_days / 365)
            total_repayment = amount + total_interest
            
            # Calculate monthly payment (approximate for display)
            monthly_payment = total_repayment / (term_days / 30)
            
            # Add calculated fields to the option
            option['amount'] = amount
            option['total_interest'] = total_interest
            option['total_repayment'] = total_repayment
            option['monthly_payment'] = monthly_payment
            
            # Track maximum loan amount
            max_loan_amount = max(max_loan_amount, option.get('max_amount', 0))
            
            # Track providers
            provider_id = option.get('provider', '')
            provider_name = option.get('provider_name', provider_id.capitalize())
            
            # Add to available providers if not already there
            if not any(p.get('id') == provider_id for p in available_providers):
                available_providers.append({
                    'id': provider_id,
                    'name': provider_name,
                    'description': f"{provider_name} DeFi Protocol"
                })
            
            # Track term days
            term = option.get('term_days', 0)
            if term > 0 and term not in unique_terms:
                unique_terms.add(term)
                available_terms.append({
                    'days': term,
                    'name': f"{term} Days" if term <= 30 else f"{term//30} Month{'s' if term//30 > 1 else ''}"
                })
            
            # Track minimum APY
            option_apy = option.get('interest_rate', min_apy)
            if option_apy < min_apy:
                min_apy = option_apy
        
        # Sort terms by duration (ascending)
        available_terms.sort(key=lambda x: x['days'])
    
    # Check if wallet was refreshed recently (within last 5 minutes)
    wallet_refresh_time_recent = wallet_refresh_time and (datetime.utcnow() - wallet_refresh_time).total_seconds() < 300
    
    return render_template('ai-agents/detail.html',
                          agent=agent,
                          allocations=allocations,
                          available_tradelines=available_tradelines,
                          form=form,
                          active_page='ai_agents',
                          credit_trend=credit_trend,
                          credit_rating=credit_rating,
                          transactions=transactions,
                          repayments=repayments,
                          Transaction=Transaction,
                          explorer_url=explorer_url,
                          wallet_balances=wallet_balances,
                          wallet_refresh_time=wallet_refresh_time,
                          wallet_refresh_time_recent=wallet_refresh_time_recent,
                          # DeFi lending variables
                          max_loan_amount=max_loan_amount,
                          available_providers=available_providers,
                          available_terms=available_terms,
                          min_apy=min_apy)

@app.route('/ai-agents/<int:agent_id>/parameters', methods=['POST'])
@login_required
def update_agent_parameters(agent_id):
    """Update AI agent parameters"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        
        # Ensure user owns this agent
        if agent.owner_id != current_user.id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        # Update agent parameters
        agent.name = request.form.get('name')
        agent.description = request.form.get('description')
        agent.purpose = request.form.get('purpose')
        agent.risk_profile = request.form.get('risk_profile')
        agent.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Agent parameters updated successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/allocation/<int:allocation_id>/toggle', methods=['POST'])
@login_required
def toggle_allocation_status(agent_id, allocation_id):
    """Toggle the active status of a tradeline allocation"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        allocation = AIAgentAllocation.query.get_or_404(allocation_id)
        
        # Ensure user owns this agent and allocation
        if agent.owner_id != current_user.id or allocation.agent_id != agent_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        # Toggle active status
        allocation.is_active = not allocation.is_active
        db.session.commit()
        
        status = "activated" if allocation.is_active else "deactivated"
        flash(f'Tradeline {status} successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/allocation/<int:allocation_id>/update', methods=['POST'])
@login_required
def update_allocation(agent_id, allocation_id):
    """Update a tradeline allocation"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        allocation = AIAgentAllocation.query.get_or_404(allocation_id)
        
        # Ensure user owns this agent and allocation
        if agent.owner_id != current_user.id or allocation.agent_id != agent_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        # Update allocation
        allocation.credit_limit = float(request.form.get('credit_limit'))
        allocation.spending_rules = request.form.get('spending_rules')
        allocation.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Tradeline allocation updated successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/repayment/schedule', methods=['POST'])
@login_required
def schedule_repayment(agent_id):
    """Schedule a new repayment for an agent"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        
        # Ensure user owns this agent
        if agent.owner_id != current_user.id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        allocation_id = request.form.get('allocation_id')
        allocation = AIAgentAllocation.query.get_or_404(allocation_id)
        
        # Ensure allocation belongs to this agent
        if allocation.agent_id != agent_id:
            flash('Invalid tradeline allocation', 'danger')
            return redirect(url_for('agent_detail', agent_id=agent_id))
        
        # Create new repayment
        repayment = Repayment(
            agent_id=agent_id,
            tradeline_allocation_id=allocation_id,
            amount=float(request.form.get('amount')),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d'),
            status='scheduled',
            description=request.form.get('description')
        )
        
        db.session.add(repayment)
        db.session.commit()
        
        flash('Repayment scheduled successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/repayment/<int:repayment_id>/update', methods=['POST'])
@login_required
def update_repayment(agent_id, repayment_id):
    """Update a scheduled repayment"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        repayment = Repayment.query.get_or_404(repayment_id)
        
        # Ensure user owns this agent and repayment
        if agent.owner_id != current_user.id or repayment.agent_id != agent_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        # Ensure repayment is in scheduled status
        if repayment.status != 'scheduled':
            flash('Only scheduled repayments can be updated', 'warning')
            return redirect(url_for('agent_detail', agent_id=agent_id))
        
        # Update repayment
        repayment.amount = float(request.form.get('amount'))
        repayment.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
        repayment.description = request.form.get('description')
        
        db.session.commit()
        flash('Repayment updated successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/repayment/<int:repayment_id>/process', methods=['POST'])
@login_required
def process_repayment(agent_id, repayment_id):
    """Process a scheduled repayment (mark as paid)"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        repayment = Repayment.query.get_or_404(repayment_id)
        
        # Ensure user owns this agent and repayment
        if agent.owner_id != current_user.id or repayment.agent_id != agent_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        # Ensure repayment is in scheduled status
        if repayment.status != 'scheduled':
            flash('This repayment has already been processed', 'warning')
            return redirect(url_for('agent_detail', agent_id=agent_id))
        
        # Process repayment
        repayment.status = 'paid'
        repayment.payment_date = datetime.utcnow()
        
        # Update credit score based on repayment
        agent.update_credit_score()
        
        db.session.commit()
        flash('Repayment processed successfully', 'success')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/allocate', methods=['POST'])
@login_required
def allocate_tradeline(agent_id):
    """Allocate a tradeline to an AI agent"""
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('ai_agents'))
    
    # Validate CSRF token
    if form.validate_on_submit():
        tradeline_id = request.form.get('tradeline_id')
        credit_limit = float(request.form.get('credit_limit', 0))
        spending_rules = request.form.get('spending_rules', '')
        
        # Verify tradeline ownership
        purchase = TradelinePurchase.query.filter_by(
            tradeline_id=tradeline_id,
            purchaser_id=current_user.id,
            is_active=True
        ).first()
        
        if not purchase:
            flash('You do not have access to this tradeline', 'danger')
            return redirect(url_for('agent_detail', agent_id=agent.id))
        
        # Check if credit limit is valid
        if credit_limit <= 0 or credit_limit > purchase.allocated_limit:
            flash(f'Invalid credit limit. Maximum available: ${purchase.allocated_limit}', 'danger')
            return redirect(url_for('agent_detail', agent_id=agent.id))
        
        # Create allocation
        allocation = AIAgentAllocation(
            agent_id=agent.id,
            tradeline_id=tradeline_id,
            credit_limit=credit_limit,
            spending_rules=spending_rules
        )
        
        db.session.add(allocation)
        db.session.commit()
        
        flash('Tradeline allocated to AI agent successfully', 'success')
    else:
        flash('CSRF validation failed. Please try again.', 'danger')
    
    return redirect(url_for('agent_detail', agent_id=agent.id))

@app.route('/ai-agents/<int:agent_id>/transaction', methods=['POST'])
@login_required
@csrf.exempt
def agent_transaction(agent_id):
    """Process a transaction from an AI agent"""
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    # Validate CSRF token from header
    token = request.headers.get('X-CSRFToken')
    if not token or not validate_csrf(token):
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.json
    allocation_id = data.get('allocation_id')
    amount = data.get('amount')
    merchant = data.get('merchant')
    description = data.get('description')
    
    # Verify allocation
    allocation = AIAgentAllocation.query.get(allocation_id)
    if not allocation or allocation.agent_id != agent.id:
        return jsonify({'error': 'Invalid allocation'}), 400
    
    # In a real app, validate spending rules and credit limit
    if amount > allocation.credit_limit:
        return jsonify({'error': 'Amount exceeds credit limit'}), 400
    
    # Get current balance from the most recent transaction
    latest_transaction = Transaction.query.filter_by(
        tradeline_allocation_id=allocation.id
    ).order_by(Transaction.transaction_date.desc()).first()
    
    current_balance = 0
    if latest_transaction and latest_transaction.balance_after is not None:
        current_balance = latest_transaction.balance_after
    
    # Calculate new balance
    new_balance = current_balance + amount
    
    # Create transaction with updated balance
    transaction = Transaction(
        agent_id=agent.id,
        tradeline_allocation_id=allocation.id,
        amount=amount,
        merchant=merchant,
        description=description,
        balance_after=new_balance
    )
    
    db.session.add(transaction)
    
    # Create a repayment record for this transaction (due in 30 days)
    due_date = datetime.utcnow() + timedelta(days=30)
    repayment = Repayment(
        agent_id=agent.id,
        tradeline_allocation_id=allocation.id,
        amount=amount,
        due_date=due_date,
        description=f"Payment for transaction at {merchant}"
    )
    
    db.session.add(repayment)
    db.session.commit()
    
    # Update the agent's credit score after transaction
    agent.update_credit_score()
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'transaction_id': transaction.id
    })

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    app.logger.warning(f"Page not found: {request.path}")
    return render_template('error.html', 
                          error_code=404,
                          error_message="The page you're looking for doesn't exist.",
                          active_page=None,
                          error="Please check the URL and try again."), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server error: {e}")
    return render_template('error.html', 
                          error_code=500,
                          error_message="An internal server error occurred. Please try again later.",
                          active_page=None,
                          error="Internal server error"), 500

# DeFi Lending Routes
@app.route('/defi-loans', methods=['GET'])
@login_required
def defi_loans():
    """Main DeFi loans page with all agents and their loans"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Get all agents for the current user
    all_agents = AIAgent.query.filter_by(owner_id=current_user.id).all()
    
    # Separate agents with and without loans
    agents_with_loans = []
    agents_without_loans = []
    
    active_loans = 0
    total_borrowed = 0
    total_interest = 0
    collateral_value = 0
    
    for agent in all_agents:
        # Get agent's loans
        loans = DefiLoan.query.filter_by(agent_id=agent.id).all()
        
        if loans:
            # Enhance agent object with loan details
            agent.defi_loans = loans
            agents_with_loans.append(agent)
            
            # Update stats
            for loan in loans:
                if loan.status == 'active':
                    active_loans += 1
                    total_borrowed += loan.amount
                    total_interest += loan.total_interest
                
                if loan.has_collateral and loan.collateral_amount:
                    collateral_value += loan.collateral_amount
        else:
            # Calculate credit utilization for agents without loans
            allocations = AIAgentAllocation.query.filter_by(agent_id=agent.id, is_active=True).all()
            total_limit = sum(a.credit_limit for a in allocations)
            # Default to 0 for total_used since we don't have a field for that
            total_used = 0
            
            if total_limit > 0:
                agent.credit_utilization = total_used / total_limit
            else:
                agent.credit_utilization = 0
            
            agents_without_loans.append(agent)
    
    # Calculate average interest rate
    avg_interest_rate = 0
    if active_loans > 0:
        avg_interest_rate = total_interest / total_borrowed
    
    return render_template(
        'defi_loans/index.html',
        active_page='defi_loans',
        all_agents=all_agents,
        agents_with_loans=agents_with_loans,
        agents_without_loans=agents_without_loans,
        active_loans=active_loans,
        total_borrowed=total_borrowed,
        avg_interest_rate=avg_interest_rate,
        collateral_value=collateral_value
    )

@app.route('/defi-loans/<int:agent_id>/create', methods=['POST'])
@login_required
def create_defi_loan_from_available(agent_id):
    """Create a new DeFi loan from available options"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Verify agent belongs to current user
    agent = AIAgent.query.filter_by(id=agent_id, owner_id=current_user.id).first_or_404()
    
    # Get form data
    provider = request.form.get('provider')
    token = request.form.get('token')
    amount = float(request.form.get('amount'))
    term_days = int(request.form.get('term_days'))
    auto_collateral = request.form.get('auto_collateral') == 'on'
    
    # Validate inputs
    if not all([provider, token, amount, term_days]):
        flash('Invalid loan parameters', 'danger')
        return redirect(url_for('defi_loans'))
    
    # Get collateral tradelines based on auto selection or manual selection
    collateral_allocation_id = None
    collateral_amount = 0
    
    if auto_collateral:
        # Auto-select collateral based on loan amount
        collateral_info = defi_lending_manager.get_auto_collateral(agent_id, amount)
        
        if collateral_info['success'] and collateral_info['collateral']:
            collateral = collateral_info['collateral']
            collateral_allocation_id = collateral['allocation_id']
            collateral_amount = collateral['amount']
        else:
            flash(f"Error: {collateral_info.get('error', 'Unable to select collateral automatically')}", 'danger')
            return redirect(url_for('defi_loans'))
    else:
        # Use manually selected collateral
        collateral_ids = request.form.get('collateral_ids', '').split(',')
        if collateral_ids and collateral_ids[0]:
            allocation_id = int(collateral_ids[0])
            allocation = AIAgentAllocation.query.get(allocation_id)
            
            if allocation and allocation.agent_id == agent_id:
                collateral_allocation_id = allocation_id
                collateral_amount = float(request.form.get('collateral_amount', 0))
            else:
                flash('Invalid collateral selection', 'danger')
                return redirect(url_for('defi_loans'))
    
    # Create loan
    result = defi_lending_manager.create_loan(
        agent_id=agent_id,
        provider=provider,
        token=token,
        amount=amount,
        term_days=term_days,
        collateral_allocation_id=collateral_allocation_id,
        collateral_amount=collateral_amount
    )
    
    if result['success']:
        flash('DeFi loan created successfully! Funds have been deposited to your agent\'s wallet.', 'success')
    else:
        flash(f"Error: {result.get('error', 'Unknown error creating loan')}", 'danger')
    
    return redirect(url_for('defi_loans'))

@app.route('/defi-loans/<int:agent_id>/create-custom', methods=['POST'])
@login_required
def create_custom_defi_loan(agent_id):
    """Create a custom DeFi loan with user-specified parameters"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Verify agent belongs to current user
    agent = AIAgent.query.filter_by(id=agent_id, owner_id=current_user.id).first_or_404()
    
    # Get form data
    provider = request.form.get('provider')
    token = request.form.get('token')
    amount = float(request.form.get('amount'))
    term_days = int(request.form.get('term_days'))
    auto_collateral = request.form.get('auto_collateral') == 'on'
    
    # Validate inputs
    if not all([provider, token, amount, term_days]):
        flash('Invalid loan parameters', 'danger')
        return redirect(url_for('defi_loans'))
    
    # Get collateral details (similar to regular loan creation)
    collateral_allocation_id = None
    collateral_amount = 0
    
    if auto_collateral:
        # Auto-select collateral based on loan amount
        collateral_info = defi_lending_manager.get_auto_collateral(agent_id, amount)
        
        if collateral_info['success'] and collateral_info['collateral']:
            collateral = collateral_info['collateral']
            collateral_allocation_id = collateral['allocation_id']
            collateral_amount = collateral['amount']
        else:
            flash(f"Error: {collateral_info.get('error', 'Unable to select collateral automatically')}", 'danger')
            return redirect(url_for('defi_loans'))
    else:
        # Use manually selected collateral
        collateral_ids = request.form.get('collateral_ids', '').split(',')
        if collateral_ids and collateral_ids[0]:
            allocation_id = int(collateral_ids[0])
            allocation = AIAgentAllocation.query.get(allocation_id)
            
            if allocation and allocation.agent_id == agent_id:
                collateral_allocation_id = allocation_id
                collateral_amount = float(request.form.get('collateral_amount', 0))
            else:
                flash('Invalid collateral selection', 'danger')
                return redirect(url_for('defi_loans'))
    
    # Create custom loan with market-determined interest rate
    result = defi_lending_manager.create_custom_loan(
        agent_id=agent_id,
        provider=provider,
        token=token,
        amount=amount,
        term_days=term_days,
        collateral_allocation_id=collateral_allocation_id,
        collateral_amount=collateral_amount
    )
    
    if result['success']:
        flash('Custom DeFi loan created successfully! Funds have been deposited to your agent\'s wallet.', 'success')
    else:
        flash(f"Error: {result.get('error', 'Unknown error creating custom loan')}", 'danger')
    
    return redirect(url_for('defi_loans'))

@app.route('/defi-loans/<int:agent_id>/pay/<int:loan_id>', methods=['POST'])
@login_required
def process_defi_loan_payment(agent_id, loan_id):
    """Process a payment for a DeFi loan"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Verify agent belongs to current user
    agent = AIAgent.query.filter_by(id=agent_id, owner_id=current_user.id).first_or_404()
    
    # Verify loan belongs to agent
    loan = DefiLoan.query.filter_by(id=loan_id, agent_id=agent_id).first_or_404()
    
    # Get payment amount
    amount = float(request.form.get('amount', 0))
    
    if amount <= 0:
        flash('Payment amount must be greater than zero', 'danger')
        return redirect(url_for('defi_loans'))
    
    # Process payment
    result = defi_lending_manager.process_payment(agent_id, loan_id, amount)
    
    if result['success']:
        flash('Payment processed successfully!', 'success')
    else:
        flash(f"Error: {result.get('error', 'Unknown error processing payment')}", 'danger')
    
    return redirect(url_for('defi_loans'))

# API endpoints for DeFi loans
@app.route('/api/agents/<int:agent_id>/loan-options', methods=['GET'])
@login_required
def get_loan_options_api(agent_id):
    """API to get available loan options for an AI agent"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Verify agent belongs to current user
    agent = AIAgent.query.filter_by(id=agent_id, owner_id=current_user.id).first_or_404()
    
    # Get loan options
    loan_options = defi_lending_manager.get_loan_options(agent_id)
    
    if not loan_options['success']:
        return jsonify({
            'success': False,
            'error': loan_options.get('error', 'Unknown error')
        }), 400
    
    # Format loan options for the API response
    formatted_options = []
    
    for option in loan_options.get('loan_options', []):
        formatted_options.append({
            'provider': option.get('provider'),
            'provider_name': option.get('provider_name'),
            'token': option.get('token'),
            'term_days': option.get('term_days'),
            'min_amount': option.get('min_amount'),
            'max_amount': option.get('max_amount'),
            'interest_rate': option.get('interest_rate'),
            'total_interest': option.get('total_interest'),
            'repayment_amount': option.get('repayment_amount'),
            'repayment_schedule': option.get('repayment_schedule'),
            'collateral_required': option.get('collateral_required', False),
            'collateral_ratio': option.get('collateral_ratio', 0),
            'provider_logo': option.get('provider_logo')
        })
    
    return jsonify({
        'success': True,
        'agent': {
            'id': agent.id,
            'name': agent.name,
            'credit_score': agent.credit_score,
            'wallet_address': agent.wallet_address,
            'wallet_balance': agent.wallet_balance
        },
        'loan_options': formatted_options
    })

@app.route('/api/agents/<int:agent_id>/auto-collateral', methods=['GET'])
@login_required
def get_auto_collateral_api(agent_id):
    """API to get automatically selected collateral for a loan amount"""
    # Import DeFi lending manager
    from modules.defi_lending import defi_lending_manager
    
    # Verify agent belongs to current user
    agent = AIAgent.query.filter_by(id=agent_id, owner_id=current_user.id).first_or_404()
    
    # Get loan amount from query string
    amount = request.args.get('amount')
    if not amount:
        return jsonify({'success': False, 'error': 'Loan amount is required'}), 400
    
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid loan amount'}), 400
    
    # Get collateral info
    collateral_result = defi_lending_manager.get_auto_collateral(agent_id, amount)
    
    if not collateral_result['success']:
        return jsonify({
            'success': False,
            'error': collateral_result.get('error', 'Unable to find suitable collateral')
        }), 400
    
    return jsonify({
        'success': True,
        'collateral': collateral_result.get('collateral', {}),
        'credit_score': agent.credit_score,
        'credit_tier': collateral_result.get('credit_tier', 'Unknown'),
        'collateral_ratio': collateral_result.get('collateral_ratio', 0),
        'required_amount': collateral_result.get('required_amount', 0)
    })

@app.route('/agents/<int:agent_id>/loan-options', methods=['GET'])
@login_required
def get_loan_options(agent_id):
    """Get available loan options for an AI agent"""
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('ai_agents'))
    
    from modules.defi_lending import defi_lending_manager
    
    # Get loan options
    loan_options = defi_lending_manager.get_loan_options(agent_id)
    
    if not loan_options['success']:
        flash(f"Error: {loan_options.get('error', 'Unknown error')}", 'danger')
        return redirect(url_for('agent_detail', agent_id=agent_id))
    
    return render_template(
        'ai-agents/defi_loan_options.html',
        agent=agent,
        loan_options=loan_options,
        active_page="ai_agents"
    )

@app.route('/ai-agents/<int:agent_id>/defi-loan/auto-collateral', methods=['GET'])
@login_required
def get_auto_collateral(agent_id):
    """Get automatically selected collateral for a loan amount based on agent's credit score"""
    from modules.defi_lending import defi_lending_manager
    
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    # Get amount from query string
    amount = request.args.get('amount')
    if not amount:
        return jsonify({'error': 'Loan amount is required'}), 400
    
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({'error': 'Invalid loan amount'}), 400
    
    # Get available collateral options based on agent's credit score
    collateral_result = defi_lending_manager.get_available_tradeline_collateral(agent_id, amount)
    
    if not collateral_result['success']:
        return jsonify({'error': collateral_result.get('error', 'Unknown error')}), 400
    
    # Get auto-selected collateral from the result (optimized based on credit score)
    auto_selected = collateral_result.get('auto_selected', [])
    
    # Calculate total collateral value
    total_value = sum(item.get('value', 0) for item in auto_selected)
    
    return jsonify({
        'success': True,
        'auto_selected': auto_selected,
        'total_value': total_value,
        'required_amount': collateral_result.get('collateral_required', 0),
        'collateral_ratio': collateral_result.get('collateral_ratio', 0),
        'agent_credit_score': agent.credit_score,
        'credit_tier': collateral_result.get('agent', {}).get('credit_tier', 'Unknown'),
        'has_sufficient_collateral': collateral_result.get('has_sufficient_collateral', False)
    })

@app.route('/ai-agents/<int:agent_id>/defi-loan/create', methods=['POST'])
@login_required
def create_defi_loan(agent_id):
    """Create a new DeFi loan for an AI agent"""
    from modules.defi_lending import defi_lending_manager
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        
        # Ensure user owns this agent
        if agent.owner_id != current_user.id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        provider = request.form.get('provider')
        token = request.form.get('token')
        amount = float(request.form.get('amount'))
        term_days = int(request.form.get('term_days'))
        
        # Get collateral information if provided
        use_collateral = request.form.get('use_collateral') == 'on'
        allocation_ids = request.form.getlist('allocation_ids[]') if use_collateral else None
        
        try:
            # Get loan options to check if amount is valid
            loan_options = defi_lending_manager.get_loan_options(agent_id)
            if not loan_options['success']:
                flash(f"Error: {loan_options.get('error', 'Unknown error')}", 'danger')
                return redirect(url_for('agent_detail', agent_id=agent_id))
                
            # Find the selected loan option to check max amount
            valid_amount = False
            for option in loan_options.get('loan_options', []):
                if option['provider'] == provider and option['token'] == token and option['term_days'] == term_days:
                    if amount >= option['min_amount'] and amount <= option['max_amount']:
                        valid_amount = True
                    break
                    
            if not valid_amount:
                flash('Invalid loan amount for the selected option', 'danger')
                return redirect(url_for('agent_detail', agent_id=agent_id))
            
            # Process the loan
            loan_result = defi_lending_manager.create_loan(
                agent_id, 
                provider, 
                token, 
                amount, 
                term_days,
                allocation_ids
            )
            
            if loan_result['success']:
                if allocation_ids:
                    flash('DeFi loan with tradeline collateral created successfully. Funds have been added to your wallet.', 'success')
                else:
                    flash('DeFi loan created successfully. Funds have been added to your wallet.', 'success')
            else:
                flash(f"Unable to process loan: {loan_result.get('error', 'Unknown error')}", 'danger')
                
        except Exception as e:
            app.logger.error(f"Error creating DeFi loan: {str(e)}")
            flash(f'Error creating loan: {str(e)}', 'danger')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/tradeline-collateral', methods=['GET'])
@login_required
def get_available_collateral(agent_id):
    """Get available tradelines for use as collateral"""
    from modules.defi_lending import defi_lending_manager
    
    agent = AIAgent.query.get_or_404(agent_id)
    
    # Ensure user owns this agent
    if agent.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    # Get loan amount from query string
    loan_amount = request.args.get('amount')
    if not loan_amount:
        return jsonify({'error': 'Loan amount is required'}), 400
    
    try:
        loan_amount = float(loan_amount)
    except ValueError:
        return jsonify({'error': 'Invalid loan amount'}), 400
    
    # Get available collateral using the DeFi lending manager
    collateral_result = defi_lending_manager.get_available_tradeline_collateral(agent_id, loan_amount)
    
    return jsonify(collateral_result)

@app.route('/ai-agents/<int:agent_id>/defi-loan/<int:loan_id>/liquidate-collateral', methods=['POST'])
@login_required
def liquidate_loan_collateral(agent_id, loan_id):
    """Liquidate collateral for a defaulted loan"""
    from modules.defi_lending import defi_lending_manager
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        
        # Ensure user owns this agent
        if agent.owner_id != current_user.id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        loan = DefiLoan.query.get_or_404(loan_id)
        
        # Ensure loan belongs to this agent
        if loan.agent_id != agent.id:
            flash('Invalid loan', 'danger')
            return redirect(url_for('agent_detail', agent_id=agent.id))
        
        # Check if loan has collateral that can be liquidated
        if not loan.has_collateral or loan.collateral_liquidated:
            flash('This loan does not have collateral available for liquidation', 'warning')
            return redirect(url_for('agent_detail', agent_id=agent.id))
        
        try:
            # Process the liquidation
            result = defi_lending_manager.liquidate_collateral(loan_id)
            
            if result['success']:
                flash('Collateral liquidated successfully. Loan has been settled.', 'success')
                
                # Update agent's credit score
                agent.update_credit_score()
                db.session.commit()
            else:
                flash(f'Unable to liquidate collateral: {result.get("error", "Unknown error")}', 'danger')
                
        except Exception as e:
            app.logger.error(f"Error liquidating collateral: {str(e)}")
            flash(f'Error liquidating collateral: {str(e)}', 'danger')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))

@app.route('/ai-agents/<int:agent_id>/defi-loan/<int:loan_id>/repayment/process', methods=['POST'])
@login_required
def process_defi_payment(agent_id, loan_id):
    """Process a DeFi loan repayment"""
    from modules.defi_lending import defi_lending_manager
    
    # Create a simple form for CSRF protection
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        agent = AIAgent.query.get_or_404(agent_id)
        
        # Ensure user owns this agent
        if agent.owner_id != current_user.id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('ai_agents'))
        
        loan = DefiLoan.query.get_or_404(loan_id)
        
        # Ensure loan belongs to this agent
        if loan.agent_id != agent.id:
            flash('Invalid loan', 'danger')
            return redirect(url_for('agent_detail', agent_id=agent.id))
        
        # Get repayment amount from form
        amount = request.form.get('amount')
        if amount:
            amount = float(amount)
        
        try:
            # Process the repayment
            result = defi_lending_manager.repay_loan(loan_id, amount)
            
            if result['success']:
                flash('Payment processed successfully', 'success')
                
                # Update agent's credit score
                agent.update_credit_score()
                db.session.commit()
            else:
                flash(f"Unable to process payment: {result.get('error', 'Unknown error')}", 'danger')
                
        except Exception as e:
            app.logger.error(f"Error processing DeFi payment: {str(e)}")
            flash(f'Error processing payment: {str(e)}', 'danger')
    
    return redirect(url_for('agent_detail', agent_id=agent_id))



@app.route('/defi/loan/<int:loan_id>/check-liquidation', methods=['GET'])
@login_required
def check_loan_liquidation(loan_id):
    """Check the liquidation status of a loan's tradeline collateral"""
    from modules.defi_lending import defi_lending_manager
    
    # Get the loan and verify ownership
    loan = DefiLoan.query.get_or_404(loan_id)
    agent = AIAgent.query.get_or_404(loan.agent_id)
    
    if agent.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized access'}), 403
    
    if not loan.has_collateral:
        return jsonify({'error': 'This loan does not have collateral'}), 400
    
    # Get collateral data
    collateral_status = {
        'loan_id': loan.id,
        'has_collateral': loan.has_collateral,
        'collateral_allocation_id': loan.collateral_allocation_id,
        'collateral_amount': loan.collateral_amount,
        'collateral_liquidated': loan.collateral_liquidated,
        'liquidation_date': loan.liquidation_date.isoformat() if loan.liquidation_date else None,
        'is_active': loan.is_active
    }
    
    # If user requests to perform liquidation check
    if request.args.get('check') == 'true' and loan.has_collateral and not loan.collateral_liquidated:
        # Check if liquidation should be performed
        if request.args.get('liquidate') == 'true':
            try:
                liquidation_result = defi_lending_manager.liquidate_collateral(loan_id)
                collateral_status['liquidation_performed'] = True
                collateral_status['liquidation_result'] = liquidation_result
            except Exception as e:
                app.logger.error(f"Error during collateral liquidation: {str(e)}")
                collateral_status['liquidation_error'] = str(e)
    
    return jsonify(collateral_status)

@app.route('/defi/loan/notification', methods=['POST'])
@csrf.exempt  # Exempt for external automated notifications
def defi_loan_notification():
    """Endpoint for receiving notifications about DeFi loan events (like liquidations)"""
    from modules.defi_lending import defi_lending_manager
    
    # Validate request
    if not request.json:
        return jsonify({'error': 'Invalid request format, expected JSON'}), 400
    
    notification_type = request.json.get('type')
    loan_id = request.json.get('loan_id')
    
    if not notification_type or not loan_id:
        return jsonify({'error': 'Missing required fields: type and loan_id'}), 400
    
    # Process based on notification type
    if notification_type == 'collateral_check':
        # Check if loan collateral needs liquidation
        try:
            loan = DefiLoan.query.get(loan_id)
            if not loan:
                return jsonify({'error': 'Loan not found'}), 404
            
            if not loan.has_collateral or loan.collateral_liquidated:
                return jsonify({
                    'loan_id': loan_id,
                    'status': 'no_action_needed',
                    'reason': 'No active collateral to check'
                })
            
            # Check if collateral needs liquidation
            if not loan.is_collateral_sufficient():
                # Use the singleton defi_lending_manager
                liquidation_result = defi_lending_manager.liquidate_collateral(loan_id)
                
                # Record the liquidation event
                app.logger.info(f"Auto-liquidation performed for loan {loan_id}: {liquidation_result}")
                
                return jsonify({
                    'loan_id': loan_id,
                    'status': 'liquidation_performed',
                    'result': liquidation_result
                })
            else:
                return jsonify({
                    'loan_id': loan_id,
                    'status': 'collateral_sufficient',
                    'ratio': loan.collateral_to_loan_ratio()
                })
        
        except Exception as e:
            app.logger.error(f"Error processing collateral check notification: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    elif notification_type == 'payment_reminder':
        # Implementation for payment reminders
        return jsonify({'status': 'reminder_acknowledged'})
    
    else:
        return jsonify({'error': 'Unsupported notification type'}), 400

@app.route('/defi/maintenance/check-overdue-loans', methods=['POST'])
@login_required
def check_overdue_loans():
    """Administrative function to check and update status of overdue loans"""
    # Only allow admin users or users with special permissions to access this endpoint
    if not current_user.id == 1:  # Simple admin check (should be enhanced with proper role management)
        return jsonify({'error': 'Unauthorized access'}), 403
    
    from modules.defi_lending import defi_lending_manager
    
    try:
        # Use the singleton defi_lending_manager
        results = defi_lending_manager.check_overdue_loans()
        
        return jsonify({
            'status': 'success',
            'loans_checked': results.get('loans_checked', 0),
            'loans_updated': results.get('loans_updated', 0),
            'credit_scores_affected': results.get('credit_scores_affected', 0)
        })
    
    except Exception as e:
        app.logger.error(f"Error checking overdue loans: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/defi/payment/process-scheduled', methods=['POST'])
@csrf.exempt  # Exempt for automated scheduled jobs
def process_scheduled_payments():
    """Process scheduled DeFi loan payments that are due today"""
    from modules.defi_lending import defi_lending_manager
    from sqlalchemy import func
    
    # Verify special API key for automated jobs
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != os.environ.get('SCHEDULER_API_KEY'):
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        # Get all DefiRepayments scheduled for today that haven't been paid yet
        today = datetime.now().date()
        scheduled_payments = DefiRepayment.query.filter(
            func.date(DefiRepayment.due_date) == today,
            DefiRepayment.status == 'scheduled'
        ).all()
        
        results = {
            'total_scheduled': len(scheduled_payments),
            'successful_payments': 0,
            'failed_payments': 0,
            'details': []
        }
        
        for payment in scheduled_payments:
            try:
                # Find the agent for this loan
                loan = DefiLoan.query.get(payment.loan_id)
                agent = AIAgent.query.get(loan.agent_id)
                
                # Check if agent has enough wallet balance
                if agent.wallet_balance >= payment.amount:
                    # Process the payment using the singleton defi_lending_manager
                    payment_result = defi_lending_manager.process_scheduled_payment(payment.id)
                    
                    if payment_result.get('success', False):
                        results['successful_payments'] += 1
                        results['details'].append({
                            'payment_id': payment.id,
                            'loan_id': payment.loan_id,
                            'agent_id': agent.id,
                            'amount': payment.amount,
                            'status': 'paid'
                        })
                    else:
                        results['failed_payments'] += 1
                        results['details'].append({
                            'payment_id': payment.id,
                            'loan_id': payment.loan_id,
                            'agent_id': agent.id,
                            'amount': payment.amount,
                            'status': 'failed',
                            'reason': payment_result.get('error', 'Unknown error')
                        })
                else:
                    # Not enough balance - mark as missed
                    payment.status = 'missed'
                    db.session.commit()
                    
                    results['failed_payments'] += 1
                    results['details'].append({
                        'payment_id': payment.id,
                        'loan_id': payment.loan_id,
                        'agent_id': agent.id,
                        'amount': payment.amount,
                        'status': 'missed',
                        'reason': 'insufficient_balance'
                    })
            except Exception as e:
                app.logger.error(f"Error processing payment {payment.id}: {str(e)}")
                results['failed_payments'] += 1
                results['details'].append({
                    'payment_id': payment.id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return jsonify(results)
    
    except Exception as e:
        app.logger.error(f"Error in scheduled payments processing: {str(e)}")
        return jsonify({'error': str(e)}), 500



    
    if not collateral_result['success']:
        return jsonify({
            'error': collateral_result.get('error', 'Unable to get collateral options')
        }), 400
    
    # Format response for the UI
    auto_selected = collateral_result.get('auto_selected', [])
    
    # If we have auto-selected collateral, format it nicely for the UI
    collateral_info = None
    if auto_selected and len(auto_selected) > 0:
        # Calculate total collateral amount
        total_value = sum(item.get('value', 0) for item in auto_selected)
        
        # Get the first tradeline as the primary one
        primary_tradeline = auto_selected[0]
        
        collateral_info = {
            'tradeline_name': primary_tradeline.get('name', 'Unknown tradeline'),
            'collateral_amount': total_value,
            'tradeline_count': len(auto_selected),
            'is_multiple': len(auto_selected) > 1
        }
    
    # Format the response with detailed credit info
    return jsonify({
        'credit_score': agent.credit_score,
        'credit_tier': collateral_result.get('agent', {}).get('credit_tier', 'Unknown'),
        'collateral_required': collateral_result.get('collateral_required', 0),
        'collateral_ratio': collateral_result.get('collateral_ratio', 1.0),
        'has_sufficient_collateral': collateral_result.get('has_sufficient_collateral', False),
        'available_tradelines': collateral_result.get('available_tradelines', []),
        'total_available_collateral': collateral_result.get('total_available_collateral', 0),
        'collateral': collateral_info,
        'loan_details': collateral_result.get('loan_details', {})
    })
