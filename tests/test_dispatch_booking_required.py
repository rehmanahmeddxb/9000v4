import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, Material, User
from werkzeug.security import generate_password_hash


def test_dispatch_requires_booking():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        # Create admin user
        admin = User.query.filter_by(username='testadmin2').first()
        if not admin:
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'testadmin2',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='testadmin2', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
                db.session.commit()

        # Create material and client without bookings
        mat = Material.query.filter_by(name='Bricks').first()
        if not mat:
            mat = Material(name='Bricks', code='BRK', unit_price=50.0)
            db.session.add(mat)
        client = Client.query.filter_by(code='CASH001').first()
        if not client:
            client = Client(name='CashClient', code='CASH001')
            db.session.add(client)
        db.session.commit()

        c = app.test_client()
        resp = c.post('/login', data={'username': 'testadmin2', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'type': 'OUT',
            'date': date.today().strftime('%Y-%m-%d'),
            'client': 'CashClient',
            'material': 'Bricks',
            'qty': '10',
        }
        resp = c.post('/add_record', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        assert b'No booking found for this client and material' in resp.data

        # Ensure no Entry created
        from models import Entry
        e = Entry.query.filter_by(client='CashClient').first()
        assert e is None
