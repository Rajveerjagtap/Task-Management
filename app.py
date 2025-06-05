from flask import Flask, render_template
from flask_swagger_ui import get_swaggerui_blueprint
import datetime
from models import db
from utils import create_access_token, jwt_required, get_jwt_identity
from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.profile import profile_bp

SWAGGER_URL = '/api/docs'  
API_URL = '/static/swagger.json'  

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://flaskuser:flaskpass@localhost:5432/flaskdb'
app.config['JWT_SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)

db.init_app(app)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  
    API_URL,
    config={  
        'app_name': "Test application"
    },
)
app.register_blueprint(swaggerui_blueprint)
app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(profile_bp)

@app.route('/')
def landing():
    return render_template('landing.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)