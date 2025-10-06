import streamlit as st
import re
import os
import requests
import bcrypt
from db import get_setting

def validate_mobile(val):
    """Validate mobile number format (+91xxxxxxxxxx)."""
    return bool(re.match(r'^\+91\d{10}$', val))

def validate_email(val):
    """Validate email format."""
    return bool(re.match(r'[^@]+@[^@]+\.[^@]+', val))

def check_admin_password(password):
    """Check admin password against hashed value."""
    ADMIN_PASSWORD_HASH = bcrypt.hashpw(os.getenv('ADMIN_PASSWORD', 'admin123').encode(), bcrypt.gensalt())
    return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH)

def fetch_real_time_price(item):
    """Fetch real-time price from API with fallback."""
    try:
        # Placeholder: Replace with actual API (e.g., JioMart, BigBasket)
        # response = requests.get(f"https://api.example.com/price?item={item}", headers={"API-KEY": os.getenv("PRICE_API_KEY")})
        # if response.status_code == 200:
        #     return response.json()['price']
        MARKET_PRICES = {
            'Apple': 200, 'Mosambi': 50, 'Banana': 40, 'Papaya': 50, 'Kiwi': 200,
            'Dragon Fruit': 250, 'Pineapple': 60, 'Custard Apple': 100, 'Sapota': 60,
            'Mango': 120, 'Spinach': 30, 'Honey': 300
        }
        return MARKET_PRICES.get(item, 100)
    except Exception as e:
        st.warning(f"Price API error: {str(e)}. Using fallback.")
        return 100

@st.cache_data(ttl=60)
def monitor_prices(item):
    """Calculate billing price with discount."""
    market_price = fetch_real_time_price(item)
    discount = float(get_setting('discount_pct', 20))
    return market_price * (1 - discount / 100)