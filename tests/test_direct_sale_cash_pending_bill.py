from app import create_app
from models import db, PendingBill, Client, Material, User
from werkzeug.security import generate_password_hash


def test_cash_direct_sale_creates_cash_pending_bill():
    app = create_app()
    app.testing = True

    with app.app_context():
        db.create_all()
        # ensure admin
        admin = User.query.filter_by(username='salechecker').first()
        if not admin:
            admin = User(username='salechecker', password_hash=generate_password_hash('testpass'), role='admin')
            db.session.add(admin)
        # ensure material
        mat = Material.query.filter_by(name='Cement').first()
        if not mat:
            mat = Material(name='Cement', code='CEM3', unit_price=100.0)
            db.session.add(mat)
        db.session.commit()

        c = app.test_client()
        resp = c.post('/login', data={'username': 'salechecker', 'password': 'testpass'}, follow_redirects=True)
        assert resp.status_code == 200

        post_data = {
            'category': 'Cash',
            'manual_client_name': 'CashCustomer',
            'product_name[]': ['Cement'],
            'qty[]': ['1'],
            'unit_rate[]': ['100'],
            'amount': '100',
            'paid_amount': '0',
            'manual_bill_no': ''
        }
        before = PendingBill.query.filter_by(client_name='CashCustomer', is_cash=True).count()
        resp = c.post('/add_direct_sale', data=post_data, follow_redirects=True)
        assert resp.status_code == 200
        after = PendingBill.query.filter_by(client_name='CashCustomer', is_cash=True).count()
        assert after == before + 1, "Unpaid cash sale should create a cash pending bill"