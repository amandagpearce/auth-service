import os
from dotenv import load_dotenv
from flask_cors import CORS
from flask import Flask, jsonify
from flask_smorest import Api
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

from resources.user import blp as UserBlueprint
from models.token_blocklist import TokenBlocklistModel
from db import db


def create_app(db_url=None):  # factory pattern
    app = Flask(__name__)
    CORS(app)

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config["API_TITLE"] = "Authentication REST API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/doc"
    app.config[
        "OPENAPI_SWAGGER_UI_URL"
    ] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url or os.getenv(
        "DATABASE_URL",
        "sqlite:///data.db",  # if database_url is not found, default to sqlite
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)  # initializes sqlalchemy
    migrate = Migrate(app, db)  # noqa

    api = Api(app)

    load_dotenv()
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        tokenExists = TokenBlocklistModel.query.filter(
            TokenBlocklistModel.token == jwt_payload["jti"]
        ).first()

        return tokenExists

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {
                    "description": "Token is not fresh.",
                    "error": "fresh_token_required",
                }
            ),
            401,
        )

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return (
            jsonify(
                {"description": "Revoked token.", "error": "token_revoked"}
            ),
            401,
        )

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify(
            {
                "message": "Invalid Token.",
                "error": "invalid_token",
            },
            401,
        )

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify(
            {
                "message": "Signature verification failed.",
                "error": "invalid_token",
            },
            401,
        )

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify(
            {
                "description": "Request must contain access token.",
                "error": "authorization_required",
            },
            401,
        )

    with app.app_context():
        db.create_all()  # creating the dbs if they dont already exist

    api.register_blueprint(UserBlueprint)

    return app
