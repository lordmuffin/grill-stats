import os
import logging
from flask import Flask
import structlog
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from src.api.routes import register_routes
from src.database.timescale_manager import TimescaleManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize OpenTelemetry
from opentelemetry.sdk.trace import TracerProvider
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize instrumentation
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Initialize database connections with retries
try:
    timescale_manager = TimescaleManager(
        host=os.getenv('TIMESCALEDB_HOST', 'localhost'),
        port=int(os.getenv('TIMESCALEDB_PORT', '5432')),
        database=os.getenv('TIMESCALEDB_DATABASE', 'grill_monitoring'),
        username=os.getenv('TIMESCALEDB_USERNAME', 'grill_monitor'),
        password=os.getenv('TIMESCALEDB_PASSWORD', 'testpass')
    )
    logger.info("TimescaleDB connection initialized successfully")
except Exception as e:
    logger.warning(f"TimescaleDB connection failed: {e}, service will run in degraded mode")
    timescale_manager = None

# Register API routes
register_routes(app, timescale_manager)

if __name__ == '__main__':
    # Initialize database with retry
    if timescale_manager:
        try:
            timescale_manager.init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    # Start the application
    port = int(os.getenv('PORT', '8080'))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info("Starting Historical Data Service", 
               port=port, 
               debug=debug,
               timescaledb=bool(timescale_manager))
    
    app.run(host='0.0.0.0', port=port, debug=debug)