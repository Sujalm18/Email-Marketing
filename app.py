import streamlit as st
import pandas as pd
import smtplib
import time
import uuid
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit.components.v1 as components

# ================= CONFIG =================
SMTP_SERVER = "smtp.gmail.com"      # Change to smtp.office365.com later
SMTP_PORT = 587

SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]

# 🔥 HOSTED IMAGE (NO ATTACHMENTS EVER)
EMAIL_IMAGE_URL = "https://phntechnology.com/assets/email/creative.png"

# 🔗 CTA (can later be form URL)
CTA_URL = "https://phntechnology.com/programs/training-program/"

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
def generate_preview_html(subject):
    return f"""
    <html>
      <body style="font-family:Arial; text-align:center;">
        <h3>{subject}</h3>

        <img src="{EMAIL_IMAGE_URL}"
             alt="PHN Campaign"
             style="max-width:100%; display:block; margin:0 auto;">

        <br><br>

        <table role="presentation" align="center">
          <tr>
            <td bgcolor="#2563eb" style="border-radius:6px;">
              <a href="{CTA_URL}"
                 target="_blank"
                 style="
                   display:inline-block;
                   padding:14px 24px;
                   font-size:16px;
                   color:#ffffff;
                   text-decoration:none;
                   font-weight:bold;
                   border-radius:6px;">
                🔗 Know More & Apply
              </a>
            </td>
          </tr>
        </table>

        <br><br>
        <p>Regards,<br>PHN Technology Team</p>
      </body>
    </html>
    """

def send_email(server, to_email, subject):
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    html = f"""
    <html>
      <body>

        <img src="{EMAIL_IMAGE_URL}"
             alt="PHN Campaign"
             style="max-width:100%; display:block; margin:0 auto;">

        <br><br>

        <table role="presentation" align="center">
          <tr>
            <td bgcolor="#2563eb" style="border-radius:6px;">
              <a href="{CTA_URL}"
                 target="_blank"
                 style="
                   display:inline-block;
                   padding:14px 24px;
                   font-size:16px;
                   color:#ffffff;
                   text-decoration:none;
                   font-weight:bold;
                   border-radius:6px;">
                🔗 Know More & Apply
              </a>
            </td>
          </tr>
        </table>

        <br><br>
        <p style="text-align:center;">Regards,<br>PHN Technology Team</p>

      </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))
    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ================= PREVIEW =================
if preview_btn:
    if not subject:
        st.warning("Please enter a subject first.")
    else:
        st.subheader("📩 Email Preview")
        components.html(generate_preview_html(subject), height=600, scrolling=True)

# ================= TEST EMAIL =================
if test_btn:
    if not campaign_name or not subject:
        st.warning("Campaign Name and Subject are required.")
        st.stop()

    if not st.session_state.campaign_id:
        st.session_state.campaign_id = f"PHN-{uuid.uuid4().hex[:8].upper()}"

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)

        send_email(server, SENDER_EMAIL, subject)
        server.quit()

        st.session_state.test_email_sent = True
        st.success("✅ Test email sent successfully! Bulk sending unlocked.")

    except Exception as e:
        st.error(f"❌ Test email failed\n{e}")

# ================= SEND BULK EMAILS =================
if send_btn:
    if not st.session_state.test_email_sent:
        st.error("🔒 Safety Lock: Send a TEST EMAIL first.")
        st.stop()

    if not campaign_name or not subject or not excel_file:
        st.error("All fields are required.")
        st.stop()

    df = pd.read_excel(excel_file)

    if "Name" not in df.columns or "Email" not in df.columns:
        st.error("Excel must contain Name and Email columns.")
        st.stop()

    if len(df) > MAX_EMAILS_PER_CAMPAIGN:
        st.error("Campaign exceeds safe Gmail limit (200).")
        st.stop()

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    logs = []
    progress = st.progress(0)

    for i, row in df.iterrows():
        try:
            send_email(server, row["Email"], subject)
            status = "Sent"
            error = ""
        except Exception as e:
            status = "Failed"
            error = str(e)

        logs.append({
            "Campaign ID": st.session_state.campaign_id,
            "Campaign Name": campaign_name,
            "Email": row["Email"],
            "Status": status,
            "Error": error,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        progress.progress((i + 1) / len(df))
        time.sleep(SEND_DELAY_SECONDS)

    server.quit()

    log_df = pd.DataFrame(logs)

    st.success("✅ Campaign completed successfully")

    st.download_button(
        "📥 Download Campaign Log (CSV)",
        log_df.to_csv(index=False),
        f"{campaign_name.replace(' ', '_')}_{st.session_state.campaign_id}.csv",
        "text/csv"
    )
