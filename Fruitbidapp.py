import random
import sqlite3
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import base64
import os
from datetime import datetime, timedelta
import tempfile

from db import (
    get_db_connection,
    init_db,
    get_items,
    get_min_bid,
    get_market_cap,
    get_highest_bid,
    get_billing_rate,
    get_user_id,
    get_setting,
    set_setting,
    initialize_items,
)
from otp import send_otp, verify_otp
from nutrition import initialize_nutrition, get_nutrition_data
from utils import (
    validate_mobile,
    validate_email,
    check_admin_password,
    fetch_real_time_price,
    monitor_prices,
)


from typing import Optional

def main(user_input: Optional[str] = None):
    """
    Main Streamlit app UI for FruitBid.
    If user_input is provided (string), the function will attempt to process and return a string result.
    Otherwise it renders the interactive Streamlit UI.
    """

    # Initialize DB and default data (safe to call multiple times)
    init_db()
    initialize_items()
    initialize_nutrition()

    # Ensure critical default settings exist
    if get_setting("discount_pct") is None:
        set_setting("discount_pct", 20)

    if get_setting("bid_start") is None:
        set_setting("bid_start", datetime.now().isoformat())

    # Page setup
    st.set_page_config(page_title="FruitBid", layout="centered", initial_sidebar_state="collapsed")

    # If called as a simple function (from app_web) and user_input provided:
    if user_input:
        # For simplicity, return a processed acknowledgement — you can replace with actual logic
        return f"Received input: {user_input}"

    # --- PDF helper class ---
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, "FruitBid Report", 0, 1, "C")

        def add_content(self, img1_path, img2_path, bid_data, user_data, nutrition_data):
            self.add_page()
            self.set_font("Arial", "", 10)
            self.cell(
                0,
                10,
                f"Market grows to USD 88.9 billion by 2030. Billing at {get_setting('discount_pct')} percent off cheapest platform. Women farmers lead.",
                0,
                1,
            )
            self.ln(10)

            # Bids section
            for _, row in bid_data.iterrows():
                billing_key = f"Billing Rate INR {get_setting('discount_pct')}pct off"
                self.cell(
                    0,
                    10,
                    f"{row['Item']}  Min {row['Min Bid INR']}  Cap {row['Max Cap INR']}  Highest {row['Highest Bid INR']}  Billing {row[billing_key]}  Lucky {row['Lucky Dip Winner']}",
                    0,
                    1,
                )

            self.ln(10)
            self.cell(0, 10, "Users", 0, 1)
            for _, row in user_data.iterrows():
                self.cell(0, 10, f"{row['mobile_email']}  {row['address']}", 0, 1)

            self.ln(10)
            self.cell(0, 10, "Nutrition Info (Per 100g)", 0, 1)
            for _, row in nutrition_data.iterrows():
                self.cell(
                    0,
                    10,
                    f"{row['item_name']}: Calories {row['calories']}, Fiber {row['fiber']}g, Vit C {row['vit_c']}mg, Potassium {row['potassium']}mg, Notes: {row['notes']}",
                    0,
                    1,
                )
            try:
                if img1_path:
                    self.image(img1_path, x=10, y=None, w=90)
                if img2_path:
                    self.image(img2_path, x=110, y=None, w=90)
            except Exception:
                # ignore missing images in PDF generation
                pass

    # --- Chart helpers (cached) ---
    @st.cache_data(ttl=30)
    def create_bids_chart(items):
        try:
            fig, ax = plt.subplots()
            highest_bids = [get_highest_bid(item) or 0 for item in items]
            billing_rates = [get_billing_rate(item) or 0 for item in items]
            ax.bar(items, highest_bids, alpha=0.5, label="Highest Bid")
            ax.bar(items, billing_rates, alpha=0.7, label="Billing Rate")
            ax.set_ylabel("INR per kg")
            ax.tick_params(axis="x", rotation=45)
            ax.legend()
            plt.tight_layout()
            return fig
        except Exception as e:
            st.error(f"Error generating bids chart: {str(e)}")
            return None

    @st.cache_data(ttl=300)
    def create_market_growth_chart():
        try:
            market_data = pd.DataFrame({"Year": [2024, 2030], "Market Size USD Billion": [66.3, 88.9]})
            fig = px.line(
                market_data,
                x="Year",
                y="Market Size USD Billion",
                markers=True,
                title="Projected Market Growth",
                labels={"Market Size USD Billion": "USD Billion"},
            )
            fig.update_traces(hovertemplate="Year: %{x}<br>Size: %{y} USD Billion")
            fig.update_layout(xaxis_title="Year", yaxis_title="Market Size USD Billion")
            return fig
        except Exception as e:
            st.error(f"Error generating market chart: {str(e)}")
            return None

    # --- App session and timing setup ---
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "current_user_id" not in st.session_state:
        st.session_state.current_user_id = None
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    if "temp_reg" not in st.session_state:
        st.session_state.temp_reg = None

    bid_start_str = get_setting("bid_start")
    bid_start = datetime.fromisoformat(bid_start_str) if bid_start_str else datetime.now()
    days_elapsed = (datetime.now() - bid_start).days
    bidding_open = days_elapsed < 3
    remaining = timedelta(days=3) - (datetime.now() - bid_start)
    if bidding_open:
        st.markdown(f"**Time left for bidding: {remaining}**")

    # --- Admin login ---
    with st.expander("Admin Login"):
        admin_pass = st.text_input("Admin Password", type="password", help="Enter the admin password to access controls.")
        if st.button("Login as Admin"):
            if check_admin_password(admin_pass):
                st.session_state.admin_logged = True
                st.success("Admin logged in successfully")
            else:
                st.error("Incorrect password")

    # --- Registration form ---
    st.subheader("Register to Bid")
    with st.form("register_form"):
        reg_type = st.radio("Register with", ["Mobile", "Email"], help="Choose mobile or email for OTP verification.")
        reg_id = st.text_input("Mobile Number (+91xxxxxxxxxx) or Email", help="Enter a valid mobile number or email.")
        address = st.text_area("Delivery Address", help="Provide a complete delivery address.")
        submit_reg = st.form_submit_button("Generate OTP")

    if submit_reg:
        valid_id = (reg_type == "Mobile" and validate_mobile(reg_id)) or (reg_type == "Email" and validate_email(reg_id))
        if valid_id and address.strip():
            if send_otp(reg_id, reg_type):
                st.session_state.temp_reg = {"reg_id": reg_id, "address": address}
                st.info("OTP sent. Check your phone or email.")
            else:
                st.error("Failed to send OTP. Try again or check configuration.")
        else:
            st.error("Invalid mobile/email format or empty address. Please correct and try again.")

    # --- OTP verification ---
    with st.form("otp_form"):
        otp_input = st.text_input("Enter OTP", help="Enter the 4-6 digit OTP received.")
        submit_otp = st.form_submit_button("Verify and Register")

    if submit_otp and "temp_reg" in st.session_state:
        if verify_otp(st.session_state.temp_reg["reg_id"], otp_input):
            data = st.session_state.temp_reg
            conn = get_db_connection()
            if conn:
                try:
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO users (mobile_email, address, verified) VALUES (?, ?, 1)",
                        (data["reg_id"], data["address"]),
                    )
                    conn.commit()
                    st.success(f"Registered successfully: {data['reg_id']}. You can now login.")
                    del st.session_state.temp_reg
                except sqlite3.IntegrityError:
                    st.error("User already registered. Please login instead.")
                except sqlite3.Error as e:
                    st.error(f"Registration error: {str(e)}")
        else:
            st.error("Invalid or expired OTP. Please try again.")

    # --- User login ---
    st.subheader("Login to Bid")
    login_id = st.text_input("Mobile Number or Email for Login", help="Enter your registered mobile or email.")
    if st.button("Login"):
        user_id = get_user_id(login_id)
        if user_id:
            st.session_state.current_user = login_id
            st.session_state.current_user_id = user_id
            st.success(f"Logged in as {login_id}")
        else:
            st.error("User not found or not verified. Please register or check details.")

    # --- Monitor billing and lucky dip (after bidding closes) ---
    if not bidding_open:
        billing_calculated = get_setting("billing_calculated")
        if billing_calculated != bid_start.isoformat():
            conn = get_db_connection()
            if conn:
                try:
                    for item in get_items():
                        billing = monitor_prices(item)
                        set_setting(f"billing_{item}", billing)
                    set_setting("billing_calculated", bid_start.isoformat())
                except Exception as e:
                    st.error(f"Error calculating billing: {str(e)}")

        conn = get_db_connection()
        if conn:
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM lucky_dip")
                if c.fetchone()[0] == 0:
                    for item in get_items():
                        c.execute("SELECT user_id, bid_amount FROM bids WHERE item_name=?", (item,))
                        bids_list = c.fetchall()
                        if bids_list:
                            winner = random.choice(bids_list)
                            c.execute("INSERT INTO lucky_dip (item_name, user_id, bid_amount) VALUES (?, ?, ?)", (item, winner[0], winner[1]))
                    conn.commit()
            except sqlite3.Error as e:
                st.error(f"Error calculating lucky dip: {str(e)}")

    # --- Admin panels ---
    if st.session_state.admin_logged:
        with st.expander("Admin Manage Items and Discount"):
            with st.form("item_form"):
                new_item = st.text_input("Add New Item e.g. Mango Spinach Honey")
                new_min_bid = st.number_input("Minimum Bid INR per kg", min_value=0.0, step=1.0)
                new_market_cap = st.number_input("Market Cap INR per kg", min_value=0.0, step=1.0)
                discount_pct = st.number_input(
                    "Discount Percent for Cycle",
                    min_value=0.0,
                    max_value=100.0,
                    step=1.0,
                    value=float(get_setting("discount_pct") or 20),
                )
                if st.form_submit_button("Add Item and Update Discount"):
                    if new_item.strip():
                        conn = get_db_connection()
                        if conn:
                            try:
                                c = conn.cursor()
                                c.execute("INSERT INTO items (name, min_bid, market_cap) VALUES (?, ?, ?)", (new_item, new_min_bid, new_market_cap))
                                conn.commit()
                                st.success(f"Item {new_item} added")
                                get_items.clear()
                            except sqlite3.IntegrityError:
                                st.error("Item already exists")
                            except sqlite3.Error as e:
                                st.error(f"Error adding item: {str(e)}")
                    if 0 <= discount_pct <= 100:
                        set_setting("discount_pct", discount_pct)
                        monitor_prices.clear()
                        get_billing_rate.clear()
                        st.success(f"Discount set to {discount_pct}%")
                    else:
                        st.error("Discount must be between 0 and 100%.")

        with st.expander("Admin Update Minimum Bids"):
            items = get_items()
            with st.form("min_bids_form"):
                new_min_bids = {}
                for item in items:
                    new_min_bids[item] = st.number_input(
                        f"Minimum Bid for {item} INR per kg",
                        value=get_min_bid(item) or 0.0,
                        min_value=0.0,
                        step=1.0,
                        key=f"min_{item}",
                    )
                if st.form_submit_button("Update Minimum Bids"):
                    conn = get_db_connection()
                    if conn:
                        try:
                            c = conn.cursor()
                            for item, new_bid in new_min_bids.items():
                                c.execute("UPDATE items SET min_bid = ? WHERE name=?", (new_bid, item))
                            conn.commit()
                            st.success("Minimum bids updated")
                            get_min_bid.clear()
                            get_highest_bid.clear()
                        except sqlite3.Error as e:
                            st.error(f"Error updating bids: {str(e)}")

        with st.expander("Admin Update Nutrition"):
            item = st.selectbox("Select Item to Update Nutrition", get_items())
            if item:
                conn = get_db_connection()
                if conn:
                    try:
                        c = conn.cursor()
                        c.execute("SELECT calories, fiber, vit_c, potassium, notes FROM nutrition WHERE item_name=?", (item,))
                        row = c.fetchone()
                        calories, fiber, vit_c, potassium, notes = (row if row else (0, 0, 0, 0, ""))
                        with st.form("nutrition_form"):
                            new_cal = st.number_input("Calories", value=float(calories), min_value=0.0)
                            new_fiber = st.number_input("Fiber (g)", value=float(fiber), min_value=0.0)
                            new_vit_c = st.number_input("Vitamin C (mg)", value=float(vit_c), min_value=0.0)
                            new_k = st.number_input("Potassium (mg)", value=float(potassium), min_value=0.0)
                            new_notes = st.text_area("Notes", value=notes)
                            if st.form_submit_button("Update Nutrition"):
                                c.execute(
                                    "INSERT OR REPLACE INTO nutrition (item_name, calories, fiber, vit_c, potassium, notes) VALUES (?, ?, ?, ?, ?, ?)",
                                    (item, new_cal, new_fiber, new_vit_c, new_k, new_notes),
                                )
                                conn.commit()
                                st.success(f"Nutrition for {item} updated.")
                                get_nutrition_data.clear()
                    except sqlite3.Error as e:
                        st.error(f"Error updating nutrition: {str(e)}")

        with st.expander("Admin Reset Bid Cycle"):
            if st.button("Reset Bid Cycle"):
                conn = get_db_connection()
                if conn:
                    try:
                        set_setting("bid_start", datetime.now().isoformat())
                        c = conn.cursor()
                        c.execute("DELETE FROM bids")
                        c.execute("DELETE FROM lucky_dip")
                        conn.commit()
                        set_setting("billing_calculated", None)
                        for item in get_items():
                            set_setting(f"billing_{item}", None)
                        st.success("Bid cycle reset")
                        get_highest_bid.clear()
                        get_billing_rate.clear()
                    except sqlite3.Error as e:
                        st.error(f"Error resetting cycle: {str(e)}")

    # --- Bidding interface ---
    if bidding_open and st.session_state.current_user:
        st.subheader(f"Place Bid - Days Left: {3 - days_elapsed}")
        item = st.selectbox("Select Item", get_items())
        cap = get_market_cap(item) or 0
        min_bid = get_min_bid(item) or 0
        current_highest = get_highest_bid(item) or 0
        bid_amount = st.number_input(f"Your Bid INR per kg (Max {cap}, Must > {current_highest})", min_value=0.0, step=1.0)
        if st.button("Submit Bid"):
            conn = get_db_connection()
            if conn:
                try:
                    c = conn.cursor()
                    c.execute(
                        "SELECT bid_amount FROM bids WHERE item_name=? AND user_id=? ORDER BY bid_amount DESC LIMIT 1",
                        (item, st.session_state.current_user_id),
                    )
                    existing = c.fetchone()
                    if existing and bid_amount <= existing[0]:
                        st.error("You already have a higher or equal bid. Increase to update.")
                    elif bid_amount > cap:
                        st.error(f"Bid exceeds market cap {cap} INR for {item}. Please lower your bid.")
                    elif bid_amount <= current_highest:
                        st.error(f"Bid must exceed current highest {current_highest} INR. Please increase your bid.")
                    elif bid_amount < min_bid:
                        st.error(f"Bid must be at least minimum {min_bid} INR. Please adjust.")
                    else:
                        c.execute(
                            "INSERT INTO bids (item_name, user_id, bid_amount, timestamp) VALUES (?, ?, ?, ?)",
                            (item, st.session_state.current_user_id, bid_amount, datetime.now().isoformat()),
                        )
                        conn.commit()
                        st.success(f"Bid confirmed for {item}: {bid_amount} INR. Thank you!")
                        get_highest_bid.clear()
                except sqlite3.Error as e:
                    st.error(f"Error submitting bid: {str(e)}")
    elif not st.session_state.current_user:
        st.info("Please login to place bids.")
    else:
        st.info(f"Bidding closed. Delivery scheduled for {(bid_start + timedelta(days=4)).strftime('%Y-%m-%d')}. Billing at {get_setting('discount_pct')}% discount. Check lucky dip below.")

    # --- User bids ---
    if st.session_state.current_user:
        st.subheader("Your Bids")
        conn = get_db_connection()
        if conn:
            try:
                user_bids = pd.read_sql_query(
                    "SELECT item_name, bid_amount, timestamp FROM bids WHERE user_id=? ORDER BY timestamp DESC",
                    conn,
                    params=(st.session_state.current_user_id,),
                )
                if not user_bids.empty:
                    st.table(user_bids)
                else:
                    st.info("No bids placed yet.")
            except sqlite3.Error as e:
                st.error(f"Error fetching your bids: {str(e)}")

    # --- Current bids data ---
    st.subheader("Current Bids, Billing, and Addresses")
    items = get_items()
    bid_data_list = []
    conn = get_db_connection()
    if conn:
        try:
            for item in items:
                highest_bid = get_highest_bid(item) or 0
                billing_rate = get_billing_rate(item) or 0
                c = conn.cursor()
                c.execute(
                    "SELECT u.mobile_email, ld.bid_amount FROM lucky_dip ld JOIN users u ON ld.user_id = u.id WHERE ld.item_name=?",
                    (item,),
                )
                lucky_row = c.fetchone()
                lucky_winner = f"{lucky_row[0]} {lucky_row[1]} INR" if lucky_row else "No Bids"
                bid_data_list.append(
                    {
                        "Item": item,
                        "Min Bid INR": get_min_bid(item),
                        "Max Cap INR": get_market_cap(item),
                        "Highest Bid INR": highest_bid,
                        f'Billing Rate INR {get_setting("discount_pct")}pct off': billing_rate,
                        "Lucky Dip Winner": lucky_winner,
                    }
                )
            bid_data = pd.DataFrame(bid_data_list)
            st.table(bid_data)
        except sqlite3.Error as e:
            st.error(f"Error displaying bid data: {str(e)}")

    # --- Registered users ---
    st.subheader("Registered Users")
    conn = get_db_connection()
    if conn:
        try:
            user_data = pd.read_sql_query("SELECT mobile_email, address FROM users", conn)
            st.table(user_data)
        except sqlite3.Error as e:
            st.error(f"Error fetching users: {str(e)}")

    # --- Nutritional info ---
    st.subheader("Nutritional Information (Per 100g, for Health Awareness)")
    try:
        nutrition_data = get_nutrition_data()
        if not nutrition_data.empty:
            for _, row in nutrition_data.iterrows():
                with st.expander(f"{row['item_name']} Nutrition"):
                    st.write(f"Calories: {row['calories']}")
                    st.write(f"Fiber: {row['fiber']}g")
                    st.write(f"Vitamin C: {row['vit_c']}mg")
                    st.write(f"Potassium: {row['potassium']}mg")
                    st.write(row["notes"])
        else:
            st.info("No nutritional data available.")
    except Exception as e:
        st.error(f"Error fetching nutrition: {str(e)}")

    # --- Feminist perspective ---
    st.subheader("Empowering Women Farmers")
    st.markdown(
        """
        Women lead in India's fruit farming, contributing to 70% of rural agricultural labor. 
        FruitBid supports women-led cooperatives by prioritizing their produce. 
        Learn more about their impact in sustainable agriculture.
    """
    )

    # --- Charts ---
    st.subheader("Bids vs Billing")
    fig1 = create_bids_chart(tuple(items))
    if fig1:
        st.pyplot(fig1)

    st.subheader("Market Growth (Interactive for Funders)")
    fig2 = create_market_growth_chart()
    if fig2:
        st.plotly_chart(fig2, use_container_width=True)

    # --- PDF generation ---
    st.subheader("Download Report")
    try:
        fig1 = create_bids_chart(tuple(items))
        if fig1:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_bids:
                fig1.savefig(tmp_bids.name, bbox_inches="tight")
                bids_path = tmp_bids.name
        else:
            raise ValueError("Failed to generate bids chart")

        market_data = pd.DataFrame({"Year": [2024, 2030], "Market Size USD Billion": [66.3, 88.9]})
        market_data.plot(x="Year", y="Market Size USD Billion", marker="o")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_growth:
            plt.savefig(tmp_growth.name, bbox_inches="tight")
            growth_path = tmp_growth.name
        plt.close("all")

        conn = get_db_connection()
        if conn:
            user_data = pd.read_sql_query("SELECT mobile_email, address FROM users", conn)
            nutrition_data = get_nutrition_data()
            pdf = PDF()
            pdf.add_content(bids_path, growth_path, bid_data, user_data, nutrition_data)
            pdf_file = "fruitbid_report.pdf"
            pdf.output(pdf_file)

            with open(pdf_file, "rb") as f:
                pdf_data = f.read()
            b64_pdf = base64.b64encode(pdf_data).decode()
            href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{pdf_file}">Download PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            os.remove(pdf_file)
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
    finally:
        try:
            if "bids_path" in locals():
                os.unlink(bids_path)
            if "growth_path" in locals():
                os.unlink(growth_path)
        except OSError as e:
            st.warning(f"Cleanup error: {str(e)}")

    st.markdown("Run with `streamlit run app.py`")


if __name__ == "__main__":
    main()
