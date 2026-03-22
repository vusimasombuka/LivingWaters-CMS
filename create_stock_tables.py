from app import create_app, db
from app.models.inventory import InventoryItem, StockResponsiblePerson

app = create_app()

with app.app_context():
    # Create only new tables (won't delete existing data)
    db.create_all()
    print("✅ Stock alert tables created successfully!")
    
    # Verify
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"\nCurrent tables: {tables}")
    
    if 'stock_responsible_person' in tables:
        print("✅ StockResponsiblePerson table exists")
    else:
        print("❌ StockResponsiblePerson table missing")