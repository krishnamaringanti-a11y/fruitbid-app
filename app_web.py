# File: app_web.py

import streamlit as st
import Fruitbidapp

st.set_page_config(page_title="🍉 FruitBid Launcher", layout="wide")

st.title("🍎 FruitBid Chat App")
st.write("Welcome to FruitBid — Smart Fruit Auction Platform")

st.divider()

st.info("This launcher connects to your FruitBid core module (Fruitbidapp.py).")

user_input = st.text_area("Enter text or question (optional):", "")

if st.button("Run FruitBid App"):
    with st.spinner("Launching FruitBid..."):
        try:
            # Try to call Fruitbidapp.main() if it exists
            if hasattr(Fruitbidapp, "main"):
                result = Fruitbidapp.main(user_input)
                st.success("✅ FruitBid ran successfully!")
                if result is not None:
                    st.write("### Result:")
                    st.write(result)
            else:
                st.warning("⚠️ No 'main()' function found in Fruitbidapp.py. "
                           "Please run it directly with:")
                st.code("streamlit run Fruitbidapp.py", language="bash")
        except Exception as e:
            st.error(f"🚨 Error launching FruitBid: {e}")

st.divider()
st.caption("Developed with ❤️ — FruitBid Platform © 2025")
