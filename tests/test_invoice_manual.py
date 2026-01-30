import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, Material, User, Entry
from werkzeug.security import generate_password_hash
from datetime import datetime


def test_manual_invoice_enforced():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        # Create admin user
        admin = User.query.filter_by(username='testadmin').first()
        if not admin:
            # Some older DB schemas still have a NOT NULL `password` column. Use raw SQL insert
            # when that column exists to avoid IntegrityError.
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'testadmin',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='testadmin', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
                db.session.commit()

        # Create material
        mat = Material.query.filter_by(name='Cement').first()
        if not mat:
            mat = Material(name='Cement', code='CEM', unit_price=100.0)
            db.session.add(mat)

        # Create client that requires manual invoice
        client = Client.query.filter_by(code='MC001').first()
        if not client:
            client = Client(name='ManualClient', code='MC001', require_manual_invoice=True)
            db.session.add(client)
        db.session.commit()

        # Add a booking for this client and material so the dispatch reaches the manual-invoice enforcement
        from models import Booking, BookingItem
        bk = Booking(client_name=client.name, location='Site', amount=500, paid_amount=0, date_posted=datetime.now())
        db.session.add(bk)
        db.session.flush()
        db.session.add(BookingItem(booking_id=bk.id, material_name='Cement', qty=20, price_at_time=100.0))
        db.session.commit()

        # Use test client to login and post a dispatch without bill_no
        c = app.test_client()
        resp = c.post('/login', data={'username': 'testadmin', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'type': 'OUT',
            'date': date.today().strftime('%Y-%m-%d'),
            'client': 'ManualClient',
            'material': 'Cement',
            'qty': '5',
            # no bill_no and no create_invoice
        }
        resp = c.post('/add_record', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Manual invoice required' in resp.data

        # Ensure no entry was created for this client
        e = Entry.query.filter_by(client='ManualClient').first()
        assert e is None
