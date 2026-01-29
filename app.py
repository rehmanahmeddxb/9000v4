from flask import Flask, render_template
from models import db, User, Client, PendingBill, Entry, ReconBasket
from flask_login import LoginManager
from utils.module_loader import load_modules

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    # Auto-load and register all blueprints from blueprints directory
    load_modules(app, blueprint_dir='blueprints')

    @app.route('/')
    def index():
        total_stock = Entry.query.count()
        total_pending = PendingBill.query.count()
        return render_template('index.html', total_stock=total_stock, total_pending=total_pending)

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
