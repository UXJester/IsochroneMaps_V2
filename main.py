import logging
import os
import webbrowser
import sys

# Add src to path if needed (helpful for some environments)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# Import environment setup and logging utils first
from src.utils import load_env_variables
from src.utils.logging_utils import setup_structured_logging
from src.config import TABLES
from src.config.database import init_supabase, check_db_connection
from src.app import app


# Main application entry point
def main():
    # Load environment variables before any operations that might need them
    dotenv_path, env_loaded = load_env_variables(
        required_vars=["ORS_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    )
    if not env_loaded:
        logging.warning(
            f"Environment variables not loaded. .env file not found at {dotenv_path}"
        )

    # Configure logging with structured logging
    setup_structured_logging(log_file="main.log", level=logging.INFO)
    logging.info(f"Environment loaded: {env_loaded}")

    # Initialize Supabase client
    try:
        supabase = init_supabase()

        # Check database connection
        db_connection_status = check_db_connection(supabase)
        if not db_connection_status:
            logging.error(
                "Database connection check failed, but continuing application startup"
            )
        else:
            logging.info("Database connection successful")

        # Add Supabase client and tables to app configuration
        app.config["SUPABASE_CLIENT"] = supabase
        app.config["TABLES"] = TABLES
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")

    # Open browser for development convenience
    flask_env = os.environ.get("FLASK_ENV", "development")
    if flask_env == "development":
        webbrowser.open("http://localhost:8000")
        logging.info(f"Opening browser in {flask_env} mode")

    # Run the Flask app
    app.run(debug=True, host="localhost", port=8000, use_reloader=False)


if __name__ == "__main__":
    main()
