import smtplib
from email.mime.text import MIMEText
from config import Config


def send_otp_email(receiver_email, otp):

    subject = "Bank DSA Portal - Email Verification OTP"

    body = f"""
Hello,

Your OTP for Bank DSA Portal is:

{otp}

This OTP is valid for {Config.OTP_EXPIRE_MINUTES} minutes.

Do not share this OTP with anyone.

Thank You,
Bank DSA Portal
"""

    message = MIMEText(body)

    message["Subject"] = subject
    message["From"] = Config.EMAIL_ADDRESS
    message["To"] = receiver_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(
        Config.EMAIL_ADDRESS,
        Config.EMAIL_PASSWORD
    )

    server.send_message(message)

    server.quit()