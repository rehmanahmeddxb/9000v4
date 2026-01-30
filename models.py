from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    can_view_stock = db.Column(db.Boolean, default=True)
    can_view_daily = db.Column(db.Boolean, default=True)
    can_view_history = db.Column(db.Boolean, default=True)
    can_import_export = db.Column(db.Boolean, default=False)
    can_manage_directory = db.Column(db.Boolean, default=False)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    category = db.Column(db.String(50), default='General') # Categories: General, Walking-Customer, Misc
    is_active = db.Column(db.Boolean, default=True)
    # If True, this client must always be given a manual invoice/bill number when dispatching
    require_manual_invoice = db.Column(db.Boolean, default=False)
    transferred_to_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)

class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)

class GRN(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supplier = db.Column(db.String(100))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    manual_bill_no = db.Column(db.String(50))
    auto_bill_no = db.Column(db.String(50))
    photo_path = db.Column(db.String(200))
    items = db.relationship('GRNItem', backref='grn', cascade="all, delete-orphan")

class GRNItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey('grn.id'))
    mat_name = db.Column(db.String(100))
    qty = db.Column(db.Float)
    price_at_time = db.Column(db.Float, default=0.0)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    location = db.Column(db.String(100))
    amount = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0.0)
    manual_bill_no = db.Column(db.String(50))
    auto_bill_no = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    photo_path = db.Column(db.String(200))
    items = db.relationship('BookingItem', backref='booking', cascade="all, delete-orphan")

class BookingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'))
    material_name = db.Column(db.String(100))
    qty = db.Column(db.Float, default=0.0)
    price_at_time = db.Column(db.Float, default=0.0)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    method = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    manual_bill_no = db.Column(db.String(50))
    auto_bill_no = db.Column(db.String(50))
    photo_path = db.Column(db.String(200))


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_code = db.Column(db.String(50), index=True)
    client_name = db.Column(db.String(100), index=True)
    invoice_no = db.Column(db.String(100), unique=True, index=True)
    is_manual = db.Column(db.Boolean, default=False)
    date = db.Column(db.Date)
    due_date = db.Column(db.Date, nullable=True)
    total_amount = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='OPEN')  # OPEN/PAID/PARTIAL/CANCELLED
    is_cash = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(20))
    created_by = db.Column(db.String(100))

class BillCounter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=1000)

class DirectSale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0.0)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    manual_bill_no = db.Column(db.String(50))
    auto_bill_no = db.Column(db.String(50))
    photo_path = db.Column(db.String(200))
    # Category for this sale (e.g., General, Walking-Customer, Cash)
    category = db.Column(db.String(50), index=True, nullable=True)
    # Optional link to Invoice when a Direct Sale is billed
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    invoice = db.relationship('Invoice', backref='direct_sales')
    items = db.relationship('DirectSaleItem', backref='direct_sale', cascade="all, delete-orphan")

class DirectSaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('direct_sale.id'))
    product_name = db.Column(db.String(100))
    qty = db.Column(db.Float, default=0.0)
    price_at_time = db.Column(db.Float, default=0.0)

class PendingBill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_code = db.Column(db.String(50), index=True)
    client_name = db.Column(db.String(100), index=True)
    bill_no = db.Column(db.String(100), index=True)
    nimbus_no = db.Column(db.String(100), index=True)
    amount = db.Column(db.Float, default=0)
    date = db.Column(db.Date)
    reason = db.Column(db.String(500))
    photo_url = db.Column(db.String(500))
    is_paid = db.Column(db.Boolean, default=False)
    # Indicates this pending bill was recorded for a cash delivery (no invoice)
    is_cash = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.String(20))
    created_by = db.Column(db.String(100))

class Entry(db.Model):
    __table_args__ = (
        db.Index('idx_entry_date_material', 'date', 'material'),
        db.Index('idx_entry_material_type', 'material', 'type'),
        db.Index('idx_entry_date_type', 'date', 'type'),
        db.Index('idx_entry_client_date', 'client', 'date'),
    )
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False, index=True)
    time = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False, index=True)
    material = db.Column(db.String(100), nullable=False, index=True)
    client = db.Column(db.String(100), index=True)
    client_name = db.Column(db.String(100), index=True)
    client_code = db.Column(db.String(50), index=True)
    qty = db.Column(db.Float, nullable=False)
    bill_no = db.Column(db.String(100), index=True)
    auto_bill_no = db.Column(db.String(100), index=True)
    nimbus_no = db.Column(db.String(100), index=True)
    # Optional link to an Invoice when this entry is billed
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)
    invoice = db.relationship('Invoice', backref='entries')
    created_by = db.Column(db.String(100))
    client_category = db.Column(db.String(50), index=True, nullable=True)


class ReconBasket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_no = db.Column(db.String(100), index=True)
    # Side A - Finance
    fin_date = db.Column(db.Date)
    fin_client = db.Column(db.String(200))
    fin_code = db.Column(db.String(100))
    fin_amount = db.Column(db.Float, default=0.0)
    # Side B - Inventory
    inv_date = db.Column(db.Date)
    inv_client = db.Column(db.String(200))
    inv_code = db.Column(db.String(100))
    inv_material = db.Column(db.String(200))
    inv_qty = db.Column(db.Float, default=0.0)
    # Status and meta
    status = db.Column(db.String(20), default='RED', index=True)  # GREEN/YELLOW/RED/BLUE
    match_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
