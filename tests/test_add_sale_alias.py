import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, Material, User
from werkzeug.security import generate_password_hash


def test_add_sale_alias_route():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username='saleadmin').first()
        if not admin:
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'saleadmin',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='saleadmin', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
                db.session.commit()

        # Create material and client
        mat = Material.query.filter_by(name='Blocks').first()
        if not mat:
            mat = Material(name='Blocks', code='BLK', unit_price=10.0)
            db.session.add(mat)
        client = Client.query.filter_by(code='CL001').first()
        if not client:
            client = Client(name='SaleClient', code='CL001')
            db.session.add(client)
        db.session.commit()

        c = app.test_client()
        resp = c.post('/login', data={'username': 'saleadmin', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'client_name': 'SaleClient',
            'product_name[]': ['Blocks'],
            'qty[]': ['5'],
            'unit_rate[]': ['10.0'],
            'amount': '50.0',
            'paid_amount': '50.0',
            'manual_bill_no': ''
        }
        resp = c.post('/add_sale', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Direct sale added successfully' in resp.data
