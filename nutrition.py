import streamlit as st
import pandas as pd
from db import get_db_connection


def initialize_nutrition():
    """Initialize default nutrition data in the database if missing."""
    conn = get_db_connection()
    if conn is None:
        return

    nutrition_data = [
        ('Apple', 52, 2.4, 4.6, 107, 'Rich in antioxidants'),
        ('Banana', 89, 2.6, 8.7, 358, 'Good potassium source'),
        ('Papaya', 43, 1.7, 60.9, 182, 'High in Vitamin C'),
        ('Kiwi', 41, 3.0, 92.7, 312, 'Boosts immunity'),
        ('Dragon Fruit', 50, 3.0, 9.0, 268, 'High in fiber'),
        ('Pineapple', 50, 1.4, 47.8, 109, 'Aids digestion'),
        ('Custard Apple', 94, 2.4, 36.3, 382, 'High in calories'),
        ('Sapota', 83, 5.3, 14.7, 193, 'Rich in dietary fiber')
    ]

    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM nutrition")
        if c.fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO nutrition (item_name, calories, fiber, vit_c, potassium, notes) VALUES (?, ?, ?, ?, ?, ?)",
                nutrition_data
            )
            conn.commit()
    except Exception as e:
        st.error(f"Error initializing nutrition data: {str(e)}")


@st.cache_data(ttl=300)
def get_nutrition_data():
    """Fetch nutrition data from the database."""
    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    try:
        query = "SELECT * FROM nutrition"
        return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Error fetching nutrition data: {str(e)}")
        return pd.DataFrame()
