# File: app_web.py

import streamlit as st
from Fruitbidapp import main  # we'll adjust this if your main logic function has another name

st.set_page_config(page_title="FruitBid Chat", layout="wide")
st.title("🍎 FruitBid Chat App")

st.write("Welcome! Type your input below:")

# Input area
user_input = st.text_area("Enter text or question:")

# Button to run your logic
if st.button("Run"):
    with st.spinner("Running your app..."):
        try:
            result = main(user_input)   # runs your Python function
            st.success("Done!")
            st.write("### Result:")
            st.write(result)
        except Exception as e:
            st.error(f"Error: {e}")
