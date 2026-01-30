import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Client, Material, User, Invoice, Booking, BookingItem
from werkzeug.security import generate_password_hash
from datetime import datetime


def test_auto_invoice_avoids_collision():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        # Create admin user
        admin = User.query.filter_by(username='testadmin3').first()
        if not admin:
            from sqlalchemy import text
            cols = [r[1] for r in db.session.execute(text("PRAGMA table_info('user')")).fetchall()]
            if 'password' in cols:
                db.session.execute(text(
                    "INSERT INTO user (username, password, password_hash, role, can_view_stock, can_view_daily, can_view_history, can_import_export, can_manage_directory) VALUES (:u, :p, :ph, :r, 1, 1, 1, 0, 0)"
                ), {
                    'u': 'testadmin3',
                    'p': 'testpass',
                    'ph': generate_password_hash('testpass'),
                    'r': 'admin'
                })
                db.session.commit()
            else:
                admin = User(username='testadmin3', password_hash=generate_password_hash('testpass'), role='admin')
                db.session.add(admin)
                db.session.commit()

        # Create two clients and a material
        a = Client.query.filter_by(code='A001').first()
        if not a:
            a = Client(name='ClientA', code='A001')
            db.session.add(a)
        b = Client.query.filter_by(code='B001').first()
        if not b:
            b = Client(name='ClientB', code='B001')
            db.session.add(b)
        mat = Material.query.filter_by(name='Tiles').first()
        if not mat:
            mat = Material(name='Tiles', code='TLS', unit_price=20.0)
            db.session.add(mat)
        db.session.commit()

        # Ensure client B has a booking for Tiles so dispatch is allowed
        bk = Booking(client_name=b.name, location='Site', amount=100, paid_amount=0, date_posted=datetime.now())
        db.session.add(bk)
        db.session.flush()
        db.session.add(BookingItem(booking_id=bk.id, material_name='Tiles', qty=10, price_at_time=20.0))
        db.session.commit()

        # Pre-create an invoice with the next auto number to force collision
        from main import get_next_bill_no
        next_no = get_next_bill_no()
        inv = Invoice(client_code=a.code, client_name=a.name, invoice_no=next_no, is_manual=True, total_amount=0, balance=0, created_at=date.today().strftime('%Y-%m-%d'), created_by='test')
        db.session.add(inv)
        db.session.commit()

        # Now perform an OUT dispatch for client B with create_invoice checked; code should skip the used number
        c = app.test_client()
        resp = c.post('/login', data={'username': 'testadmin3', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'type': 'OUT',
            'date': date.today().strftime('%Y-%m-%d'),
            'client': 'ClientB',
            'material': 'Tiles',
            'qty': '2',
            'create_invoice': '1'
        }
        resp = c.post('/add_record', data=post_data, follow_redirects=True)
        assert resp.status_code == 200

        # Verify an Invoice exists for ClientB with a different invoice_no than next_no
        inv_b = Invoice.query.filter(Invoice.client_code == b.code).first()
        assert inv_b is not None
        assert inv_b.invoice_no != next_no
