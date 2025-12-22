import streamlit as st
import pandas as pd
import smtplib
import time
import uuid
import base64
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

SEND_DELAY_SECONDS = 3
MAX_EMAILS_PER_CAMPAIGN = 200

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

# ================= EXCEL SHEET SELECTION =================
if excel_file:
    try:
        xls = pd.ExcelFile(excel_file)
        sheet_names = xls.sheet_names

        if len(sheet_names) > 1:
            selected_sheet = st.selectbox(
                "📑 Select Excel Sheet to Send",
                sheet_names
            )
        else:
            selected_sheet = sheet_names[0]

        df = pd.read_excel(xls, sheet_name=selected_sheet)

        st.info(f"📊 Loaded sheet: **{selected_sheet}** | Rows: **{len(df)}**")

    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
        st.stop()

# ---- Buttons ----
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
      <body style="font-family:Arial; text-align:center;">
        <h3>{subject}</h3>

        <img src="data:image/png;base64,{encoded}"
             style="max-width:100%; display:block; margin:0 auto;">

        <br><br>
        <p style="color:#16a34a; font-size:15px; font-weight:600;">
          🎉 Congratulations! You’ve been shortlisted.
        </p>
        <p style="color:#374151; font-size:14px;">
          Please complete the registration process to proceed further.
        </p>
      </body>
    </html>
    """

def send_email(server, to_email, subject, image_bytes):
    msg = MIMEMultipart("related")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    alternative = MIMEMultipart("alternative")
    msg.attach(alternative)

    html = f"""
    <html>
      <body>
        <div style="display:none;font-size:1px;opacity:0;overflow:hidden;">
          {PREHEADER_TEXT}
        </div>

        <img src="cid:creative" style="max-width:100%;display:block;margin:0 auto;">

        <br><br>

        <table role="presentation" align="center">
          <tr>
            <td bgcolor="#2563eb" style="border-radius:6px;">
              <a href="{CTA_URL}" target="_blank"
                 style="display:inline-block;padding:14px 24px;
                        font-size:16px;color:#ffffff;
                        text-decoration:none;font-weight:bold;
                        border-radius:6px;">
                🔗 Know More & Apply
              </a>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    alternative.attach(MIMEText(html, "html"))

    img = MIMEImage(image_bytes)
    img.add_header("Content-ID", "<creative>")
    img.add_header("Content-Disposition", "inline", filename="Internship Program.png")
    img.add_header("X-Attachment-Id", "creative")
    msg.attach(img)

    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ================= PREVIEW =================
if preview_btn:
    if not image_file or not subject:
        st.warning("Upload image and subject first.")
    else:
        preview_html = generate_preview_html(subject, image_file.read())
        components.html(preview_html, height=550)

# ================= TEST EMAIL =================
if test_btn:
    if not subject or not image_file:
        st.warning("Subject and Image are required.")
        st.stop()

    image_file.seek(0)
    image_bytes = image_file.read()

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)

        send_email(server, SENDER_EMAIL, subject, image_bytes)
        server.quit()

        st.session_state.test_email_sent = True
        st.success("✅ Test email sent successfully.")

    except Exception as e:
        st.error(e)

# ================= SEND BULK =================
if send_btn:
    if not st.session_state.test_email_sent:
        st.error("Send test email first.")
        st.stop()

    if df is None or "Email" not in df.columns:
        st.error("Selected sheet must contain an Email column.")
        st.stop()

    image_file.seek(0)
    image_bytes = image_file.read()

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    progress = st.progress(0)

    for i, row in df.iterrows():
        send_email(server, row["Email"], subject, image_bytes)
        progress.progress((i + 1) / len(df))
        time.sleep(SEND_DELAY_SECONDS)

    server.quit()
    st.success("✅ Bulk emails sent successfully.")
