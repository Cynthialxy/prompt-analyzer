from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    CORS(app)

    from app.routes.data import data_bp
    from app.routes.analysis import analysis_bp
    from app.routes.pipeline import pipeline_bp
    from app.routes.analysis_v1 import analysis_v1_bp

    app.register_blueprint(data_bp, url_prefix="/api/data")
    app.register_blueprint(analysis_bp, url_prefix="/api/analysis")
    app.register_blueprint(pipeline_bp, url_prefix="/api/pipeline")
    app.register_blueprint(analysis_v1_bp, url_prefix="/api/v1/analysis")

    from app.services.cache_service import init_db
    init_db()

    return app
