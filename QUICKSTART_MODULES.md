# Quick Start: Adding New Modules

## The Problem (Before)
- Manual blueprint registration in `app.py`
- Adding new features required modifying core app file
- Risk of forgetting to register blueprints
- No clear separation of concerns

## The Solution (After)
- **Auto-discovery**: Drop a new module file in `blueprints/` and it loads automatically
- **Zero config**: No changes needed to `app.py`
- **Modular**: Each feature is completely independent
- **Scalable**: Add as many modules as needed

---

## Creating Your First Module (30 seconds)

### Step 1: Create the File
Create `blueprints/my_feature.py`:

```python
from flask import Blueprint, render_template
from flask_login import login_required

MODULE_CONFIG = {
    'name': 'My Feature',
    'description': 'Does something cool',
    'url_prefix': '/my_feature',
    'enabled': True
}

my_bp = Blueprint('my_feature', __name__)

@my_bp.route('/')
@login_required
def index():
    return render_template('my_feature_index.html')

@my_bp.route('/action')
@login_required
def action():
    return {'status': 'success'}
```

### Step 2: Create Template
Create `templates/my_feature_index.html`:

```html
{% extends "layout.html" %}

{% block content %}
<h1>My Feature</h1>
<p>Hello from my new module!</p>
{% endblock %}
```

### Step 3: Done!
- Restart the app
- Visit: `http://localhost:5000/my_feature/`
- Your module is loaded! ✅

---

## File Naming Rules

**Blueprint variables (MUST follow these patterns):**
```python
✅ my_bp = Blueprint(...)
✅ my_module_bp = Blueprint(...)
✅ feature_bp = Blueprint(...)
✅ auth_bp = Blueprint(...)

❌ my_blueprint = Blueprint(...)  # Won't be discovered
❌ bp_my = Blueprint(...)         # Wrong order
❌ my = Blueprint(...)             # Missing _bp
```

**File naming (just descriptive):**
```
blueprints/clients.py          ✅
blueprints/inventory.py        ✅
blueprints/user_management.py  ✅
blueprints/utils.py            ❌ (no routes, won't register)
```

---

## Real-World Examples

### Example 1: Simple CRUD Module

```python
# blueprints/products.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product

MODULE_CONFIG = {
    'name': 'Products',
    'url_prefix': '/products',
    'enabled': True
}

products_bp = Blueprint('products', __name__)

@products_bp.route('/')
def list():
    products = Product.query.all()
    return render_template('products_list.html', products=products)

@products_bp.route('/add', methods=['POST'])
def add():
    product = Product(name=request.form['name'])
    db.session.add(product)
    db.session.commit()
    flash('Product added!')
    return redirect(url_for('products.list'))

@products_bp.route('/<id>/delete', methods=['POST'])
def delete(id):
    Product.query.get_or_404(id).delete()
    db.session.commit()
    return redirect(url_for('products.list'))
```

Access at: `/products/`, `/products/add`, `/products/1/delete`

### Example 2: API Module

```python
# blueprints/api.py
from flask import Blueprint, jsonify, request
from flask_login import login_required
from models import db, Data

MODULE_CONFIG = {
    'name': 'API',
    'url_prefix': '/api',
    'enabled': True
}

api_bp = Blueprint('api', __name__)

@api_bp.route('/data')
@login_required
def get_data():
    data = Data.query.all()
    return jsonify([{'id': d.id, 'value': d.value} for d in data])

@api_bp.route('/data', methods=['POST'])
@login_required
def create_data():
    data = Data(value=request.json['value'])
    db.session.add(data)
    db.session.commit()
    return jsonify({'id': data.id, 'status': 'created'}), 201

@api_bp.route('/data/<id>', methods=['PUT'])
@login_required
def update_data(id):
    data = Data.query.get_or_404(id)
    data.value = request.json['value']
    db.session.commit()
    return jsonify({'status': 'updated'})
```

