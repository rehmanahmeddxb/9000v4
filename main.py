import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
from sqlalchemy import func, case
from types import SimpleNamespace
from models import db, User, Client, Material, Entry, PendingBill, Booking, BookingItem, Payment, Invoice, BillCounter, DirectSale, DirectSaleItem

app = Flask(__name__)
# Increase max content length to 16MB to handle large JSON imports
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024


def generate_client_code():
    """Generate next client code in format tmpc-000001"""
    last_client = Client.query.filter(Client.code.like('tmpc-%')).order_by(
        Client.code.desc()).first()
    if last_client and last_client.code:
        try:
            num = int(last_client.code.split('-')[1]) + 1
        except:
            num = 1
    else:
        num = 1
    return f"tmpc-{num:06d}"


def generate_material_code():
    """Generate next material code in format tmpm-00001"""
    last_material = Material.query.filter(
        Material.code.like('tmpm-%')).order_by(Material.code.desc()).first()
    if last_material and last_material.code:
        try:
            num = int(last_material.code.split('-')[1]) + 1
        except:
            num = 1
    else:
        num = 1
    return f"tmpm-{num:05d}"


def get_next_bill_no():
    counter = BillCounter.query.first()
    if not counter:
        counter = BillCounter(count=1000)
        db.session.add(counter)
        db.session.commit()
    no = f"#{counter.count}"
    counter.count += 1
    db.session.commit()
    return no


