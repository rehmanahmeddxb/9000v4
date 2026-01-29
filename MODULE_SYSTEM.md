# Module System Documentation

## Overview
This project uses an **automated module-based architecture** where blueprints are automatically discovered and registered. No manual registration is required - just create a new module and it will be loaded automatically.

## Architecture

### Directory Structure
```
/workspaces/9000v4/
├── app.py                 # Main Flask app factory with auto-loader
├── models.py              # Database models
├── main.py                # Legacy routes (to be refactored into modules)
├── blueprints/            # Blueprint modules (auto-discovered)
│   ├── __init__.py
│   ├── data_lab.py        # Data analysis module
│   ├── import_export.py   # Import/Export module
│   └── inventory.py       # Inventory management module
├── utils/                 # Utility modules
│   ├── __init__.py
│   └── module_loader.py   # Automatic module discovery & registration
└── templates/             # HTML templates
```

## Creating a New Module

### Step 1: Create Module File
Create a new file in the `blueprints/` directory (e.g., `blueprints/my_module.py`):

```python
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from models import db, YourModel

# Module configuration (optional but recommended)
MODULE_CONFIG = {
    'name': 'My Module',
    'description': 'Description of what this module does',
    'url_prefix': '/my_module',  # URL prefix for routes
    'enabled': True               # Toggle module on/off
}

# Create blueprint (must be named 'bp' or '*_bp')
my_bp = Blueprint('my_module', __name__)

# Define your routes
@my_bp.route('/')
@login_required
def dashboard():
    return render_template('my_template.html')

@my_bp.route('/api/data')
@login_required
def get_data():
    return jsonify({'data': 'value'})

@my_bp.route('/submit', methods=['POST'])
@login_required
def submit_data():
    # Handle form submission
    return redirect(url_for('my_module.dashboard'))
```

### Step 2: Auto-Registration
The module will be automatically registered when the Flask app starts. The `load_modules()` function in `app.py` will:
1. Discover your new blueprint file
2. Import the module
3. Find all Blueprint objects (variables ending with `_bp` or named `bp`)
4. Register them with Flask using the configured URL prefix

### Blueprint Naming Conventions

**Valid blueprint variable names:**
- `bp = Blueprint('name', __name__)`
- `my_module_bp = Blueprint('name', __name__)`
- `auth_bp = Blueprint('auth', __name__)`

