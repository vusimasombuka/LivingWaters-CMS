import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add your app to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models.member import Member
from app.models.branch import Branch

# ==========================================
# CONFIGURATION - CHANGE THESE
# ==========================================
EXCEL_FILE = "MEMBERS FORM MASTER.xlsx"
TARGET_BRANCH_ID = 1  # ⚠️ CHANGE THIS TO YOUR ACTUAL BRANCH ID
SKIP_DUPLICATE_PHONES = True  # Skip if phone already exists in DB
# ==========================================

def excel_serial_to_date(serial):
    """Convert Excel date serial number to Python date"""
    if pd.isna(serial) or serial == "":
        return None
    try:
        # Excel epoch is 1900-01-00 (with leap year bug consideration)
        # 21916 = ~1960-01-01
        excel_epoch = datetime(1899, 12, 30)
        if isinstance(serial, (int, float)):
            return (excel_epoch + timedelta(days=int(serial))).date()
        return None
    except:
        return None

def clean_value(val):
    """Clean Excel values - handle NaN, empty strings, dashes"""
    if pd.isna(val):
        return None
    val = str(val).strip()
    if val in ['', '--', '----', 'None', 'nan']:
        return None
    return val

def normalize_phone(phone):
    """
    Basic phone normalization (fallback if your utils aren't available)
    Converts '063 131 7270' to '0631317270' and adds +27 if needed
    """
    if not phone:
        return None
    
    # Remove spaces, dashes, and non-numeric except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Remove leading zero and add +27 for SA numbers
    if cleaned.startswith('0') and len(cleaned) == 10:
        return '+27' + cleaned[1:]
    elif cleaned.startswith('27') and len(cleaned) == 11:
        return '+' + cleaned
    elif not cleaned.startswith('+') and len(cleaned) == 10:
        return '+27' + cleaned[1:] if cleaned.startswith('0') else None
    
    return cleaned if cleaned.startswith('+') else None

def import_members():
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
        
        print(f"🏢 Importing to branch: {branch.name} (ID: {TARGET_BRANCH_ID})\n")
        
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
                if str(row.get('Names')).upper() == 'NAMES':
                    continue
                
                # Clean required fields
                first_name = clean_value(row.get('Names'))
                last_name = clean_value(row.get('Surname'))
                
                # Skip if no name data
                if not first_name or not last_name:
                    print(f"⚠️  Row {row_num}: Skipped (missing name)")
                    skipped += 1
                    continue
                
                # Clean optional fields
                title = clean_value(row.get('Title'))
                address = clean_value(row.get('Address'))
                phone_raw = clean_value(row.get('Phone'))
                marital = clean_value(row.get('Marital Status'))
                employment = clean_value(row.get('Employment Status'))
                dob_serial = row.get('DOB')
                
                # Convert title to proper case (MRS -> Mrs)
                if title:
                    title = title.title()
                
                # Convert names to Title Case (SARAH -> Sarah)
                first_name = first_name.title()
                last_name = last_name.title()
                
                # Handle phone
                phone = normalize_phone(phone_raw)
                
                # Check for duplicates by phone
                if phone and SKIP_DUPLICATE_PHONES:
                    existing = Member.query.filter_by(phone=phone).first()
                    if existing:
                        print(f"⚠️  Row {row_num}: Duplicate phone ({phone}) - {first_name} {last_name}")
                        duplicates += 1
                        continue
                
                # Handle DOB conversion
                dob = excel_serial_to_date(dob_serial)
                
                # Map employment status to occupation field
                occupation = employment.title() if employment else None
                marital_status = marital.title() if marital else None
                
                # Handle address - split into street and section if comma exists
                street = address
                section = None
                if address and ',' in address:
                    parts = [p.strip() for p in address.split(',')]
                    street = parts[0]
                    section = parts[1] if len(parts) > 1 else None
                
                # Create member
                member = Member(
                    title=title,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    street_address=street,
                    section=section,
                    marital_status=marital_status,
                    occupation=occupation,
                    date_of_birth=dob,
                    branch_id=TARGET_BRANCH_ID,
                    member_status='active',
                    membership_course=False,
                    baptized=False
                    # email, id_number, emergency contact left as None
                )
                
                db.session.add(member)
                
                # Commit in batches of 10
                if (success + 1) % 10 == 0:
                    db.session.commit()
                
                success += 1
                print(f"✅ Row {row_num}: {first_name} {last_name}")
                
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

if __name__ == "__main__":
    # Safety check
    if TARGET_BRANCH_ID == 1:
        print("⚠️  WARNING: Using default Branch ID 1.")
        print("Make sure this is correct, or change TARGET_BRANCH_ID in the script.\n")
        input("Press Enter to continue or Ctrl+C to cancel...")
    
    import_members()