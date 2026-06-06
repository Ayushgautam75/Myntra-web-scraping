"""Myntra Analytics Dashboard - Flask Application."""
import os

from flask import Flask, render_template
from flask_cors import CORS

from routes import api_bp
from src.config.config import config
from src.config.logger import logger


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api_bp)

    @app.route("/")
    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/products")
    @app.route("/reviews")
    @app.route("/analytics")
    @app.route("/recommendations")
    @app.route("/settings")
    def dashboard_sections():
        return render_template("dashboard.html")

    logger.info("[OK] Myntra Analytics Dashboard initialized")
    return app


app = create_app()

if __name__ == "__main__":
    # use_reloader=False prevents Windows hang / duplicate listeners on port 5000
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=False, host="127.0.0.1", port=port, threaded=True, use_reloader=False)
