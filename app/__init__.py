from flask import Flask
from app.config import load_configurations, configure_logging
from .views import webhook_blueprint
from dotenv import load_dotenv
import os


def create_app():
    app = Flask(__name__)

    load_dotenv(override=True)
    app.config["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")
    app.config["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY")

    # Load configurations and logging settings
    load_configurations(app)
    configure_logging()

    # Import and register blueprints, if any
    app.register_blueprint(webhook_blueprint)

    return app
