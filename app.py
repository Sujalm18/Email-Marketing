import streamlit as st
import pandas as pd
import smtplib
import time
import uuid
import base64
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import streamlit.components.v1 as components

# ================= CONFIG =================
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]

CTA_URL = "https://phntechnology.com/programs/training-program/"
PREHEADER_TEXT = "🎉 Congratulations! Please complete the registration process to proceed further."

TEST_EMAIL_RECIPIENTS = [
    "outreach@phntechnology.com",
    "sujalmandape@gmail.com"
]

SEND_DELAY_SECONDS = 3
HISTORY_FILE = "campaign_history.csv"

# ================= SESSION STATE =================
if "test_email_sent" not in st.session_state:
    st.session_state.test_email_sent = False

# ================= UI =================
st.set_page_config(page_title="Email Marketing Automation", layout="centered")
st.title("📧 Email Marketing Automation System")

campaign_name = st.text_input("📌 Campaign Name")
subject = st.text_input("✉ Email Subject")

content_type = st.radio(
    "📬 Email Content Type",
    ["Only Body Text", "Only Creative", "Creative + Body"],
    horizontal=True
)

body_text = st.text_area(
    "📝 Email Body (Optional)",
    height=140,
    placeholder="Write your message here..."
)

excel_file = st.file_uploader("📄 Upload Excel", type=["xlsx"])
image_file = st.file_uploader(
    "🖼 Upload Creative (Required for Creative options)",
    type=["png", "jpg", "jpeg"]
)

# ================= HELPERS =================
def clean_email(email):
    if not email:
        return None
    email = str(email).replace("\n", "").replace("\r", "").strip()
    return email if "@" in email else None

# ================= EMAIL HTML BUILDER =================
def build_email_html(body_text, image_cid, content_type):
    body_html = f"""
    <p style="font-size:14px;color:#374151;line-height:1.6;">
      {body_text.replace("\n", "<br>")}
    </p>
    """ if body_text else ""

    image_html = f"""
    <img src="cid:{image_cid}"
         style="max-width:100%;display:block;margin:0 auto;">
    """ if image_cid else ""

    return f"""
    <html>
      <body>

        <div style="display:none;font-size:1px;opacity:0;">
          {PREHEADER_TEXT}
        </div>

        {image_html if content_type != "Only Body Text" else ""}
        {body_html if content_type != "Only Creative" else ""}

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" style="padding-top:22px;">
              <table role="presentation">
                <tr>
                  <td bgcolor="#2563eb" style="border-radius:6px;">
                    <a href="{CTA_URL}" target="_blank"
                       style="display:inline-block;
                              padding:14px 28px;
                              font-size:16px;
                              font-weight:bold;
                              color:#ffffff;
                              text-decoration:none;
                              border-radius:6px;">
                      REGISTER NOW!
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>

      </body>
    </html>
    """

# ================= EMAIL SENDER =================
def send_email(server, to_email, subject, body_text, image_bytes, content_type):
    msg = MIMEMultipart("related")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject.strip()

    alt = MIMEMultipart("alternative")
    msg.attach(alt)

    image_cid = None
    if content_type != "Only Body Text" and image_bytes:
        image_cid = "creative"

    html = build_email_html(body_text, image_cid, content_type)
    alt.attach(MIMEText(html, "html"))

    if image_cid:
        img = MIMEImage(image_bytes)
        img.add_header("Content-ID", f"<{image_cid}>")
        img.add_header("Content-Disposition", "inline", filename="Internship Program.png")
        msg.attach(img)

    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ================= TEST EMAIL =================
if st.button("🧪 Send Test Email"):
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    img_bytes = image_file.read() if image_file else None

    for recipient in TEST_EMAIL_RECIPIENTS:
        clean = clean_email(recipient)
        if clean:
            send_email(
                server,
                clean,
                subject,
                body_text,
                img_bytes,
                content_type
            )

    server.quit()
    st.session_state.test_email_sent = True
    st.success("✅ Test email sent to both test recipients")

# ================= BULK SEND =================
if st.button("🚀 SEND BULK EMAILS"):
    if not st.session_state.test_email_sent:
        st.error("Send test email first.")
        st.stop()

    df = pd.read_excel(excel_file, engine="openpyxl")
    df.columns = df.columns.str.lower().str.strip()
    email_col = next((c for c in df.columns if "email" in c), None)

    if not email_col:
        st.error("No email column found.")
        st.stop()

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    img_bytes = image_file.read() if image_file else None

    for _, row in df.iterrows():
        email = clean_email(row[email_col])
        if email:
            send_email(
                server,
                email,
                subject,
                body_text,
                img_bytes,
                content_type
            )
            time.sleep(3)

    server.quit()
    st.success("✅ Bulk emails sent successfully")
