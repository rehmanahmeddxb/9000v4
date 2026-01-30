import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, Material, User, PendingBill, DirectSale
from werkzeug.security import generate_password_hash


def test_direct_sale_creates_pending_bill_when_unpaid():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username='salechecker').first()
        if not admin:
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'salechecker',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='salechecker', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
                db.session.commit()

        mat = Material.query.filter_by(name='Cement').first()
        if not mat:
            mat = Material(name='Cement', code='CEM2', unit_price=100.0)
            db.session.add(mat)
        client = Client.query.filter_by(code='CLX01').first()
        if not client:
            client = Client(name='SaleClientX', code='CLX01')
            db.session.add(client)
        db.session.commit()

        c = app.test_client()
        resp = c.post('/login', data={'username': 'salechecker', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'client_name': 'SaleClientX',
            'product_name[]': ['Cement'],
            'qty[]': ['3'],
            'unit_rate[]': ['100.0'],
            'amount': '300.0',
            'paid_amount': '0.0',
            'manual_bill_no': ''
        }
        resp = c.post('/add_direct_sale', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Direct sale added successfully' in resp.data

        # There should be a pending bill for the unpaid amount
        pb = PendingBill.query.filter_by(client_code=client.code).first()
        assert pb is not None
        assert abs(pb.amount - 300.0) < 0.01

        # The DirectSale entry should exist and appear in financial ledger
        ds = DirectSale.query.filter_by(client_name=client.name).first()
        assert ds is not None
