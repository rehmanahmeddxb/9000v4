import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, PendingBill, Material, User
from werkzeug.security import generate_password_hash


def test_direct_sale_with_has_bill_unchecked_does_not_create_pending_bill():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        # ensure admin exists for login (handle legacy user schema)
        admin = User.query.filter_by(username='salechecker2').first()
        if not admin:
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'salechecker2',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='salechecker2', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
        # ensure material and client
        mat = Material.query.filter_by(name='Cement').first()
        if not mat:
            mat = Material(name='Cement', code='CEM3', unit_price=100.0)
            db.session.add(mat)
        client = Client.query.filter_by(code='HBT').first()
        if not client:
            client = Client(name='HasBillTest', code='HBT')
            db.session.add(client)
        db.session.commit()

        c = app.test_client()
        # login as admin
        resp = c.post('/login', data={'username': 'salechecker2', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        # Post a direct sale with has_bill unchecked (omit has_bill)
        post_data = {
            'client_code': 'HBT',
            'client_name': 'HasBillTest',
            'product_name[]': ['Cement'],
            'qty[]': ['1'],
            'unit_rate[]': ['100'],
            'amount': '100',
            'paid_amount': '0',
            'manual_bill_no': '',
            'has_bill': '0'  # explicitly unchecked
        }
        before = PendingBill.query.filter_by(client_code='HBT').count()
        resp = c.post('/add_direct_sale', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        after = PendingBill.query.filter_by(client_code='HBT').count()
        assert after == before, "No new pending bill should be created when has_bill is unchecked"
        return

        p = PendingBill.query.filter_by(client_code='HBT').all()
        assert len(p) == 0, "No pending bill should be created when has_bill is unchecked"