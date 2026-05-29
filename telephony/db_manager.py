import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../v_engine.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Campaigns table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        contact_name TEXT NOT NULL,
        phone_number TEXT,
        email_address TEXT,
        bottlenecks TEXT,
        value_prop TEXT,
        draft_message TEXT,
        draft_email TEXT,
        status TEXT DEFAULT 'PENDING_APPROVAL',
        last_incoming_message TEXT,
        last_outgoing_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Dynamically migrate database schema to support V-Engine 2.0 multi-channel decisions
    try:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN channel_strategy TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN strategy_rationale TEXT")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

def add_campaign(company_name, contact_name, phone_number=None, email_address=None, bottlenecks=None, value_prop=None, draft_message=None, draft_email=None, channel_strategy=None, strategy_rationale=None):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO campaigns (company_name, contact_name, phone_number, email_address, bottlenecks, value_prop, draft_message, draft_email, channel_strategy, strategy_rationale, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_APPROVAL')
    """, (company_name, contact_name, phone_number, email_address, bottlenecks, value_prop, draft_message, draft_email, channel_strategy, strategy_rationale))
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id

def get_campaign(campaign_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_campaign_by_phone(phone_number):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Normalize phone numbers for search
    clean_phone = phone_number.replace("+", "").replace(" ", "").split("@")[0]
    cursor.execute("SELECT * FROM campaigns WHERE phone_number LIKE ?", (f"%{clean_phone}%",))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_campaign_status(campaign_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaigns SET status = ? WHERE id = ?", (status, campaign_id))
    conn.commit()
    conn.close()

def get_stats():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM campaigns")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'PENDING_APPROVAL'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status IN ('SENT', 'APPROVED')")
    sent = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'REPLIED'")
    replied = cursor.fetchone()[0]
    
    conn.close()
    
    success_rate = 0.0
    if sent > 0:
        success_rate = round((replied / sent) * 100.0, 1)
        
    return {
        "total": total,
        "pending": pending,
        "sent": sent,
        "replied": replied,
        "success_rate": success_rate
    }