def save_photo(file):
    if file and file.filename != '':
        filename = secure_filename(
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        upload_folder = os.path.join(basedir, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return filename
    return None


app.secret_key = "ahmed_tracking_secure_key"

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'ahmed_cement.db')

if not os.path.exists(os.path.join(basedir, 'instance')):
    os.makedirs(os.path.join(basedir, 'instance'))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


# Ensure DB has `password_hash` column before any queries occur
def _ensure_user_password_column():
    """Ensure `password_hash` column exists on `user` table and copy legacy `password` values.

    Uses textual SQL via `text()` to avoid SQLAlchemy coercion errors.
    """
    from sqlalchemy import text

    try:
        rows = db.session.execute(text("PRAGMA table_info('user')")).fetchall()
        cols = [r[1] for r in rows]
        if 'password_hash' not in cols:
            # Add the column and copy legacy values if present
            db.session.execute(text("ALTER TABLE user ADD COLUMN password_hash VARCHAR(200);"))
            if 'password' in cols:
                db.session.execute(text("UPDATE user SET password_hash = password WHERE password_hash IS NULL;"))
            db.session.commit()
    except Exception:
        db.session.rollback()

# Run early migration once at import-time so subsequent imports/requests are safe

def _ensure_model_columns():
    """Add any missing columns declared in models but missing in the DB.

    This is a pragmatic, best-effort migration helper to bring older SQLite
    databases in sync. It maps common SQLAlchemy types to reasonable SQLite
    column types and runs simple ALTER TABLE ADD COLUMN commands. Uses `text()`
    for SQL execution to avoid coercion errors.
    """
    from sqlalchemy import String, Integer, Float, Date, DateTime, Boolean, Text, text

    try:
        for table in db.metadata.sorted_tables:
            rows = db.session.execute(text(f"PRAGMA table_info('{table.name}')")).fetchall()
            existing_cols = [r[1] for r in rows]
            for col in table.columns:
                if col.name not in existing_cols:
                    coltype = col.type
                    sqltype = 'VARCHAR(200)'
                    if isinstance(coltype, (String, Text)):
                        sqltype = 'VARCHAR(200)'
                    elif isinstance(coltype, (Integer, Boolean)):
                        sqltype = 'INTEGER'
                    elif isinstance(coltype, Float):
                        sqltype = 'REAL'
                    elif isinstance(coltype, Date):
                        sqltype = 'DATE'
                    elif isinstance(coltype, DateTime):
                        sqltype = 'DATETIME'

                    try:
                        db.session.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {sqltype};"))
                    except Exception:
                        # If a single column fails to add, continue with others
                        db.session.rollback()
        db.session.commit()
    except Exception:
        db.session.rollback()


with app.app_context():
    db.create_all()
    try:
        _ensure_user_password_column()
    except Exception:
        # Best-effort at startup; don't prevent app import if migration fails
        pass

    try:
        _ensure_model_columns()
    except Exception:
        # Best-effort: continue even if generic migration fails
        pass


# --- Helper Functions ---
def get_next_bill_no():
    counter = BillCounter.query.first()
    if not counter:
        counter = BillCounter(count=1000)
        db.session.add(counter)
        db.session.commit()
    no = f"#{counter.count}"
    counter.count += 1
    db.session.commit()
    return no


def save_photo(file):
    if file and file.filename != '':
        filename = secure_filename(
            f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        upload_folder = os.path.join(basedir, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return filename
    return None


# --- New Routes from A1 ---
@app.route('/bookings')
@login_required
def bookings_page():
    bookings = Booking.query.order_by(Booking.date_posted.desc()).all()
    clients = Client.query.filter_by(is_active=True).all()
    materials = Material.query.all()
    counter = BillCounter.query.first()
    if not counter:
        counter = BillCounter(count=1000)
        db.session.add(counter)
        db.session.commit()
    next_auto = f"#{counter.count}"
    return render_template('bookings.html',
                           bookings=bookings,
                           clients=clients,
                           materials=materials,
                           next_auto=next_auto)


@app.route('/add_booking', methods=['POST'])
@login_required
def add_booking():
    client_name = request.form.get('client_name')
    materials = request.form.getlist('material_name[]')
    qtys = request.form.getlist('qty[]')
    rates = request.form.getlist('unit_rate[]')
    amount = float(request.form.get('amount', 0))
    paid_amount = float(request.form.get('paid_amount', 0))
    manual_bill_no = request.form.get('manual_bill_no')

    photo_path = save_photo(request.files.get('photo'))
    auto_bill_no = get_next_bill_no()

    # Auto-add to PendingBill
    client = Client.query.filter_by(name=client_name).first()
    if client:
        existing_pb = PendingBill.query.filter_by(bill_no=auto_bill_no, client_code=client.code).first()
        if not existing_pb:
            db.session.add(PendingBill(
                client_code=client.code,
                client_name=client.name,
                bill_no=auto_bill_no,
                amount=amount,
                reason=f"Booking: {materials[0] if materials else ''}",
                created_at=datetime.now().strftime('%Y-%m-%d'),
                created_by=current_user.username
            ))

    booking = Booking(client_name=client_name,
                      amount=amount,
                      paid_amount=paid_amount,
                      manual_bill_no=manual_bill_no,
                      auto_bill_no=auto_bill_no,
                      photo_path=photo_path)
    db.session.add(booking)
    db.session.flush()

    for mat, qty, rate in zip(materials, qtys, rates):
        if mat:
            db.session.add(
                BookingItem(booking_id=booking.id,
                            material_name=mat,
                            qty=float(qty),
                            price_at_time=float(rate)))

    db.session.commit()
    flash('Booking added successfully', 'success')
    return redirect(url_for('bookings_page'))


@app.route('/payments')
@login_required
def payments_page():
    payments = Payment.query.order_by(Payment.date_posted.desc()).all()
    clients = Client.query.filter_by(is_active=True).all()
    counter = BillCounter.query.first()
    if not counter:
        counter = BillCounter(count=1000)
        db.session.add(counter)
        db.session.commit()
    next_auto = f"#{counter.count}"
    return render_template('payments.html',
                           payments=payments,
                           clients=clients,
                           next_auto=next_auto)


@app.route('/add_payment', methods=['POST'])
@login_required
def add_payment():
    client_name = request.form.get('client_name')
    amount = float(request.form.get('amount', 0))
    method = request.form.get('method')
    manual_bill_no = request.form.get('manual_bill_no')
    photo_path = save_photo(request.files.get('photo'))
    auto_bill_no = get_next_bill_no()

    payment = Payment(client_name=client_name,
                      amount=amount,
                      method=method,
                      manual_bill_no=manual_bill_no,
                      auto_bill_no=auto_bill_no,
                      photo_path=photo_path)
    db.session.add(payment)
    db.session.flush()

    # Apply payment to matching pending bills when possible
    remaining = float(amount)
    applied = []

    # Prefer matching by bill_no when provided
    if manual_bill_no:
        pending_q = PendingBill.query.filter_by(bill_no=manual_bill_no).order_by(PendingBill.id.asc()).all()
    else:
        # Otherwise apply to oldest unpaid bills for this client
        pending_q = PendingBill.query.filter_by(client_name=client_name, is_paid=False).order_by(PendingBill.id.asc()).all()

    for pb in pending_q:
        if remaining <= 0:
            break
        if pb.is_paid:
            continue
        if remaining >= (pb.amount or 0):
            remaining -= (pb.amount or 0)
            pb.amount = 0
            pb.is_paid = True
            applied.append((pb.bill_no, 'paid'))
        else:
            pb.amount = (pb.amount or 0) - remaining
            applied.append((pb.bill_no, f'partial {remaining:.2f}'))
            remaining = 0

    db.session.commit()

    msg = 'Payment received successfully'
    if applied:
        details = ', '.join([f"{b}: {s}" for b, s in applied])
        msg += f" — applied to: {details}"
    flash(msg, 'success')
    return redirect(url_for('payments_page'))


# GRN feature removed: stock-in functionality is handled via Entries with type='IN'.
# The `/grn`, `/add_grn` and edit/delete handlers and `grn.html` template were removed
# to simplify the system and avoid maintaining duplicated inventory flows.


@app.route('/view_bill/<path:bill_no>')
@login_required
def view_bill(bill_no):
    # Support both with and without #
    search_no = bill_no if bill_no.startswith('#') else f"#{bill_no}"

    booking = Booking.query.filter_by(auto_bill_no=search_no).first()
    payment = Payment.query.filter_by(auto_bill_no=search_no).first()
    invoice = Invoice.query.filter_by(invoice_no=search_no).first()

    if booking:
        return render_template('view_bill.html', bill=booking, type='Booking', items=booking.items)
    if payment:
        return render_template('view_bill.html', bill=payment, type='Payment')
    if invoice:
        # Shape invoice into expected template fields
        # Provide `auto_bill_no`, `amount`, `paid_amount`, `date_posted`, and `items` for compatibility
        invoice.auto_bill_no = invoice.invoice_no
        invoice.amount = invoice.total_amount
        invoice.paid_amount = (invoice.total_amount - invoice.balance) if invoice.total_amount is not None and invoice.balance is not None else 0
        invoice.date_posted = datetime.combine(invoice.date, datetime.min.time()) if invoice.date else None

        # Build items list from linked DirectSale items if available, otherwise from entries
        items = []
        if getattr(invoice, 'direct_sales', None):
            # Use first linked direct sale's items for display
            if invoice.direct_sales:
                ds = invoice.direct_sales[0]
                items = [{'name': it.product_name, 'qty': it.qty} for it in ds.items]
        if not items and getattr(invoice, 'entries', None):
            items = [{'name': e.material, 'qty': e.qty} for e in invoice.entries]
        return render_template('view_bill.html', bill=invoice, type='Invoice', items=items)


    flash('Bill not found', 'danger')
    return redirect(url_for('index'))


@app.route('/download_invoice/<path:bill_no>')
@login_required
def download_invoice(bill_no):
    # For now, provide a simple HTML download of the invoice details. PDF generation could be added later.
    search_no = bill_no if bill_no.startswith('#') else f"#{bill_no}"
    inv = Invoice.query.filter_by(invoice_no=search_no).first()
    if not inv:
        flash('Invoice not found', 'danger')
        return redirect(url_for('index'))

    # Render the invoice view and send as an attachment (HTML) for convenience
    inv.auto_bill_no = inv.invoice_no
    inv.amount = inv.total_amount
    inv.paid_amount = (inv.total_amount - inv.balance) if inv.total_amount is not None and inv.balance is not None else 0
    inv.date_posted = datetime.combine(inv.date, datetime.min.time()) if inv.date else None

    items = []
    if getattr(inv, 'direct_sales', None) and inv.direct_sales:
        ds = inv.direct_sales[0]
        items = [{'name': it.product_name, 'qty': it.qty} for it in ds.items]
    if not items and getattr(inv, 'entries', None):
        items = [{'name': e.material, 'qty': e.qty} for e in inv.entries]

    rendered = render_template('view_bill.html', bill=inv, type='Invoice', items=items)
    from flask import make_response
    response = make_response(rendered)
    response.headers['Content-Disposition'] = f'attachment; filename=invoice-{inv.invoice_no}.html'
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


@app.route('/edit_bill/Booking/<int:id>', methods=['POST'])
@login_required
def edit_booking(id):
    booking = Booking.query.get_or_404(id)
    booking.client_name = request.form.get('client_name')
    booking.amount = float(request.form.get('amount', 0))
    booking.paid_amount = float(request.form.get('paid_amount', 0))
    booking.manual_bill_no = request.form.get('manual_bill_no')

    new_photo = save_photo(request.files.get('photo'))
    if new_photo:
        booking.photo_path = new_photo

    BookingItem.query.filter_by(booking_id=id).delete()

    materials = request.form.getlist('material_name[]')
    qtys = request.form.getlist('qty[]')
    rates = request.form.getlist('unit_rate[]')

    for mat, qty, rate in zip(materials, qtys, rates):
        if mat:
            db.session.add(
                BookingItem(booking_id=booking.id,
                            material_name=mat,
                            qty=float(qty),
                            price_at_time=float(rate)))

    db.session.commit()
    flash('Booking updated', 'success')
    return redirect(url_for('bookings_page'))


@app.route('/edit_bill/Payment/<int:id>', methods=['POST'])
@login_required
def edit_payment(id):
    payment = Payment.query.get_or_404(id)
    payment.amount = float(request.form.get('amount', 0))
    payment.manual_bill_no = request.form.get('manual_bill_no')

    new_photo = save_photo(request.files.get('photo'))
    if new_photo:
        payment.photo_path = new_photo

    db.session.commit()
    flash('Payment updated', 'success')
    return redirect(url_for('payments_page'))


# GRN edit handler removed (GRN feature deprecated).

@app.route('/direct_sales')
@login_required
def direct_sales_page():
    sales = DirectSale.query.order_by(DirectSale.date_posted.desc()).all()
    materials = Material.query.all()
    clients = Client.query.filter_by(is_active=True).all()
    # collect categories from clients and include 'Cash'
    categories = sorted(list({c.category for c in clients if c.category}))
    if 'Cash' not in categories:
        categories.insert(0, 'Cash')
    client_name_prefill = request.args.get('client_name', '').strip()
    counter = BillCounter.query.first()
    if not counter:
        counter = BillCounter(count=1000)
        db.session.add(counter)
        db.session.commit()
    next_auto = f"#{counter.count}"
    return render_template('direct_sales.html',
                           sales=sales,
                           materials=materials,
                           clients=clients,
                           categories=categories,
                           next_auto=next_auto,
                           client_name_prefill=client_name_prefill)


@app.route('/add_direct_sale', methods=['POST'])
@login_required
def add_direct_sale():
    # Backwards-compatible alias: support legacy POST to /add_sale

    # Accept either explicit client_name (from hidden input) or the visible client_code field if user typed a free-text name
    client_name = request.form.get('client_name') or request.form.get('client_code')
    materials = request.form.getlist('product_name[]')
    qtys = request.form.getlist('qty[]')
    rates = request.form.getlist('unit_rate[]')
    amount = float(request.form.get('amount', 0))
    paid_amount = float(request.form.get('paid_amount', 0))
    manual_bill_no = request.form.get('manual_bill_no')

    photo_path = save_photo(request.files.get('photo'))
    auto_bill_no = get_next_bill_no()

    # Category (may be 'Cash' for non-registered customers)
    category = request.form.get('category') or ''

    # If category is 'Cash', respect manual customer name input and do not resolve a registered client
    client = None
    if category.lower() == 'cash':
        manual_client_name = request.form.get('manual_client_name')
        if manual_client_name:
            client_name = manual_client_name
    else:
        # Try to resolve client by name first, then by code if the user submitted a code
        client = Client.query.filter_by(name=client_name).first()
        if not client and client_name:
            client_by_code = Client.query.filter_by(code=client_name).first()
            if client_by_code:
                client = client_by_code
                # Normalize client_name to actual client name for storage
                client_name = client.name

    # Check if user asked to create an Invoice for this sale
    create_invoice = bool(request.form.get('create_invoice'))
    # Respect explicit 'has_bill' flag on the form. If absent, default to True
    # (backwards compatible with older forms that omit this field).
    hv = request.form.get('has_bill')
    if hv is None:
        has_bill = True
    else:
        has_bill = hv in ['on', '1', 'true', 'True']

    # If client exists, we may create a PendingBill or Invoice based on form
    pending_amount = max(0.0, float(amount) - float(paid_amount))

    # Enforce manual invoice requirement if client requires it and invoice not requested and no manual bill provided
    if client and client.require_manual_invoice and (not create_invoice) and not manual_bill_no:
        flash('Manual invoice required for this client. Please provide Manual Bill No or check Create Invoice.', 'danger')
        return redirect(url_for('direct_sales_page'))

    # Handle invoice creation when requested
    inv = None
    invoice_no = None
    if create_invoice:
        # Prefer manual bill no as manual invoice number
        if manual_bill_no:
            invoice_no = manual_bill_no
            is_manual = True
        else:
            invoice_no = get_next_bill_no()
            is_manual = False

        # Ensure uniqueness
        existing_global = Invoice.query.filter_by(invoice_no=invoice_no).first()
        if existing_global and not is_manual:
            # auto-generated collided; generate until unique
            while Invoice.query.filter_by(invoice_no=invoice_no).first():
                invoice_no = get_next_bill_no()
        elif existing_global and is_manual:
            if client and existing_global.client_code != client.code:
                flash(f'Invoice number "{invoice_no}" is already used by another client. Pick a different manual invoice number.', 'danger')
                return redirect(url_for('direct_sales_page'))

        # Create or update the Invoice record
        inv = Invoice.query.filter_by(invoice_no=invoice_no, client_code=(client.code if client else None)).first()
        balance = max(0.0, float(amount) - float(paid_amount))
        status = 'OPEN'
        if balance <= 0:
            status = 'PAID'
        elif paid_amount > 0:
            status = 'PARTIAL'

        if inv:
            inv.client_name = client.name if client else client_name
            inv.total_amount = amount
            inv.balance = balance
            inv.is_cash = bool(request.form.get('track_as_cash'))
            inv.status = status
            inv.date = datetime.now().date()
        else:
            inv = Invoice(client_code=(client.code if client else None),
                          client_name=client.name if client else client_name,
                          invoice_no=invoice_no,
                          is_manual=is_manual,
                          date=datetime.now().date(),
                          total_amount=amount,
                          balance=balance,
                          status=status,
                          is_cash=bool(request.form.get('track_as_cash')),
                          created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                          created_by=current_user.username)
            db.session.add(inv)
            db.session.flush()

    app.logger.info('add_direct_sale: client=%s create_invoice=%s has_bill=%s pending_amount=%s category=%s', getattr(client, 'code', None), create_invoice, has_bill, pending_amount, category)

    # Auto-add to PendingBill for any billed sale with outstanding amount (including cash category)
    if has_bill and not create_invoice and pending_amount > 0:
        app.logger.info('Creating pending bill for direct sale: %s %s', getattr(client, 'code', None), auto_bill_no)
        existing_pb = PendingBill.query.filter_by(bill_no=auto_bill_no, client_code=(client.code if client else None)).first()
        if not existing_pb:
            db.session.add(PendingBill(
                client_code=(client.code if client else None),
                client_name=(client.name if client else client_name),
                bill_no=auto_bill_no,
                amount=pending_amount,
                reason=f"Direct Sale: {materials[0] if materials else ''}",
                created_at=datetime.now().strftime('%Y-%m-%d'),
                created_by=current_user.username
            ))

    # Special-case: unpaid Cash category direct sales should create a cash PendingBill so they appear
    # in the cash pending payments section (is_cash=True). We use an empty bill_no for cash payments.
    if (category and category.lower() == 'cash') and pending_amount > 0:
        app.logger.info('Creating cash pending bill for direct sale (cash): %s', client_name)
        existing_pb = PendingBill.query.filter_by(client_name=client_name, amount=pending_amount, is_cash=True).first()
        if not existing_pb:
            db.session.add(PendingBill(
                client_code=None,
                client_name=client_name,
                bill_no='',
                amount=pending_amount,
                reason=f"Cash Direct Sale: {materials[0] if materials else ''}",
                is_cash=True,
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                created_by=current_user.username
            ))

    # If invoice created and there's a balance, add PendingBill using invoice number so it's tracked
    if create_invoice and inv and inv.balance > 0 and has_bill:
        existing_pb = PendingBill.query.filter_by(bill_no=inv.invoice_no, client_code=(client.code if client else None)).first()
        if not existing_pb:
            db.session.add(PendingBill(
                client_code=(client.code if client else None),
                client_name=(client.name if client else client_name),
                bill_no=inv.invoice_no,
                amount=inv.balance,
                reason=f"Direct Sale: {materials[0] if materials else ''}",
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                created_by=current_user.username
            ))
    # If client not found, leave as free-text name on the sale (cash customer)

    sale = DirectSale(client_name=client_name,
                      amount=amount,
                      paid_amount=paid_amount,
                      manual_bill_no=manual_bill_no,
                      auto_bill_no=auto_bill_no,
                      photo_path=photo_path,
                      category=category)
    db.session.add(sale)
    db.session.flush()

    # If we created an Invoice above, link it to the sale
    if create_invoice and inv:
        sale.invoice_id = inv.id

    items_created = []
    for mat, qty, rate in zip(materials, qtys, rates):
        if mat:
            dsi = DirectSaleItem(sale_id=sale.id,
                               product_name=mat,
                               qty=float(qty),
                               price_at_time=float(rate))
            db.session.add(dsi)
            items_created.append(dsi)

    # Create dispatching Entry rows for each sale item so this sale appears in material ledger
    now = datetime.now()
    for item in items_created:
        entry = Entry(date=now.strftime('%Y-%m-%d'),
                      time=now.strftime('%H:%M:%S'),
                      type='OUT',
                      material=item.product_name,
                      client=client_name,
                      client_code=(client.code if client else None),
                      qty=item.qty,
                      bill_no=(manual_bill_no if manual_bill_no else (auto_bill_no if has_bill else None)),
                      auto_bill_no=auto_bill_no,
                      nimbus_no='Direct Sale',
                      created_by=current_user.username,
                      client_category=category)
        db.session.add(entry)

    db.session.commit()
    msg = 'Direct sale added successfully'
    if create_invoice and inv:
        msg += f" — Invoice: {inv.invoice_no}"
    flash(msg, 'success')
    return redirect(url_for('direct_sales_page'))


# Legacy alias: maintain compatibility for `/add_sale`
@app.route('/add_sale', methods=['POST'])
@login_required
def add_sale():
    return add_direct_sale()


@app.route('/edit_bill/DirectSale/<int:id>', methods=['POST'])
@login_required
def edit_direct_sale(id):
    sale = DirectSale.query.get_or_404(id)
    sale.client_name = request.form.get('client_name')
    sale.amount = float(request.form.get('amount', 0))
    sale.paid_amount = float(request.form.get('paid_amount', 0))
    sale.manual_bill_no = request.form.get('manual_bill_no')

    new_photo = save_photo(request.files.get('photo'))
    if new_photo:
        sale.photo_path = new_photo

    DirectSaleItem.query.filter_by(sale_id=id).delete()

    materials = request.form.getlist('product_name[]')
    qtys = request.form.getlist('qty[]')
    rates = request.form.getlist('unit_rate[]')

    for mat, qty, rate in zip(materials, qtys, rates):
        if mat:
            db.session.add(
                DirectSaleItem(sale_id=sale.id,
                               product_name=mat,
                               qty=float(qty),
                               price_at_time=float(rate)))

    db.session.commit()
    flash('Direct sale updated', 'success')
    return redirect(url_for('direct_sales_page'))


@app.route('/delete_bill/<string:type>/<int:id>')
@login_required
def delete_bill(type, id):
    if current_user.role != 'admin':
        flash('Unauthorized', 'danger')
        return redirect(url_for('index'))

    if type == 'Booking':
        bill = Booking.query.get(id)
    elif type == 'Payment':
        bill = Payment.query.get(id)
    elif type == 'DirectSale':
        bill = DirectSale.query.get(id)
    else:
        bill = None

    if bill:
        db.session.delete(bill)
        db.session.commit()
        flash(f'{type} deleted successfully', 'success')
    else:
        flash('Bill not found', 'danger')

    if type == 'Booking': return redirect(url_for('bookings_page'))
    if type == 'Payment': return redirect(url_for('payments_page'))
    if type == 'DirectSale': return redirect(url_for('direct_sales_page'))
    return redirect(url_for('index'))


@app.route('/ledger')
@login_required
def ledger_page():
    clients = Client.query.filter_by(is_active=True).all()
    return render_template('ledger.html', clients=clients)


@app.route('/ledger/<int:client_id>')
@login_required
def financial_ledger(client_id):
    client = Client.query.get_or_404(client_id)
    
    # 1. Fetch Pending Bills from PendingBill table matching client_code
    pending_bills = PendingBill.query.filter_by(client_code=client.code).order_by(PendingBill.id.desc()).all()
    
    # 2. Financial Ledger (Transactions) - Used for calculating balance
    bookings = Booking.query.filter_by(client_name=client.name).all()
    payments = Payment.query.filter_by(client_name=client.name).all()
    direct_sales = DirectSale.query.filter_by(client_name=client.name).all()

    financial_history = []
    for b in bookings:
        financial_history.append({
            'date': b.date_posted,
            'description': 'Booking',
            'bill_no': b.auto_bill_no,
            'debit': b.amount,
            'credit': b.paid_amount,
            'type': 'Booking',
            'id': b.id
        })
    for p in payments:
        financial_history.append({
            'date': p.date_posted,
            'description': f'Payment ({p.method})',
            'bill_no': p.auto_bill_no,
            'debit': 0,
            'credit': p.amount,
            'type': 'Payment',
            'id': p.id
        })
    for s in direct_sales:
        financial_history.append({
            'date': s.date_posted,
            'description': 'Direct Sale',
            'bill_no': s.auto_bill_no,
            'debit': s.amount,
            'credit': s.paid_amount,
            'type': 'DirectSale',
            'id': s.id
        })
    
    financial_history.sort(key=lambda x: x['date'], reverse=True)

    # 3. Material Ledger (Deliveries and Direct Sales)
    # We use bill_no to ensure we don't double count if a delivery and a sale share a bill_no
    deliveries = Entry.query.filter(
        (Entry.client_code == client.code) | (Entry.client == client.name),
        Entry.type == 'OUT'
    ).order_by(Entry.date.desc(), Entry.time.desc()).all()

    material_history = []
    seen_material_bills = set()
    
    for d in deliveries:
        material_history.append({
            'date': d.date,
            'material': d.material,
            'qty': d.qty,
            'bill_no': d.bill_no,
            'nimbus_no': d.nimbus_no
        })
        if d.bill_no: seen_material_bills.add(d.bill_no)

    for s in direct_sales:
        if s.auto_bill_no not in seen_material_bills:
            for item in s.items:
                material_history.append({
                    'date': s.date_posted.strftime('%Y-%m-%d'),
                    'material': item.product_name,
                    'qty': item.qty,
                    'bill_no': s.auto_bill_no,
                    'nimbus_no': 'Direct Sale'
                })

    return render_template('client_ledger.html',
                           client=client,
                           pending_bills=pending_bills,
                           financial_history=financial_history,
                           material_history=material_history)


@app.route('/financial_ledger/<int:client_id>')
@login_required
def financial_ledger_details(client_id):
    return redirect(url_for('financial_ledger', client_id=client_id))


@app.route('/material_ledger/<int:mat_id>')
@login_required
def material_ledger_page(mat_id):
    material = Material.query.get_or_404(mat_id)
    # Use stock-in entries (Entry.type == 'IN') to represent additions to stock
    stock_ins = Entry.query.filter_by(material=material.name, type='IN').all()
    sales = DirectSaleItem.query.filter_by(product_name=material.name).all()

    all_transactions = []
    for e in stock_ins:
        all_transactions.append({
            'date': e.date if not isinstance(e.date, str) else datetime.strptime(e.date, '%Y-%m-%d'),
            'item': e.material,
            'bill_no': e.bill_no or '',
            'add': e.qty,
            'delivered': 0
        })
    for s in sales:
        all_transactions.append({
            'date': s.direct_sale.date_posted,
            'item': s.product_name,
            'bill_no': s.direct_sale.auto_bill_no,
            'add': 0,
            'delivered': s.qty
        })

    all_transactions.sort(key=lambda x: x['date'])
    history = []
    running_balance = 0
    for t in all_transactions:
        running_balance += (t['add'] - t['delivered'])
        history.append({
            'date': t['date'].strftime('%d-%m-%Y'),
            'item': t['item'],
            'bill_no': t['bill_no'],
            'add': t['add'],
            'delivered': t['delivered'],
            'balance': running_balance
        })

    return render_template('material_ledger.html',
                           material=material,
                           history=history)


@app.route('/view_bill_detail/<string:type>/<int:id>')
@login_required
def view_bill_detail(type, id):
    if type == 'Booking':
        bill = Booking.query.get_or_404(id)
    elif type == 'Payment':
        bill = Payment.query.get_or_404(id)
    elif type == 'DirectSale':
        bill = DirectSale.query.get_or_404(id)
    else:
        return "Invalid Bill Type", 400
    return render_template('view_bill.html', bill=bill, type=type)


from blueprints.inventory import inventory_bp
from blueprints.import_export import import_export_bp

app.register_blueprint(inventory_bp)
app.register_blueprint(import_export_bp)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
@login_required
def index():
    today = date.today().strftime('%B %d, %Y')
    client_count = db.session.query(func.count(Client.id)).scalar() or 0
    stats_query = db.session.query(
        Entry.material,
        func.sum(case((Entry.type == 'IN', Entry.qty),
                      else_=0)).label('total_in'),
        func.sum(case(
            (Entry.type == 'OUT', Entry.qty),
            else_=0)).label('total_out')).group_by(Entry.material).all()
    # Sort alphabetically by brand name
    stats = sorted([{
        'name': row.material,
        'in': int(row.total_in or 0),
        'out': int(row.total_out or 0),
        'stock': int((row.total_in or 0) - (row.total_out or 0))
    } for row in stats_query],
                   key=lambda x: x['name'])
    total_stock = sum(s['stock'] for s in stats)
    return render_template('index.html',
                           today_date=today,
                           total_stock=int(total_stock),
                           client_count=client_count,
                           stats=stats)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(
            username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash,
                                        str(request.form.get('password'))):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid Credentials', 'danger')
    return render_template('login.html')


@app.route('/api/clients/search')
@login_required
def api_clients_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2: return jsonify([])
    clients = Client.query.filter(
        db.or_(Client.name.ilike(f'%{q}%'),
               Client.code.ilike(f'%{q}%'))).limit(10).all()
    return jsonify([{'name': c.name, 'code': c.code} for c in clients])


@app.route('/materials')
@login_required
def materials():
    page = request.args.get('page', 1, type=int)
    # Alphabetical sorting
    pagination = Material.query.order_by(Material.name.asc()).paginate(
        page=page, per_page=10)
    return render_template('materials.html',
                           materials=pagination.items,
                           pagination=pagination)


@app.route('/add_material', methods=['POST'])
@login_required
def add_material():
    name = request.form.get('material_name')
    code = request.form.get('material_code', '').strip()
    if not name:
        flash('Material name is required', 'danger')
        return redirect(url_for('materials'))
    if not code:
        flash('Material code is required for manual entry', 'danger')
        return redirect(url_for('materials'))
    if Material.query.filter_by(code=code).first():
        flash(f'Material code "{code}" already exists', 'danger')
        return redirect(url_for('materials'))
    db.session.add(Material(name=name, code=code))
    db.session.commit()
    flash('Brand Added', 'success')
    return redirect(url_for('materials'))


@app.route('/edit_material/<int:id>', methods=['POST'])
@login_required
def edit_material(id):
    m = db.session.get(Material, id)
    if m:
        new_code = request.form.get('material_code', '').strip()
        if not new_code:
            flash('Material code is required', 'danger')
            return redirect(url_for('materials'))
        existing = Material.query.filter_by(code=new_code).first()
        if existing and existing.id != id:
            flash(f'Material code "{new_code}" already exists', 'danger')
            return redirect(url_for('materials'))
        old_name = m.name
        new_name = request.form.get('material_name')
        for e in Entry.query.filter_by(material=old_name).all():
            e.material = new_name
        m.name = new_name
        m.code = new_code
        db.session.commit()
        flash('Brand Updated', 'info')
    return redirect(url_for('materials'))


@app.route('/delete_material/<int:id>')
@login_required
def delete_material(id):
    m = db.session.get(Material, id)
    if m:
        db.session.delete(m)
        db.session.commit()
        flash('Brand Removed', 'warning')
    return redirect(url_for('materials'))


@app.route('/clients')
@login_required
def clients():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    page_active = request.args.get('page_active', 1, type=int)
    page_inactive = request.args.get('page_inactive', 1, type=int)

    # Active Clients Query
    active_query = Client.query.filter(Client.is_active == True)
    if search:
        active_query = active_query.filter(
            db.or_(Client.name.ilike(f'%{search}%'),
                   Client.code.ilike(f'%{search}%')))
    if category:
        active_query = active_query.filter(Client.category == category)
    active_pagination = active_query.order_by(Client.name.asc()).paginate(
        page=page_active, per_page=10)

    # Inactive Clients Query
    inactive_query = Client.query.filter(Client.is_active == False)
    if search:
        inactive_query = inactive_query.filter(
            db.or_(Client.name.ilike(f'%{search}%'),
                   Client.code.ilike(f'%{search}%')))
    if category:
        inactive_query = inactive_query.filter(Client.category == category)
    inactive_pagination = inactive_query.order_by(Client.name.asc()).paginate(
        page=page_inactive, per_page=10)

    # Calculate stats for all visible clients
    all_visible_clients = active_pagination.items + inactive_pagination.items
    for c in all_visible_clients:
        c.total_bills = db.session.query(func.count(PendingBill.id)).filter_by(client_code=c.code).scalar() or 0
        c.total_deliveries = db.session.query(func.sum(Entry.qty)).filter_by(client=c.name, type='OUT').scalar() or 0

    active_clients_list = Client.query.filter(
        Client.is_active == True).order_by(Client.name.asc()).all()
    return render_template('clients.html',
                           active_pagination=active_pagination,
                           inactive_pagination=inactive_pagination,
                           search=search,
                           category=category,
                           active_clients=active_clients_list)


@app.route('/add_client', methods=['POST'])
@login_required
def add_client():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    if not name:
        flash('Client name is required', 'danger')
        return redirect(url_for('clients'))
    if not code:
        flash('Client code is required for manual entry', 'danger')
        return redirect(url_for('clients'))
    if Client.query.filter_by(code=code).first():
        flash(f'Client code "{code}" already exists', 'danger')
        return redirect(url_for('clients'))
    new_c = Client(name=name,
                   code=code,
                   phone=request.form.get('phone'),
                   address=request.form.get('address'),
                   category=request.form.get('category', 'General'))
    db.session.add(new_c)
    db.session.commit()
    flash('Client Registered', 'success')
    return redirect(url_for('clients'))


@app.route('/edit_client/<int:id>', methods=['POST'])
@login_required
def edit_client(id):
    c = db.session.get(Client, id)
    if c:
        old_code = c.code
        old_name = c.name
        new_code = request.form.get('code', '').strip()
        new_name = request.form.get('name', '').strip()

        if not new_code:
            flash('Client code is required', 'danger')
            return redirect(url_for('clients'))

        existing = Client.query.filter_by(code=new_code).first()
        if existing and existing.id != id:
            flash(f'Client code "{new_code}" already exists', 'danger')
            return redirect(url_for('clients'))

        # Global Data Consistency: Propagate changes to all modules
        if old_code != new_code or old_name != new_name:
            # Update Pending Bills
            PendingBill.query.filter_by(client_code=old_code).update({
                'client_code':
                new_code,
                'client_name':
                new_name
            })
            Entry.query.filter_by(client_code=old_code).update({
                'client_code':
                new_code,
                'client':
                new_name
            })
            # Legacy check for name-based entries
            Entry.query.filter_by(client=old_name).update({'client': new_name})

        c.name = new_name
        c.code = new_code
        c.phone = request.form.get('phone')
        c.address = request.form.get('address')
        c.category = request.form.get('category', 'General')

        db.session.commit()
        flash('Client updated and changes propagated across all records',
              'success')
    return redirect(url_for('clients'))


@app.route('/delete_client/<int:id>')
@login_required
def delete_client(id):
    c = db.session.get(Client, id)
    if c:
        db.session.delete(c)
        db.session.commit()
        flash('Client Deleted', 'warning')
    return redirect(url_for('clients'))


@app.route('/transfer_client/<int:id>', methods=['POST'])
@login_required
def transfer_client(id):
    source_client = db.session.get(Client, id)
    target_client_id = request.form.get('target_client_id')
    if not source_client or not target_client_id:
        flash('Invalid transfer request', 'danger')
        return redirect(url_for('clients'))

    target_client = db.session.get(Client, int(target_client_id))
    if not target_client:
        flash('Target client not found', 'danger')
        return redirect(url_for('clients'))

    if target_client.id == source_client.id:
        flash('Cannot transfer to the same client', 'danger')
        return redirect(url_for('clients'))

    if not target_client.is_active:
        flash('Cannot transfer to an inactive client', 'danger')
        return redirect(url_for('clients'))

    # Update both Entry and PendingBill
    entries_updated = Entry.query.filter_by(
        client_code=source_client.code).update({
            'client':
            target_client.name,
            'client_code':
            target_client.code
        })
    bills_updated = PendingBill.query.filter_by(
        client_code=source_client.code).update({
            'client_name':
            target_client.name,
            'client_code':
            target_client.code
        })

    source_client.is_active = False
    source_client.transferred_to_id = target_client.id
    db.session.commit()

    flash(
        f'Transferred {entries_updated} entries and {bills_updated} bills from "{source_client.name}" to "{target_client.name}".',
        'success')
    return redirect(url_for('clients'))


@app.route('/reclaim_client/<int:id>', methods=['POST'])
@login_required
def reclaim_client(id):
    source_client = db.session.get(Client, id)
    if not source_client or source_client.is_active or not source_client.transferred_to_id:
        flash('Invalid reclaim request', 'danger')
        return redirect(url_for('clients', show_inactive=1))

    target_client = db.session.get(Client, source_client.transferred_to_id)
    if not target_client:
        flash('Target client not found', 'danger')
        return redirect(url_for('clients', show_inactive=1))

    # Reverse the transfer: Only reclaim data originally belonging to the source client
    # This assumes the source client's code is unique and was preserved in the entries
    # But since we update the code during transfer, we need to be careful.
    # Requirement says "it takes back it data from the target client and it automates only reclaim its own data only"
    # This implies we should track original owner. For simplicity, we'll assume the code is the identifier.

    # Re-activate source client
    source_client.is_active = True

    # We need to find entries that were originally source_client's.
    # Since we updated them to target_client.code, we can't easily distinguish unless we track original_code.
    # However, if we assume the user only wants to revert the LAST transfer:
    entries_reclaimed = Entry.query.filter_by(
        client_code=target_client.code, client=target_client.name).update({
            'client':
            source_client.name,
            'client_code':
            source_client.code
        })
    bills_reclaimed = PendingBill.query.filter_by(
        client_code=target_client.code,
        client_name=target_client.name).update({
            'client_name':
            source_client.name,
            'client_code':
            source_client.code
        })

    source_client.transferred_to_id = None
    db.session.commit()

    flash(
        f'Reclaimed data for "{source_client.name}". {entries_reclaimed} entries and {bills_reclaimed} bills moved back.',
        'success')
    return redirect(url_for('clients'))


@app.route('/receiving')
@login_required
def receiving():
    mats = Material.query.order_by(Material.name.asc()).all()
    today = date.today().strftime('%Y-%m-%d')
    return render_template('receiving.html', materials=mats, today_date=today)


@app.route('/dispatching')
@login_required
def dispatching():
    mats = Material.query.order_by(Material.name.asc()).all()
    cls = Client.query.filter(Client.is_active == True).order_by(
        Client.name.asc()).all()
    today = date.today().strftime('%Y-%m-%d')
    return render_template('dispatching.html',
                           materials=mats,
                           clients=cls,
                           today_date=today)


@app.route('/add_record', methods=['POST'])
@login_required
def add_record():
    entry_date = request.form.get('date') or datetime.now().strftime(
        '%Y-%m-%d')
    # Standard User back-dated data protection
    if current_user.role == 'user' and entry_date != datetime.now().strftime(
            '%Y-%m-%d'):
        flash(
            'Permission Denied: Standard users cannot add back-dated records.',
            'danger')
        return redirect(url_for('index'))

    now = datetime.now()
    client_name = request.form.get('client')
    client_code = None
    client_obj = None
    if client_name:
        client_obj = Client.query.filter_by(name=client_name).first()
        if client_obj: client_code = client_obj.code

    # Enforce that OUT dispatches for non-registered (cash) customers use Direct Sale
    if request.form.get('type') == 'OUT' and not client_obj:
        db.session.rollback()
        flash('Unknown client: For cash customers not in your client directory, please use the Direct Sale form.', 'warning')
        # Redirect to Direct Sales page and prefill client name if provided
        return redirect(url_for('direct_sales_page', client_name=client_name or ''))

    # For registered clients, enforce that OUT dispatches only happen when there's a booking
    # for the same client and material (material booking). If none exists, ask to use Direct Sale.
    if request.form.get('type') == 'OUT' and client_obj:
        material_name = request.form.get('material')
        has_booking = BookingItem.query.join(Booking).filter(
            Booking.client_name == client_obj.name,
            BookingItem.material_name == material_name).first()
        if not has_booking:
            db.session.rollback()
            flash('No booking found for this client and material. Use Direct Sale for cash customers or create a booking first.', 'warning')
            return redirect(url_for('direct_sales_page', client_name=client_name or '', client_material=material_name or ''))

    entry = Entry(date=entry_date,
              time=now.strftime('%H:%M:%S'),
              type=request.form.get('type'),
              material=request.form.get('material'),
              client=client_name,
              client_code=client_code,
              qty=float(request.form.get('qty')),
              bill_no=request.form.get('bill_no'),
              nimbus_no=request.form.get('nimbus_no'),
              created_by=current_user.username)
    db.session.add(entry)
    db.session.flush()

    # Respect explicit 'has_bill' flag on the form. If absent, default to True
    # (backwards compatible with older forms that omit this field).
    hv = request.form.get('has_bill')
    if hv is None:
        has_bill = True
    else:
        has_bill = hv in ['on', '1', 'true', 'True']

    material_obj = Material.query.filter_by(name=entry.material).first()
    unit_price = (material_obj.unit_price if material_obj else 0) or 0
    amount = float(entry.qty) * float(unit_price)

    # Invoice creation logic: create Invoice when requested or when manual bill_no provided
    create_invoice = bool(request.form.get('create_invoice'))
    client_obj = None
    if entry.client_code:
        client_obj = Client.query.filter_by(code=entry.client_code).first()

    # Enforce manual invoice when client requires it
    if client_obj and client_obj.require_manual_invoice and entry.type == 'OUT' and not entry.bill_no and not create_invoice:
        db.session.rollback()
        flash('Manual invoice required for this client. Please provide Bill/Invoice No. or check Create Invoice.', 'danger')
        return redirect(url_for('dispatching'))

        invoice_no = None
        inv = None
        # Only create invoice if user asked for it and the transaction is considered 'has_bill'
        if has_bill and (create_invoice or entry.bill_no):
            # Prefer explicit bill_no as manual invoice
            if entry.bill_no:
                invoice_no = entry.bill_no
                is_manual = True
            else:
                # Auto-generate invoice number
                invoice_no = get_next_bill_no()
                entry.auto_bill_no = invoice_no
                is_manual = False

            # Ensure uniqueness of invoice_no across all invoices. If a collision happens on auto-generated
            # number, keep generating until we find a unique value. For manual invoice numbers, report an error
            # if the number is already used by another client.
            existing_global = Invoice.query.filter_by(invoice_no=invoice_no).first()
            if existing_global and not is_manual:
                # auto-generated collided; generate next until unique
                while Invoice.query.filter_by(invoice_no=invoice_no).first():
                    invoice_no = get_next_bill_no()
                entry.auto_bill_no = invoice_no
            elif existing_global and is_manual:
                # Manual invoice number is already in use (possibly by another client)
                if existing_global.client_code != entry.client_code:
                    db.session.rollback()
                    flash(f'Invoice number "{invoice_no}" is already used by another client. Pick a different manual invoice number.', 'danger')
                    return redirect(url_for('dispatching'))

            # Now create or update invoice for this client
            inv = Invoice.query.filter_by(invoice_no=invoice_no, client_code=entry.client_code).first()
            if inv:
                inv.client_name = entry.client
                inv.total_amount = amount
                inv.balance = amount
                inv.is_cash = bool(request.form.get('track_as_cash'))
                inv.date = datetime.strptime(entry.date, '%Y-%m-%d').date() if entry.date else datetime.now().date()
            else:
                inv = Invoice(client_code=entry.client_code,
                              client_name=entry.client,
                              invoice_no=invoice_no,
                              is_manual=is_manual,
                              date=datetime.strptime(entry.date, '%Y-%m-%d').date() if entry.date else datetime.now().date(),
                              total_amount=amount,
                              balance=amount,
                              is_cash=bool(request.form.get('track_as_cash')),
                              created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                              created_by=current_user.username)
                db.session.add(inv)
                db.session.flush()
            entry.invoice_id = inv.id

        # Case A: Billed dispatch (has explicit manual bill_no or auto_bill_no) -> create/update PendingBill
        if has_bill and (entry.bill_no or entry.auto_bill_no):
            bill_no = entry.bill_no or entry.auto_bill_no
            client_code = entry.client_code
            client_name = entry.client

            existing_pb = PendingBill.query.filter_by(bill_no=bill_no, client_code=client_code).first()
            if existing_pb:
                existing_pb.client_name = client_name
                existing_pb.amount = amount
                existing_pb.reason = f"Dispatch: {entry.material}"
                existing_pb.created_at = datetime.now().strftime('%Y-%m-%d %H:%M')
                existing_pb.created_by = current_user.username
            else:
                db.session.add(PendingBill(
                    client_code=client_code,
                    client_name=client_name,
                    bill_no=bill_no,
                    amount=amount,
                    reason=f"Dispatch: {entry.material}",
                    created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    created_by=current_user.username
                ))
        else:
            # Case B: No bill requested. If user checked 'track_as_cash', record it as a cash pending bill
            if request.form.get('track_as_cash'):
                db.session.add(PendingBill(
                    client_code=entry.client_code,
                    client_name=entry.client,
                    bill_no='',
                    amount=amount,
                    reason=f"Cash Delivery: {entry.material}",
                    is_cash=True,
                    created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    created_by=current_user.username
                ))

    db.session.commit()
    flash("Record Saved", "success")
    return redirect(url_for('index'))


@app.route('/edit_entry/<int:id>', methods=['POST'])
@login_required
def edit_entry(id):
    e = db.session.get(Entry, id)
    if not e: return redirect(url_for('index'))

    # Date Restriction
    today_str = date.today().strftime('%Y-%m-%d')
    if current_user.role != 'admin' and e.date != today_str:
        flash('Permission Denied: Only Admins can edit back-dated records.',
              'danger')
        return redirect(url_for('index'))

    old_bill_no = e.bill_no
    old_client_code = e.client_code

    e.date = request.form.get('date') or e.date
    e.time = request.form.get('time') or e.time
    e.type = request.form.get('type') or e.type
    e.material = request.form.get('material') or e.material
    e.client = request.form.get('client') if request.form.get(
        'client') else None
    if e.client:
        client_obj = Client.query.filter_by(name=e.client).first()
        if client_obj: e.client_code = client_obj.code
    else: e.client_code = None
    e.qty = float(
        request.form.get('qty')) if request.form.get('qty') else e.qty
    e.bill_no = request.form.get('bill_no') if request.form.get(
        'bill_no') else None
    e.nimbus_no = request.form.get('nimbus_no') if request.form.get(
        'nimbus_no') else None

    # Synchronize PendingBill based on this entry's OUT status and bill_no
    if e.type == 'OUT':
        # Case: bill removed on edit -> delete associated PendingBill
        if not e.bill_no and old_bill_no:
            PendingBill.query.filter_by(bill_no=old_bill_no, client_code=old_client_code).delete()
        else:
            # Try to find by new bill_no first, then fall back to old bill_no
            pb = None
            if e.bill_no:
                pb = PendingBill.query.filter_by(bill_no=e.bill_no, client_code=e.client_code).first()
            if not pb and old_bill_no:
                pb = PendingBill.query.filter_by(bill_no=old_bill_no, client_code=old_client_code).first()

            qty = e.qty
            material_obj = Material.query.filter_by(name=e.material).first()
            unit_price = (material_obj.unit_price if material_obj else 0) or 0
            amount = float(qty) * float(unit_price)

            if pb:
                pb.bill_no = e.bill_no or pb.bill_no
                pb.client_name = e.client
                pb.client_code = e.client_code
                pb.amount = amount
                pb.reason = f"Dispatch: {e.material}"
                pb.created_at = pb.created_at or datetime.now().strftime('%Y-%m-%d %H:%M')
                pb.created_by = pb.created_by or current_user.username
            else:
                if e.bill_no:
                    db.session.add(PendingBill(
                        client_code=e.client_code,
                        client_name=e.client,
                        bill_no=e.bill_no,
                        amount=amount,
                        reason=f"Dispatch: {e.material}",
                        created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                        created_by=current_user.username
                    ))

            # Ensure an Invoice exists for edited bill_no where applicable
            if e.bill_no:
                inv = Invoice.query.filter_by(invoice_no=e.bill_no, client_code=e.client_code).first()
                if not inv:
                    inv = Invoice(client_code=e.client_code,
                                  client_name=e.client,
                                  invoice_no=e.bill_no,
                                  is_manual=True,
                                  date=datetime.strptime(e.date, '%Y-%m-%d').date() if e.date else datetime.now().date(),
                                  total_amount=amount,
                                  balance=amount,
                                  created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                                  created_by=current_user.username)
                    db.session.add(inv)
                    db.session.flush()
                e.invoice_id = inv.id
            else:
                e.invoice_id = None

    db.session.commit()
    flash('Entry Updated and synchronized with Pending Bills', 'success')
    redirect_to = request.form.get('redirect_to')
    if redirect_to == 'tracking': return redirect(url_for('tracking'))
    if redirect_to == 'daily_transactions':
        return redirect(url_for('inventory.daily_transactions', date=e.date))
    return redirect(url_for('inventory.stock_summary', date=e.date))


@app.route('/delete_entry/<int:id>')
@login_required
def delete_entry(id):
    e = db.session.get(Entry, id)
    if not e: return redirect(url_for('index'))

    # Date Restriction
    today_str = date.today().strftime('%Y-%m-%d')
    if current_user.role != 'admin' and e.date != today_str:
        flash('Permission Denied: Only Admins can delete back-dated records.',
              'danger')
        return redirect(url_for('index'))

    # If deleting a dispatch entry with a bill, also delete from PendingBill?
    # Requirement 6 says "A entry change edit or delete must update in all app"
    if e.type == 'OUT' and e.bill_no:
        PendingBill.query.filter_by(bill_no=e.bill_no,
                                    client_code=e.client_code).delete()

    d = e.date
    db.session.delete(e)
    db.session.commit()
    flash('Entry Deleted and associated Pending Bill removed', 'warning')
    return redirect(url_for('inventory.daily_transactions', date=d))


@app.route('/client_ledger/<int:id>')
@login_required
def client_ledger(id):
    client = db.session.get(Client, id)
    if client:
        page = request.args.get('page', 1, type=int)
        pagination = Entry.query.filter_by(client=client.name).order_by(
            Entry.date.desc()).paginate(page=page, per_page=10)
        summary_query = db.session.query(
            Entry.material,
            func.sum(Entry.qty).label('total')).filter_by(
                client=client.name).group_by(Entry.material).all()
        summary = {row.material: row.total for row in summary_query}
        total_qty = db.session.query(func.sum(
            Entry.qty)).filter_by(client=client.name).scalar() or 0

        # Get all pending bills with photos to match by bill_no
        pending_photos = {
            b.bill_no: b.photo_url
            for b in PendingBill.query.filter(
                PendingBill.photo_url != '').all() if b.bill_no
        }

        return render_template('ledger.html',
                               client=client,
                               entries=pagination.items,
                               pagination=pagination,
                               total_qty=total_qty,
                               summary=summary,
                               pending_photos=pending_photos)
    return redirect(url_for('clients'))


@app.route('/tracking')
@login_required
def tracking():
    s = request.args.get('start_date')
    end = request.args.get('end_date')
    cl = request.args.get('client')
    m = request.args.get('material')
    bill_no = request.args.get('bill_no', '').strip()
    category = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    has_filter = bool(s or end or cl or m or search or bill_no or category)
    # New filters for type and has_bill
    type_filter = request.args.get('type', '').strip()
    has_bill_filter = request.args.get('has_bill', '').strip()
    
    if type_filter:
        # Add type to has_filter so UI shows results when only type is selected
        has_filter = True
    if has_bill_filter in ['0','1']:
        has_filter = True

    entries = []
    pagination = None
    summary = {}
    total_qty = 0

    if has_filter:
        query = Entry.query
        if s: query = query.filter(Entry.date >= s)
        if end: query = query.filter(Entry.date <= end)
        if cl: query = query.filter(Entry.client == cl)
        if m: query = query.filter(Entry.material == m)
        if bill_no: query = query.filter(db.or_(Entry.bill_no.ilike(f'%{bill_no}%'), Entry.auto_bill_no.ilike(f'%{bill_no}%')))
        if category:
            query = query.join(Client,
                               Entry.client_code == Client.code).filter(
                                   Client.category == category)
        # Apply type filter if provided
        if type_filter:
            query = query.filter(Entry.type == type_filter)
        # Apply has_bill filter: 1 => has bill, 0 => no bill
        if has_bill_filter == '1':
            query = query.filter(db.or_(Entry.bill_no != None, Entry.auto_bill_no != None)).filter(db.or_(Entry.bill_no != '', Entry.auto_bill_no != ''))
        if has_bill_filter == '0':
            query = query.filter(db.and_(Entry.bill_no == None, Entry.auto_bill_no == None))

        if search:
            query = query.filter(
                db.or_(Entry.material.ilike(f'%{search}%'),
                       Entry.client.ilike(f'%{search}%'),
                       Entry.client_code.ilike(f'%{search}%'),
                       Entry.bill_no.ilike(f'%{search}%'),
                       Entry.nimbus_no.ilike(f'%{search}%')))

        pagination = query.order_by(
            Entry.date.desc(), Entry.time.desc()).paginate(page=page,
                                                           per_page=15,
                                                           error_out=False)
        entries = pagination.items

        # Include Booking items as 'BOOKING' rows when appropriate
        booking_entries = []
        # Only include bookings if no type filter or the type filter explicitly requests bookings
        if not type_filter or type_filter == 'BOOKING':
            bq = Booking.query
            if s: bq = bq.filter(Booking.date_posted >= s)
            if end: bq = bq.filter(Booking.date_posted <= end)
            if cl: bq = bq.filter(Booking.client_name == cl)
            if search:
                bq = bq.filter(db.or_(Booking.client_name.ilike(f'%{search}%'),
                                      Booking.manual_bill_no.ilike(f'%{search}%'),
                                      Booking.auto_bill_no.ilike(f'%{search}%')))
            # material and category filters are applied at item level
            for b in bq.order_by(Booking.date_posted.desc()).all():
                for item in b.items:
                    if m and item.material_name != m:
                        continue
                    # If category filter requested, attempt to match via client lookup
                    if category:
                        cobj = Client.query.filter_by(name=b.client_name).first()
                        if not cobj or cobj.category != category:
                            continue
                    be = SimpleNamespace()
                    be.id = f"b-{item.id}"
                    be.date = b.date_posted.strftime('%Y-%m-%d') if b.date_posted else ''
                    be.time = b.date_posted.strftime('%H:%M') if b.date_posted else ''
                    be.type = 'BOOKING'
                    be.client = b.client_name
                    client_obj = Client.query.filter_by(name=b.client_name).first()
                    be.client_code = client_obj.code if client_obj else ''
                    be.material = item.material_name
                    be.qty = item.qty
                    be.bill_no = b.auto_bill_no or b.manual_bill_no or ''
                    be.nimbus_no = ''
                    be.created_by = 'Booking'
                    be.booking_id = b.id
                    be.item_id = item.id
                    booking_entries.append(be)

        # Recalculate summary with category filter if needed (include bookings as negative/reserved)
        base_query = db.session.query(
            Entry.material,
            func.sum(case((Entry.type == 'IN', Entry.qty),
                          else_=-Entry.qty)).label('net'))

        if category:
            base_query = base_query.join(
                Client, Entry.client_code == Client.code).filter(
                    Client.category == category)

        if s: base_query = base_query.filter(Entry.date >= s)
        if end: base_query = base_query.filter(Entry.date <= end)
        if cl: base_query = base_query.filter(Entry.client == cl)
        if m: base_query = base_query.filter(Entry.material == m)
        if bill_no:
            base_query = base_query.filter(Entry.bill_no.ilike(f'%{bill_no}%'))
        if search:
            base_query = base_query.filter(
                db.or_(Entry.material.ilike(f'%{search}%'),
                       Entry.client.ilike(f'%{search}%'),
                       Entry.client_code.ilike(f'%{search}%'),
                       Entry.bill_no.ilike(f'%{search}%'),
                       Entry.nimbus_no.ilike(f'%{search}%')))

        summary_query = base_query.group_by(Entry.material).all()
        summary = {row.material: row.net for row in summary_query}

        # Subtract booking quantities (bookings are reservations / outgoing) from the summary
        if booking_entries:
            # Aggregate booking quantities per material
            book_map = {}
            for be in booking_entries:
                book_map[be.material] = book_map.get(be.material, 0) + (be.qty or 0)
            for mat, q in book_map.items():
                summary[mat] = summary.get(mat, 0) - q

        total_qty = sum(summary.values()) if summary else 0

        # Merge booking entries into page results (sort by date/time desc)
        if booking_entries:
            # Convert pagination Entry objects to SimpleNamespace for uniformity
            normalized = []
            for e in entries:
                ns = SimpleNamespace(
                    id=e.id,
                    date=e.date,
                    time=e.time,
                    type=e.type,
                    client=e.client,
                    client_code=e.client_code,
                    material=e.material,
                    qty=e.qty,
                    bill_no=e.bill_no or '',
                    nimbus_no=e.nimbus_no or '',
                    created_by=e.created_by if hasattr(e, 'created_by') else None
                )
                normalized.append(ns)
            normalized.extend(booking_entries)
            # Sort by date desc then time desc
            normalized.sort(key=lambda x: (x.date or '', x.time or ''), reverse=True)
            entries = normalized
            # Disable pagination when bookings are merged (simpler UX)
            pagination = None

    today_str = date.today().strftime('%Y-%m-%d')
    # Get all pending bills with photos to match by bill_no
    pending_photos = {
        b.bill_no: b.photo_url
        for b in PendingBill.query.filter(PendingBill.photo_url != '').all()
        if b.bill_no
    }

    return render_template(
        'tracking.html',
        entries=entries,
        pagination=pagination,
        clients=Client.query.filter(Client.is_active == True).order_by(
            Client.name.asc()).all(),
        materials=Material.query.order_by(Material.name.asc()).all(),
        start_date=s,
        end_date=end,
        client_filter=cl,
        material_filter=m,
        bill_no_filter=bill_no,
        category_filter=category,
        search_query=search,
        now_date=today_str,
        total_qty=total_qty,
        summary=summary,
        has_filter=has_filter,
        pending_photos=pending_photos,
        type_filter=type_filter,
        has_bill_filter=has_bill_filter)


@app.route('/import_jumble')
@login_required
def import_jumble_view():
    return render_template('import_jumble.html')


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', users=User.query.all())


@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin': return redirect(url_for('index'))
    un = request.form.get('username')
    pw = generate_password_hash(str(request.form.get('password')))
    rl = request.form.get('role')

    if User.query.filter_by(username=un).first():
        flash('Username exists', 'danger')
    else:
        new_u = User(username=un,
                     password_hash=pw,
                     role=rl,
                     can_view_stock='can_view_stock' in request.form,
                     can_view_daily='can_view_daily' in request.form,
                     can_view_history='can_view_history' in request.form,
                     can_import_export='can_import_export' in request.form,
                     can_manage_directory='can_manage_directory'
                     in request.form)
        db.session.add(new_u)
        db.session.commit()
        flash('User Created', 'success')
    return redirect(url_for('settings'))


@app.route('/edit_user_permissions/<int:id>', methods=['POST'])
@login_required
def edit_user_permissions(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    u = db.session.get(User, id)
    if u and u.username != 'admin':
        u.role = request.form.get('role')
        u.can_view_stock = 'can_view_stock' in request.form
        u.can_view_daily = 'can_view_daily' in request.form
        u.can_view_history = 'can_view_history' in request.form
        u.can_import_export = 'can_import_export' in request.form
        u.can_manage_directory = 'can_manage_directory' in request.form
        # Store restriction for standard users (back-dated editing)
        u.restrict_backdated_edit = (request.form.get('role') == 'user')
        db.session.commit()
        flash('Permissions Updated', 'success')
    return redirect(url_for('settings'))


@app.route('/delete_user/<int:id>')
@login_required
def delete_user(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    u = db.session.get(User, id)
    if u:
        db.session.delete(u)
        db.session.commit()
        flash('User Removed', 'warning')
    return redirect(url_for('settings'))


@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_user.password_hash = generate_password_hash(
        str(request.form.get('password')))
    db.session.commit()
    flash('Password Updated', 'success')
    return redirect(url_for('settings'))


@app.route('/delete_selected_data', methods=['POST'])
@login_required
def delete_selected_data():
    if current_user.role != 'admin': return redirect(url_for('index'))

    if request.form.get('confirm_text') != "DELETE SELECTED":
        flash('Incorrect confirmation text', 'danger')
        return redirect(url_for('settings'))

    targets = request.form.getlist('delete_targets')
    if not targets:
        flash('No datasets selected for deletion', 'warning')
        return redirect(url_for('settings'))

    try:
        deleted_info = []
        if 'clients' in targets:
            Client.query.delete()
            deleted_info.append('Clients')
        if 'pending_bills' in targets:
            PendingBill.query.delete()
            deleted_info.append('Pending Bills')
        if 'dispatching' in targets:
            Entry.query.filter_by(type='OUT').delete()
            deleted_info.append('Dispatching Entries')
        if 'receiving' in targets:
            Entry.query.filter_by(type='IN').delete()
            deleted_info.append('Receiving Entries')
        if 'materials' in targets:
            Material.query.delete()
            deleted_info.append('Materials')
        if 'direct_sales' in targets:
            # Remove line items first to avoid FK issues, then sales
            DirectSaleItem.query.delete()
            DirectSale.query.delete()
            deleted_info.append('Direct Sales')
        if 'payments' in targets:
            Payment.query.delete()
            deleted_info.append('Payments')
        if 'bookings' in targets:
            # Remove booking items then bookings
            BookingItem.query.delete()
            Booking.query.delete()
            deleted_info.append('Bookings')

        db.session.commit()
        flash(f'Data Wiped: {", ".join(deleted_info)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Wipe failed: {str(e)}', 'danger')

    return redirect(url_for('settings'))


@app.route('/delete_all_data', methods=['POST'])
@login_required
def delete_all_data():
    # Deprecated in favor of delete_selected_data, but kept for legacy
    return redirect(url_for('settings'))


@app.route('/api/check_bill/<path:bill_no>')
@login_required
def check_bill_api(bill_no):
    entry = Entry.query.filter_by(bill_no=bill_no).first()
    if entry:
        return jsonify({
            'exists': True,
            'url': url_for('tracking', search=bill_no),
            'material': entry.material,
            'qty': int(entry.qty)
        })
    return jsonify({'exists': False})


@app.route('/toggle_bill_paid/<int:id>', methods=['POST'])
@login_required
def toggle_bill_paid(id):
    bill = db.session.get(PendingBill, id)
    if bill:
        bill.is_paid = not bill.is_paid
        db.session.commit()
        return jsonify({'success': True, 'is_paid': bill.is_paid})
    return jsonify({'success': False}), 404


@app.route('/pending_bills')
@login_required
def pending_bills():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '').strip()
    filters = {
        'client_code': request.args.get('client_code', '').strip(),
        'bill_no': request.args.get('bill_no', '').strip(),
        'bill_from': request.args.get('bill_from', '').strip(),
        'bill_to': request.args.get('bill_to', '').strip(),
        'category': category,
        'is_cash': request.args.get('is_cash', '').strip()
    }
    query = PendingBill.query
    if filters['client_code']:
        query = query.filter(PendingBill.client_code == filters['client_code'])
    if filters['bill_no']:
        query = query.filter(PendingBill.bill_no == filters['bill_no'])
    if filters['is_cash'] != '':
        query = query.filter(PendingBill.is_cash == (filters['is_cash'] == '1'))

    if filters['bill_from'] and filters['bill_to']:
        try:
            bf = int(filters['bill_from'])
            bt = int(filters['bill_to'])
            # We need to cast bill_no to integer for comparison if possible
            # SQLite casting: CAST(bill_no AS INTEGER)
            query = query.filter(
                func.cast(PendingBill.bill_no, db.Integer).between(bf, bt))
        except:
            pass

    if category:
        query = query.join(Client,
                           PendingBill.client_code == Client.code).filter(
                               Client.category == category)

    # Handle "CASH" general code requirement
    # We can add a special filter or just ensure it shows up in search
    if filters['bill_no'] == 'CASH':
        query = query.filter(PendingBill.bill_no == 'CASH')

    # Sort by Bill Number ascending (numeric) for sequential view
    pagination = query.order_by(
        func.cast(PendingBill.bill_no, db.Integer).asc()).paginate(page=page,
                                                                   per_page=15)

    # Alphabetical order for all client lists
    active_clients = Client.query.filter(Client.is_active == True).order_by(
        Client.name.asc()).all()
    # Ensure Materials are also alphabetical
    materials = Material.query.order_by(Material.name.asc()).all()
    return render_template('pending_bills.html',
                           bills=pagination.items,
                           pagination=pagination,
                           filters=filters,
                           clients=active_clients,
                           materials=materials)


@app.route('/add_pending_bill', methods=['POST'])
@login_required
def add_pending_bill():
    client_code = request.form.get('client_code', '').strip()
    client_obj = Client.query.filter_by(code=client_code).first()

    if not client_obj:
        flash(
            'Invalid Client Code. Client must exist in the Client Directory.',
            'danger')
        return redirect(url_for('pending_bills'))

    bill = PendingBill(client_code=client_code,
                       client_name=client_obj.name,
                       bill_no=request.form.get('bill_no', '').strip(),
                       nimbus_no=request.form.get('nimbus_no', '').strip(),
                       amount=float(request.form.get('amount') or 0),
                       reason=request.form.get('reason', '').strip(),
                       photo_url=request.form.get('photo_url', '').strip(),
                       created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                       created_by=current_user.username)
    db.session.add(bill)
    db.session.commit()
    flash('Pending bill added', 'success')
    return redirect(url_for('pending_bills'))


@app.route('/edit_pending_bill/<int:id>', methods=['POST'])
@login_required
def edit_pending_bill(id):
    bill = db.session.get(PendingBill, id)
    if bill:
        old_bill_no = bill.bill_no
        old_client_code = bill.client_code
        client_code = request.form.get('client_code', '').strip()
        client_obj = Client.query.filter_by(code=client_code).first()

        if not client_obj:
            flash(
                'Invalid Client Code. Client must exist in the Client Directory.',
                'danger')
            return redirect(url_for('pending_bills'))

        bill.client_code = client_code
        bill.client_name = client_obj.name
        bill.bill_no = request.form.get('bill_no', '').strip()
        bill.nimbus_no = request.form.get('nimbus_no', '').strip()
        bill.amount = float(request.form.get('amount') or 0)
        bill.reason = request.form.get('reason', '').strip()
        bill.photo_url = request.form.get('photo_url', '').strip()

        # Global Data Consistency: Propagate changes to Dispatching entries
        # If Bill No or Client changed, update matching entries
        update_data = {
            'bill_no': bill.bill_no,
            'client': bill.client_name,
            'client_code': bill.client_code
        }
        Entry.query.filter_by(bill_no=old_bill_no,
                              client_code=old_client_code).update(update_data)

        db.session.commit()
        flash('Bill updated and synchronized across system', 'success')
    return redirect(url_for('pending_bills'))


@app.route('/delete_pending_bill/<int:id>')
@login_required
def delete_pending_bill(id):
    bill = db.session.get(PendingBill, id)
    if bill:
        # Standard User back-dated protection
        if current_user.role == 'user':
            bill_date = bill.created_at[:10]
            if bill_date != date.today().strftime('%Y-%m-%d'):
                flash('Standard users cannot delete back-dated bills.',
                      'danger')
                return redirect(url_for('pending_bills'))
        db.session.delete(bill)
        db.session.commit()
        flash('Bill deleted', 'warning')
    return redirect(url_for('pending_bills'))


@app.route('/export_pending_bills')
@login_required
def export_pending_bills():
    import pandas as pd
    import io
    fmt = request.args.get('format', 'excel')
    bills = PendingBill.query.all()
    data = [{
        'ClientCode': b.client_code,
        'BillNo': b.bill_no,
        'ClientName': b.client_name,
        'Amount': b.amount,
        'Reason': b.reason,
        'NimbusNo': b.nimbus_no
    } for b in bills]
    df = pd.DataFrame(data)
    if fmt == 'csv':
        from flask import Response
        return Response(
            df.to_csv(index=False),
            mimetype="text/csv",
            headers={
                "Content-disposition":
                f"attachment; filename=pending_bills_{date.today()}.csv"
            })
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    from flask import send_file
    return send_file(output,
                     as_attachment=True,
                     download_name=f"pending_bills_{date.today()}.xlsx")


@app.route('/import_pending_bills', methods=['POST'])
@login_required
def import_pending_bills():
    import pandas as pd
    import io
    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file selected', 'danger')
        return redirect(url_for('pending_bills'))

    try:
        if file.filename.endswith('.csv'):
            # Use low_memory=False to avoid DtypeWarning and handle large files better
            df = pd.read_csv(file, low_memory=False)
        else:
            df = pd.read_excel(file)

        # Mandatory Rule: Every row with a Bill No is required
        count = 0
        for _, row in df.iterrows():
            bill_no = str(row.get('BillNo', '')).strip() if pd.notna(
                row.get('BillNo')) else ''
            code = str(row.get('ClientCode', '')).strip() if pd.notna(
                row.get('ClientCode')) else ''
            name = str(row.get('ClientName', '')).strip() if pd.notna(
                row.get('ClientName')) else ''

            if not bill_no or bill_no == 'nan' or bill_no == 'NO BILL':
                continue

            if not name or name == 'nan' or name == 'EMPTY':
                name = "Unknown"

            try:
                amount_str = str(row.get('Amount', '0')).replace(',',
                                                                 '').strip()
                amount = float(
                    amount_str) if amount_str and amount_str != 'nan' else 0
            except:
                amount = 0

            reason = str(row.get('Reason', '')).strip() if pd.notna(
                row.get('Reason')) and str(row.get('Reason')) != 'nan' else ''
            nimbus_no = str(
                row.get('NimbusNo',
                        '')).strip() if pd.notna(row.get('NimbusNo')) and str(
                            row.get('NimbusNo')) != 'nan' else ''

            # Sync with Clients list
            client = None
            if code and code != 'NA':
                client = Client.query.filter_by(code=code).first()

            if not client and name and name != 'Unknown' and name != 'EMPTY' and name != 'NO NAME':
                client = Client.query.filter_by(name=name).first()

            if not client:
                new_code = code if code and code != 'NA' else generate_client_code(
                )
                client = Client(code=new_code, name=name, is_active=True)
                db.session.add(client)
                db.session.flush()

            # Add pending bill
            bill = PendingBill(
                client_code=client.code,
                client_name=client.name,
                bill_no=bill_no,
                amount=amount,
                reason=reason,
                nimbus_no=nimbus_no,
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                created_by=current_user.username)
            db.session.add(bill)
            count += 1

        db.session.commit()
        flash(
            f'Successfully imported {count} pending bills and synced clients.',
            'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Import failed: {str(e)}', 'danger')

    return redirect(url_for('pending_bills'))


@app.route('/confirm_import', methods=['POST'])
@login_required
def confirm_import():
    try:
        data = request.form.get('import_data')
        if not data:
            flash('No data to import', 'warning')
            return redirect(url_for('pending_bills'))

        import json
        imported_list = json.loads(data)
        count = 0
        for item in imported_list:
            client = None
            code = item.get('client_code', '').strip()
            name = item.get('client_name', '').strip()

            if code and code != 'NA':
                client = Client.query.filter_by(code=code).first()
            if not client and name and name != 'EMPTY' and name != 'NO NAME' and name != 'NO BILL':
                client = Client.query.filter_by(name=name).first()

            if not client:
                # If name is 'Unknown', still create or find it
                new_code = code if code and code != 'NA' else generate_client_code(
                )
                client = Client(code=new_code, name=name, is_active=True)
                db.session.add(client)
                db.session.flush()  # Get ID and ensure code is unique

            bill = PendingBill(
                client_code=client.code,
                client_name=client.name,
                bill_no=item.get('bill_no'),
                amount=item.get('amount', 0),
                reason=item.get('reason', ''),
                nimbus_no=item.get('nimbus_no', ''),
                created_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
                created_by=current_user.username)
            db.session.add(bill)
            count += 1

        db.session.commit()
        flash(f'Successfully imported {count} pending bills.', 'success')
    except Exception as e:
        db.session.rollback()
        import traceback
        print(traceback.format_exc())
        flash(f'Confirmation failed: {str(e)}', 'danger')

    return redirect(url_for('pending_bills'))


# `_ensure_user_password_column` moved earlier to run at module import-time to
# ensure the `password_hash` column exists before any queries execute.

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        _ensure_user_password_column()
        if not User.query.filter_by(username='admin').first():
            db.session.add(
                User(username='admin',
                     password_hash=generate_password_hash('admin123'),
                     role='admin'))
            db.session.commit()
    app.run(host='0.0.0.0', port=5000)
