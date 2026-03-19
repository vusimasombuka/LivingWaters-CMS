import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add your app to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.visitor import Visitor
from app.models.branch import Branch

# ==========================================
# CONFIGURATION
# ==========================================
EXCEL_FILE = "VISITORS FORM MASTER.xlsx"
TARGET_BRANCH_ID = 1  # Your confirmed branch ID
SKIP_DUPLICATE_PHONES = True  # Skip if phone already exists in DB
# ==========================================

def clean_value(val):
    """Clean Excel values - handle NaN, empty strings, dashes"""
    if pd.isna(val):
        return None
    val = str(val).strip()
    if val in ['', '--', '----', '-----', 'None', 'nan']:
        return None
    return val

def normalize_phone(phone):
    """
    Normalize phone number to +27 format
    Returns (primary_phone, alternative_phone) tuple
    """
    if not phone:
        return None, None
    
    # Handle multiple phones separated by / or \
    phones = str(phone).replace('\\', '/').split('/')
    phones = [p.strip() for p in phones if p.strip()]
    
    normalized = []
    for p in phones:
        # Remove spaces and non-numeric except +
        cleaned = ''.join(c for c in p if c.isdigit() or c == '+')
        
        # Convert SA numbers to +27 format
        if cleaned.startswith('0') and len(cleaned) == 10:
            cleaned = '+27' + cleaned[1:]
        elif cleaned.startswith('27') and len(cleaned) == 11:
            cleaned = '+' + cleaned
        elif not cleaned.startswith('+') and len(cleaned) == 10:
            cleaned = '+27' + cleaned[1:] if cleaned.startswith('0') else None
        
        if cleaned and cleaned.startswith('+'):
            normalized.append(cleaned)
    
    if not normalized:
        return None, None
    elif len(normalized) == 1:
        return normalized[0], None
    else:
        # Return first as primary, rest joined as alternative
        return normalized[0], '/'.join(normalized[1:])

def import_visitors():
    app = create_app()
    
    with app.app_context():
        print(f"🔌 Database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Verify branch exists
        branch = Branch.query.get(TARGET_BRANCH_ID)
        if not branch:
            print(f"❌ Error: Branch ID {TARGET_BRANCH_ID} not found!")
            print("Available branches:")
            for b in Branch.query.all():
                print(f"  - ID {b.id}: {b.name}")
            return
        
        print(f"🏢 Importing visitors to branch: {branch.name} (ID: {TARGET_BRANCH_ID})\n")
        
        # Read Excel
        try:
            df = pd.read_excel(EXCEL_FILE, sheet_name=0)
            print(f"📊 Found {len(df)} rows in Excel\n")
        except Exception as e:
            print(f"❌ Error reading Excel: {e}")
            return
        
        success = 0
        skipped = 0
        errors = 0
        duplicates = 0
        
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (1-based + header)
            
            try:
                # Skip header row if duplicated in data
                if str(row.get('Name')).upper() == 'NAME':
                    continue
                
                # Clean name fields (REQUIRED)
                first_name = clean_value(row.get('Name'))
                last_name = clean_value(row.get('Surname'))
                
                # Skip if no name data
                if not first_name or not last_name:
                    print(f"⚠️  Row {row_num}: Skipped (missing name)")
                    skipped += 1
                    continue
                
                # Clean optional fields
                title = clean_value(row.get('Title'))  # Not stored, just for logging
                phone_raw = clean_value(row.get('Phone'))
                
                # Normalize names (Title Case)
                first_name = first_name.title()
                last_name = last_name.title()
                
                # Handle phone(s)
                phone, alternative = normalize_phone(phone_raw)
                
                # Check for duplicates by primary phone
                if phone and SKIP_DUPLICATE_PHONES:
                    existing = Visitor.query.filter_by(phone=phone).first()
                    if existing:
                        print(f"⚠️  Row {row_num}: Duplicate phone ({phone}) - {first_name} {last_name}")
                        duplicates += 1
                        continue
                
                # Note: Date of Birth and Marital Status exist in Excel but 
                # aren't in the Visitor model. They'll be preserved when 
                # converting this visitor to a member later.
                
                # Create visitor
                visitor = Visitor(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    alternative_contact=alternative,  # Stores second phone if present
                    email=None,  # Not in Excel
                    branch_id=TARGET_BRANCH_ID
                )
                
                db.session.add(visitor)
                
                # Commit in batches of 10
                if (success + 1) % 10 == 0:
                    db.session.commit()
                
                success += 1
                
                # Log with title if available
                title_display = f"{title} " if title else ""
                alt_display = f" (+ alt: {alternative})" if alternative else ""
                print(f"✅ Row {row_num}: {title_display}{first_name} {last_name}{alt_display}")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Row {row_num}: Error - {str(e)}")
                errors += 1
                continue
        
        # Final commit
        db.session.commit()
        
        print(f"\n{'='*50}")
        print(f"IMPORT COMPLETE")
        print(f"{'='*50}")
        print(f"✅ Successfully imported: {success}")
        print(f"⚠️  Skipped (no name): {skipped}")
        print(f"⚠️  Duplicates skipped: {duplicates}")
        print(f"❌ Errors: {errors}")
        print(f"{'='*50}")
        print("\n💡 Note: Date of Birth and Marital Status aren't stored for visitors.")
        print("   This info will transfer when you convert them to members.")

if __name__ == "__main__":
    # Safety check
    if TARGET_BRANCH_ID == 1:
        print("⚠️  WARNING: Using default Branch ID 1.")
        print("Make sure this is correct, or change TARGET_BRANCH_ID in the script.\n")
        input("Press Enter to continue or Ctrl+C to cancel...")
    
    import_visitors()