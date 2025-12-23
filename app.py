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
MAX_EMAILS_PER_CAMPAIGN = 200
HISTORY_FILE = "campaign_history.csv"

# ================= SESSION STATE =================
if "campaign_id" not in st.session_state:
    st.session_state.campaign_id = None

if "test_email_sent" not in st.session_state:
    st.session_state.test_email_sent = False

# ================= UI =================
st.set_page_config(page_title="Email Marketing Automation", layout="centered")
st.title("📧 Email Marketing Automation System")

campaign_name = st.text_input("📌 Campaign Name")
subject = st.text_input("✉ Email Subject")

excel_file = st.file_uploader("📄 Upload Excel (Name, Email)", type=["xlsx"])
image_file = st.file_uploader("🖼 Upload Email Creative", type=["png", "jpg", "jpeg"])

selected_sheet = None
df = None
email_column = None

# ================= HELPER =================
def clean_email(email):
    if not email:
        return None
    cleaned = str(email).replace("\n", "").replace("\r", "").strip()
    if "@" not in cleaned:
        return None
    return cleaned

# ================= EXCEL SHEET SELECTION =================
if excel_file:
    try:
        xls = pd.ExcelFile(excel_file)
        sheet_names = xls.sheet_names

        selected_sheet = (
            st.selectbox("📑 Select Excel Sheet to Send", sheet_names)
            if len(sheet_names) > 1 else sheet_names[0]
        )

        df = pd.read_excel(xls, sheet_name=selected_sheet, engine="openpyxl")

        # Normalize columns
        df.columns = df.columns.str.strip().str.lower()

        EMAIL_COLUMN_CANDIDATES = ["email", "email id", "email_id", "e-mail", "mail"]
        for col in EMAIL_COLUMN_CANDIDATES:
            if col in df.columns:
                email_column = col
                break

        if not email_column:
            st.error(
                "❌ No valid email column found.\n\n"
                "Expected one of: Email, Email ID, email_id, E-mail, Mail"
            )
            st.stop()

        df[email_column] = df[email_column].apply(clean_email)
        df = df.dropna(subset=[email_column])

        st.info(
            f"📊 Sheet Loaded: **{selected_sheet}** | Valid Emails: **{len(df)}**"
        )

    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
        st.stop()

# ================= BUTTONS =================
col1, col2, col3 = st.columns(3)

with col1:
    preview_btn = st.button("👀 Preview Email")

with col2:
    test_btn = st.button("🧪 Send Test Email")

with col3:
    send_btn = st.button("🚀 SEND EMAILS")

if st.session_state.test_email_sent:
    st.success("🔓 Bulk sending unlocked (Test email verified)")
else:
    st.warning("🔒 Bulk sending locked – send a test email first")

# ================= FUNCTIONS =================
def generate_preview_html(subject, image_bytes):
    encoded = base64.b64encode(image_bytes).decode()
    return f"""
    <html>
      <body style="font-family:Arial;text-align:center;">
        <h3>{subject}</h3>
        <img src="data:image/png;base64,{encoded}" style="max-width:100%;margin:auto;">
        <p style="color:#16a34a;font-weight:600;">
          🎉 Congratulations! You’ve been shortlisted.
        </p>
        <p>Please complete the registration process to proceed further.</p>
      </body>
    </html>
    """

def send_email(server, to_email, subject, image_bytes):
    msg = MIMEMultipart("related")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject.replace("\n", "").replace("\r", "").strip()

    alt = MIMEMultipart("alternative")
    msg.attach(alt)

    html = f"""
    <html>
      <body>

        <div style="display:none;font-size:1px;opacity:0;">
          {PREHEADER_TEXT}
        </div>

        <img src="cid:creative"
             style="max-width:100%;display:block;margin:0 auto;">

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" style="padding-top:22px;">
              <table role="presentation" cellpadding="0" cellspacing="0">
                <tr>
                  <td bgcolor="#2563eb" style="border-radius:6px;">
                    <a href="{CTA_URL}" target="_blank"
                       style="
                         display:inline-block;
                         padding:14px 28px;
                         font-size:16px;
                         font-weight:bold;
                         color:#ffffff;
                         text-decoration:none;
                         border-radius:6px;
                         letter-spacing:0.5px;
                       ">
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

    alt.attach(MIMEText(html, "html"))

    img = MIMEImage(image_bytes)
    img.add_header("Content-ID", "<creative>")
    img.add_header("Content-Disposition", "inline", filename="Internship Program.png")
    msg.attach(img)

    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

def save_campaign_history(record):
    df_hist = pd.DataFrame([record])
    if os.path.exists(HISTORY_FILE):
        df_hist.to_csv(HISTORY_FILE, mode="a", header=False, index=False)
    else:
        df_hist.to_csv(HISTORY_FILE, index=False)

# ================= PREVIEW =================
if preview_btn and image_file:
    components.html(
        generate_preview_html(subject, image_file.read()),
        height=520,
        scrolling=True
    )

# ================= TEST EMAIL =================
if test_btn:
    image_file.seek(0)
    image_bytes = image_file.read()

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)

        for recipient in TEST_EMAIL_RECIPIENTS:
            clean_recipient = clean_email(recipient)
            if clean_recipient:
                send_email(server, clean_recipient, subject, image_bytes)

        server.quit()

        st.session_state.test_email_sent = True
        st.success(
            "✅ Test email sent successfully to:\n"
            "- outreach@phntechnology.com\n"
            "- sujalmandape@gmail.com"
        )

    except Exception as e:
        st.error(f"❌ Test email failed: {e}")

# ================= SEND BULK =================
if send_btn:
    if not st.session_state.test_email_sent:
        st.error("Send test email first.")
        st.stop()

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    image_file.seek(0)
    image_bytes = image_file.read()

    sent_count = 0
    progress = st.progress(0)

    for i, row in df.iterrows():
        recipient = clean_email(row[email_column])
        if not recipient:
            continue

        send_email(server, recipient, subject, image_bytes)
        sent_count += 1
        progress.progress((i + 1) / len(df))
        time.sleep(SEND_DELAY_SECONDS)

    server.quit()

    save_campaign_history({
        "Campaign ID": st.session_state.campaign_id or f"PHN-{uuid.uuid4().hex[:8].upper()}",
        "Campaign Name": campaign_name,
        "Excel File": excel_file.name,
        "Sheet Name": selected_sheet,
        "Total Rows": len(df),
        "Emails Sent": sent_count,
        "Sender Email": SENDER_EMAIL,
        "Subject": subject,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Status": "Completed"
    })

    st.success("✅ Bulk emails sent & campaign history saved")

# ================= HISTORY VIEW =================
st.divider()
st.subheader("📊 Campaign History")

if os.path.exists(HISTORY_FILE):
    st.dataframe(pd.read_csv(HISTORY_FILE), use_container_width=True)
else:
    st.info("No campaign history available yet.")