Access at: `/api/data`, `/api/data/<id>`

### Example 3: Multi-Blueprint Module

Some modules might have multiple related blueprints:

```python
# blueprints/reports.py
from flask import Blueprint, render_template
from flask_login import login_required

MODULE_CONFIG = {
    'name': 'Reports',
    'url_prefix': '/reports',
    'enabled': True
}

# Main module
reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
def dashboard():
    return render_template('reports_dashboard.html')

# Additional blueprint for analytics
analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/')
def analytics_dashboard():
    return render_template('analytics_dashboard.html')

# Both will be auto-registered!
# /reports/
# /analytics/
```

---

## Common Patterns

### Pattern 1: Database Operations

```python
from models import db, YourModel

@bp.route('/create', methods=['POST'])
def create():
    obj = YourModel(name=request.form['name'])
    db.session.add(obj)
    db.session.commit()
    return redirect(url_for('module.list'))
```

### Pattern 2: User Authorization

```python
from flask_login import login_required, current_user

@bp.route('/')
@login_required
def secure_page():
    if current_user.role != 'admin':
        abort(403)
    return render_template('admin_panel.html')
```

### Pattern 3: Forms with Validation

```python
@bp.route('/form', methods=['GET', 'POST'])
def form_handler():
    if request.method == 'POST':
        # Validate
        if not request.form.get('email'):
            flash('Email required', 'error')
            return redirect(url_for('module.form_handler'))
        
        # Process
        # ...
        
        flash('Saved!', 'success')
        return redirect(url_for('module.view'))
    
    return render_template('form.html')
```

### Pattern 4: API with JSON

```python
from flask import jsonify

@bp.route('/api/status')
def status():
    return jsonify({
        'status': 'ok',
        'modules_loaded': 5,
        'timestamp': '2024-01-29'
    })
```

### Pattern 5: File Upload

```python
from werkzeug.utils import secure_filename
import os

@bp.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join('uploads', filename))
        flash('File uploaded!')
    return redirect(url_for('module.list'))
```

---

## Testing Your Module

### 1. Check Module Loaded
Look for this in the startup logs:
```
✓ Registered blueprint 'my_feature' from module 'my_feature' at '/my_feature'
```

### 2. Test Routes
```bash
curl http://localhost:5000/my_feature/
curl http://localhost:5000/my_feature/action
```

### 3. Check Admin Dashboard
Visit: `http://localhost:5000/admin/modules` (if you're an admin)

---

## Troubleshooting

### "Module not loading"
- Is the file in `blueprints/` folder?
- Does it have `Blueprint('name', __name__)`?
- Is the variable named `*_bp` or `bp`?
- Check for Python syntax errors

### "404 on my route"
- Check URL: `http://localhost:5000/{url_prefix}/{route}`
- Restart the app after creating file
- Check `MODULE_CONFIG['url_prefix']`

### "Template not found"
- Templates go in `templates/` folder
- Use filename, not path: `render_template('my_feature.html')`
- Match template name to file name

---

## Best Practices

1. **Name clearly**: `blueprints/user_management.py` not `blueprints/um.py`
2. **Add MODULE_CONFIG**: Helps with documentation and discoverability
3. **Keep related routes together**: Group by feature, not by HTTP method
4. **Use proper authentication**: `@login_required` on protected routes
5. **Error handling**: Use try/catch for database and file operations
6. **Logging**: Add print/log statements for debugging
7. **Comments**: Document complex logic
8. **Consistent templates**: Use naming convention for templates

---

## Next Steps

1. ✅ Create your first module
2. ✅ Add more routes to it
3. ✅ Create connected templates
4. ✅ Use database queries
5. ✅ Add form handling
6. ✅ Implement file uploads/downloads
7. ✅ Add API endpoints
8. ✅ Build a dashboard

See `MODULE_SYSTEM.md` for complete documentation.
