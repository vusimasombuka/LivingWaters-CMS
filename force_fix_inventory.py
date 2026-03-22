from app import create_app, db
from sqlalchemy import text
import os

app = create_app()

with app.app_context():
    print("⚠️  DELETING and RECREATING inventory tables...")
    
    # Force drop tables with raw SQL
    sql_commands = """
    DROP TABLE IF EXISTS stock_responsible_person;
    DROP TABLE IF EXISTS inventory_item;
    DROP TABLE IF EXISTS department;
    
    CREATE TABLE department (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL UNIQUE
    );
    
    CREATE TABLE inventory_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(150) NOT NULL,
        quantity INTEGER DEFAULT 1,
        notes TEXT,
        min_stock_level INTEGER DEFAULT 0 NOT NULL,
        is_low_stock_alert_active BOOLEAN DEFAULT 0,
        last_replenished_at DATETIME,
        last_sms_sent_at DATETIME,
        last_email_sent_at DATETIME,
        department_id INTEGER NOT NULL,
        branch_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES department (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    );
    
    CREATE TABLE stock_responsible_person (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_item_id INTEGER NOT NULL,
        name VARCHAR(100) NOT NULL,
        phone VARCHAR(20),
        email VARCHAR(120),
        notify_sms BOOLEAN DEFAULT 1,
        notify_email BOOLEAN DEFAULT 1,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_item (id)
    );
    """
    
    # Execute each statement
    for statement in sql_commands.strip().split(';'):
        if statement.strip():
            db.session.execute(text(statement.strip()))
    
    db.session.commit()
    
    # Verify
    result = db.session.execute(text("PRAGMA table_info(inventory_item)"))
    columns = [row[1] for row in result]
    print(f"\n✅ Inventory item columns: {columns}")
    
    if 'min_stock_level' in columns:
        print("✅ SUCCESS! min_stock_level column exists!")
    else:
        print("❌ Still missing...")