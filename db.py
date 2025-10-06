import sqlite3
import streamlit as st
from datetime import datetime

DB_FILE = 'fruitbid.db'

# 🥭 Create or reuse cached database connection
@st.cache_resource
def get_db_connection():
    """Create a cached SQLite database connection."""
    try:
        return sqlite3.connect(DB_FILE, check_same_thread=False)
    except sqlite3.Error as e:
        st.error(f"Database connection error: {str(e)}")
        return None


def init_db():
    """Initialize database schema."""
    conn = get_db_connection()
    if conn is None:
        return

    try:
        c = conn.cursor()

        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mobile_email TEXT UNIQUE NOT NULL,
                address TEXT NOT NULL,
                verified BOOLEAN NOT NULL
            )
        ''')

        # Create items table
        c.execute('''
            CREATE TABLE IF NOT EXISTS items (
                name TEXT PRIMARY KEY,
                min_bid REAL NOT NULL,
                market_cap REAL NOT NULL
            )
        ''')

        # ✅ Ensure billing_rate column exists in items table
        try:
            c.execute("ALTER TABLE items ADD COLUMN billing_rate REAL DEFAULT 0.05")
        except sqlite3.OperationalError:
            # Column already exists — ignore
            pass

        # Create bids table
        c.execute('''
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                bid_amount REAL NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY(item_name) REFERENCES items(name),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        # Create lucky_dip table
        c.execute('''
            CREATE TABLE IF NOT EXISTS lucky_dip (
                item_name TEXT PRIMARY KEY,
                user_id INTEGER,
                bid_amount REAL,
                FOREIGN KEY(item_name) REFERENCES items(name),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')

        # Create settings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Create otps table
        c.execute('''
            CREATE TABLE IF NOT EXISTS otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mobile_email TEXT NOT NULL,
                otp TEXT NOT NULL,
                expiration DATETIME NOT NULL
            )
        ''')

        # Create nutrition table
        c.execute('''
            CREATE TABLE IF NOT EXISTS nutrition (
                item_name TEXT PRIMARY KEY,
                calories REAL,
                fiber REAL,
                vit_c REAL,
                potassium REAL,
                notes TEXT,
                FOREIGN KEY(item_name) REFERENCES items(name)
            )
        ''')

        conn.commit()

    except sqlite3.Error as e:
        st.error(f"Database initialization error: {str(e)}")
    # No close for cached conn


# ✅ Independent helper to get items list
@st.cache_data(ttl=300)
def get_items():
    """Fetch list of items from database."""
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM items")
        return [row[0] for row in c.fetchall()]
    except sqlite3.Error as e:
        st.error(f"Error getting items: {str(e)}")
        return []
def get_min_bid(item_name):
    """Fetch the minimum bid for a specific item."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        c = conn.cursor()
        c.execute("SELECT min_bid FROM items WHERE name = ?", (item_name,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        st.error(f"Error fetching minimum bid: {str(e)}")
        return None
def get_market_cap(item_name):
    """Fetch the market cap for a specific item."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        c = conn.cursor()
        c.execute("SELECT market_cap FROM items WHERE name = ?", (item_name,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        st.error(f"Error fetching market cap: {str(e)}")
        return None
def get_highest_bid(item_name):
    """Fetch the highest bid for a given item."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        c = conn.cursor()
        c.execute("SELECT MAX(bid_amount) FROM bids WHERE item_name = ?", (item_name,))
        row = c.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.Error as e:
        st.error(f"Error fetching highest bid: {str(e)}")
        return None
def get_billing_rate(item_name):
    """Fetch the billing rate for a given item."""
    conn = get_db_connection()
    if conn is None:
        return 0.05  # default fallback
    try:
        c = conn.cursor()
        c.execute("SELECT billing_rate FROM items WHERE name = ?", (item_name,))
        row = c.fetchone()
        return row[0] if row and row[0] is not None else 0.05
    except sqlite3.Error as e:
        st.error(f"Error getting billing rate: {str(e)}")
        return 0.05
def get_user_id(mobile_email):
    """Fetch user ID based on mobile/email."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE mobile_email=?", (mobile_email,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        st.error(f"Error getting user ID: {str(e)}")
        return None


def get_setting(key):
    """Fetch an app setting value."""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        st.error(f"Error getting setting: {str(e)}")
        return None


def set_setting(key, value):
    """Insert or update an app setting."""
    conn = get_db_connection()
    if conn is None:
        return
    try:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error setting value: {str(e)}")


def initialize_items():
    """Insert default fruit items into database if empty."""
    conn = get_db_connection()
    if conn is None:
        return
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM items")
        if c.fetchone()[0] == 0:
            initial_items = [
                ('Apple', 100.0, 200.0, 0.05),
                ('Mosambi', 40.0, 60.0, 0.05),
                ('Banana', 30.0, 50.0, 0.05),
                ('Papaya', 40.0, 60.0, 0.05),
                ('Kiwi', 150.0, 250.0, 0.05),
                ('Dragon Fruit', 200.0, 300.0, 0.05),
                ('Pineapple', 50.0, 80.0, 0.05),
                ('Custard Apple', 80.0, 120.0, 0.05),
                ('Sapota', 50.0, 70.0, 0.05)
            ]
            c.executemany(
                "INSERT INTO items (name, min_bid, market_cap, billing_rate) VALUES (?, ?, ?, ?)",
                initial_items
            )
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Error initializing items: {str(e)}")
