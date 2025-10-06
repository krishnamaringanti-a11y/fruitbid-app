import streamlit as st
from twilio.rest import Client
from datetime import datetime, timedelta
import random
import os
from db import get_db_connection


# ---------------------- TWILIO CONFIG ----------------------

# You can either hardcode or set these via environment variables
TWILIO_SID = os.getenv("TWILIO_SID", "your_twilio_sid_here")
TWILIO_AUTH = os.getenv("TWILIO_AUTH", "your_twilio_auth_token_here")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "+1234567890")


# ---------------------- OTP FUNCTIONS ----------------------

def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp(mobile_email):
    """Send OTP via Twilio SMS (or display if testing)."""
    conn = get_db_connection()
    if conn is None:
        return False

    otp = generate_otp()
    expiration = datetime.now() + timedelta(minutes=5)

    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO otps (mobile_email, otp, expiration) VALUES (?, ?, ?)",
            (mobile_email, otp, expiration)
        )
        conn.commit()

        # Try sending SMS (if number)
        if mobile_email.replace("+", "").isdigit():
            try:
                client = Client(TWILIO_SID, TWILIO_AUTH)
                client.messages.create(
                    body=f"Your FruitBid OTP is {otp}. It expires in 5 minutes.",
                    from_=TWILIO_PHONE,
                    to=mobile_email
                )
                st.success(f"OTP sent successfully to {mobile_email}")
            except Exception as sms_err:
                st.warning(f"Could not send SMS: {sms_err}. Showing OTP for testing: {otp}")
        else:
            # If it's an email or invalid phone, just show the OTP
            st.info(f"Your OTP (for testing): {otp}")

        return True

    except Exception as e:
        st.error(f"Error sending OTP: {str(e)}")
        return False


def verify_otp(mobile_email, user_otp):
    """Verify user OTP input."""
    conn = get_db_connection()
    if conn is None:
        return False

    try:
        c = conn.cursor()
        c.execute(
            "SELECT otp, expiration FROM otps WHERE mobile_email=? ORDER BY id DESC LIMIT 1",
            (mobile_email,)
        )
        row = c.fetchone()

        if not row:
            st.error("No OTP found for this user.")
            return False

        db_otp, exp_time = row
        exp_time = datetime.strptime(exp_time, "%Y-%m-%d %H:%M:%S.%f")

        if datetime.now() > exp_time:
            st.error("OTP expired. Please request a new one.")
            return False

        if user_otp == db_otp:
            st.success("OTP verified successfully!")
            return True
        else:
            st.error("Invalid OTP.")
            return False

    except Exception as e:
        st.error(f"Error verifying OTP: {str(e)}")
        return False