**Invalid (won't be discovered):**
- `blueprint = Blueprint('name', __name__)` ❌
- `route = Blueprint('name', __name__)` ❌

## Module Configuration

### MODULE_CONFIG Dictionary
Optional configuration at the top of your module:

```python
MODULE_CONFIG = {
    'name': 'Display Name',           # User-friendly name
    'description': 'What it does',    # Short description
    'url_prefix': '/custom_prefix',   # Custom URL prefix (overrides default)
    'enabled': True,                  # Enable/disable module
    'version': '1.0.0',              # Optional: module version
    'dependencies': ['other_module']  # Optional: required modules
}
```

## Module Functions

### Available in each module:
- **Request context**: Access to `request`, `session`, `current_user`, etc.
- **Database**: Use `db` from models for queries
- **Templates**: Render templates from the templates/ directory
- **URL Building**: Use `url_for()` for navigation between modules

### Template Location
Templates for modules should be placed in `templates/` directory with descriptive names:
- `templates/my_module_dashboard.html`
- `templates/my_module_form.html`

## How Auto-Registration Works

The `load_modules()` function (in `utils/module_loader.py`):

1. **Discovery**: Scans the `blueprints/` directory for `.py` files
2. **Import**: Dynamically imports each module
3. **Detection**: Finds all Flask Blueprint objects in the module
4. **Registration**: Registers blueprints with Flask app using:
   - Module name as default URL prefix (e.g., `inventory.py` → `/inventory`)
   - Custom `url_prefix` from `MODULE_CONFIG` if provided
5. **Logging**: Prints registration status for each blueprint

### Console Output Example
```
✓ Registered blueprint 'data_lab' from module 'data_lab' at '/data_lab'
✓ Registered blueprint 'import_export' from module 'import_export' at '/import_export'
✓ Registered blueprint 'inventory' from module 'inventory' at '/inventory'
```

## Existing Modules

### Data Lab (`blueprints/data_lab.py`)
- **Prefix**: `/data_lab`
- **Functions**: Data analysis, reconciliation, file uploads
- **Key Routes**:
  - `GET /data_lab/` - Upload interface

### Import/Export (`blueprints/import_export.py`)
- **Prefix**: `/import_export`
- **Functions**: Data import/export, Excel/CSV handling
- **Key Routes**:
  - `GET /import_export/import_export` - Main interface
  - `GET /import_export/export/<format>` - Export data

### Inventory (`blueprints/inventory.py`)
- **Prefix**: `/inventory`
- **Functions**: Stock tracking, daily transactions
- **Key Routes**:
  - `GET /inventory/stock_summary` - Stock overview
  - `GET /inventory/daily_transactions` - Daily logs

## Migration Guide (main.py → Modules)

The `main.py` file contains legacy routes. To migrate routes to the modular system:

1. **Identify related routes** in `main.py`
2. **Create new module** (e.g., `blueprints/clients.py`)
3. **Move routes** to the new module
4. **Replace `app.route()` with `bp.route()`**
5. **Delete from main.py** after migration
6. **No registration needed** - module auto-loads

### Example Migration

**Before (in main.py):**
```python
@app.route('/clients')
@login_required
def clients():
    return render_template('clients.html', clients=Client.query.all())

@app.route('/client/add', methods=['POST'])
@login_required
def add_client():
    # ... client creation logic ...
    return redirect(url_for('clients'))
```

**After (in blueprints/clients.py):**
```python
from flask import Blueprint, render_template, redirect, url_for, request
from models import db, Client
from flask_login import login_required

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/')
@login_required
def clients():
    return render_template('clients.html', clients=Client.query.all())

@clients_bp.route('/add', methods=['POST'])
@login_required
def add_client():
    # ... client creation logic ...
    return redirect(url_for('clients.clients'))  # Note: prefix with blueprint name
```

## Best Practices

1. **One module per feature**: Group related routes together
2. **Use descriptive names**: Module name should reflect its function
3. **Add MODULE_CONFIG**: Makes your module discoverable and configurable
4. **Keep modules focused**: Don't mix unrelated functionality
5. **Reuse templates**: Use consistent naming for templates
6. **Handle errors**: Use proper Flask error handlers and logging
7. **Comment your routes**: Document what each route does

## Troubleshooting

### Module not loading?
1. Check the file is in `blueprints/` directory
2. Verify blueprint variable is named correctly (ends with `_bp` or is `bp`)
3. Check console output for error messages
4. Ensure valid Python syntax

### Routes returning 404?
1. Check the URL prefix: `http://localhost:5000/module_name/route`
2. Verify blueprint name in route decorator: `@bp.route('/path')`
3. Check `url_for()` uses correct blueprint name

### Template not found?
1. Template should be in `templates/` directory
2. Use template filename, not module name
3. Example: `render_template('clients.html')` not `render_template('clients_module/clients.html')`

## Admin/Monitoring

To list all loaded modules programmatically:

```python
from utils.module_loader import get_modules_info

modules = get_modules_info('blueprints')
for module_name, blueprints in modules:
    print(f"Module: {module_name}, Blueprints: {blueprints}")
```

Create an admin dashboard route to show module status:

```python
from utils.module_loader import get_modules_info

@admin_bp.route('/modules')
@admin_required
def module_status():
    modules = get_modules_info('blueprints')
    return render_template('admin/modules.html', modules=modules)
```

## Next Steps

1. ✅ Move remaining routes from `main.py` to dedicated modules
2. ✅ Create new modules for features as needed
3. ✅ Update cross-module navigation with proper `url_for()` calls
4. ✅ Create admin dashboard showing loaded modules
