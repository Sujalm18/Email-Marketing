import streamlit as st
import pandas as pd
import smtplib
import time
import uuid
import base64
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import streamlit.components.v1 as components

# ================= CONFIG =================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]

TRACKING_BASE_URL = "https://email-marketing-tracking-server.onrender.com/click"
REDIRECT_URL = "https://phntechnology.com/programs/training-program/"

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

campaign_name = st.text_input(
    "📌 Campaign Name",
    placeholder="Eg: IIT Guwahati – AIML Internship – Jan 2026"
)

subject = st.text_input("✉ Email Subject")

excel_file = st.file_uploader("📄 Upload Excel (Columns: Name, Email)", type=["xlsx"])
image_file = st.file_uploader("🖼 Upload Email Creative (PNG/JPG)", type=["png", "jpg", "jpeg"])

col1, col2, col3 = st.columns(3)
with col1:
    preview_btn = st.button("👀 Preview Email")
with col2:
    test_btn = st.button("🧪 Send Test Email")
with col3:
    btn = st.button("🚀 SEND EMAILS")

if st.session_state.test_email_sent:
    st.success("🔓 Bulk sending unlocked (Test email verified)")
else:
    st.warning("🔒 Bulk sending locked – send a test email first")

# ================= FUNCTIONS =================
def generate_tracking_link(campaign_id, campaign_name, name, email):
    params = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "name": name,
        "email": email,
        "redirect_url": REDIRECT_URL
    }
    return f"{TRACKING_BASE_URL}?{urllib.parse.urlencode(params)}"

def generate_preview_html(subject, image_bytes):
    encoded = base64.b64encode(image_bytes).decode()
    return f"""
    <html>
      <body style="font-family:Arial; text-align:center;">
        <h3>Subject: {subject}</h3>

        <img src="data:image/png;base64,{encoded}"
             style="max-width:100%; display:block; margin:0 auto;">

        <br><br>

        <table role="presentation" cellspacing="0" cellpadding="0" align="center">
          <tr>
            <td align="center" bgcolor="#2563eb" style="border-radius:6px;">
              <a style="
                   display:inline-block;
                   padding:14px 24px;
                   font-size:16px;
                   color:#ffffff;
                   text-decoration:none;
                   font-weight:bold;
                   border-radius:6px;
                 ">
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

def send_email(server, to_email, subject, image_bytes, tracking_link):
    msg = MIMEMultipart("related")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    html = f"""
    <html>
      <body>

        <img src="cid:creative" style="max-width:100%; display:block; margin:0 auto;">

        <br><br>

        <table role="presentation" cellspacing="0" cellpadding="0" align="center">
          <tr>
            <td align="center" bgcolor="#2563eb" style="border-radius:6px;">
              <a href="{tracking_link}"
                 target="_blank"
                 style="
                   display:inline-block;
                   padding:14px 24px;
                   font-size:16px;
                   color:#ffffff;
                   text-decoration:none;
                   font-weight:bold;
                   border-radius:6px;
                 ">
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

    img = MIMEImage(image_bytes)
    img.add_header("Content-ID", "<creative>")
    img.add_header("Content-Disposition", "inline", filename="creative.png")
    img.add_header("X-Attachment-Id", "creative")
    msg.attach(img)

    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ================= PREVIEW =================
if preview_btn:
    if not image_file or not subject:
        st.warning("Upload image and subject first.")
    else:
        image_bytes = image_file.read()
        preview_html = generate_preview_html(subject, image_bytes)
        st.subheader("📩 Email Preview")
        components.html(preview_html, height=600, scrolling=True)

# ================= TEST EMAIL =================
if test_btn:
    if not campaign_name or not subject or not image_file:
        st.warning("Campaign Name, Subject and Image are required.")
        st.stop()

    if not st.session_state.campaign_id:
        st.session_state.campaign_id = f"PHN-{uuid.uuid4().hex[:8].upper()}"

    image_file.seek(0)
    image_bytes = image_file.read()

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)

        link = generate_tracking_link(
            st.session_state.campaign_id,
            campaign_name,
            "Test",
            SENDER_EMAIL
        )

        send_email(server, SENDER_EMAIL, subject, image_bytes, link)

        server.quit()
        st.session_state.test_email_sent = True
        st.success("✅ Test email sent successfully! Bulk sending unlocked.")
    except Exception as e:
        st.error(f"❌ Test email failed\n{e}")

# ================= SEND BULK EMAILS =================
if send_btn:
    if not st.session_state.test_email_sent:
        st.error("🔒 Safety Lock: Send a TEST EMAIL before bulk sending.")
        st.stop()

    if not campaign_name or not subject or not excel_file or not image_file:
        st.error("All fields are required.")
        st.stop()

    df = pd.read_excel(excel_file)

    if "Name" not in df.columns or "Email" not in df.columns:
        st.error("Excel must contain Name and Email columns.")
        st.stop()

    if len(df) > MAX_EMAILS_PER_CAMPAIGN:
        st.error("Campaign exceeds safe Gmail limit (200 emails).")
        st.stop()

    image_file.seek(0)
    image_bytes = image_file.read()

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)

    campaign_log = []
    progress = st.progress(0)
    status = st.empty()

    sent = failed = 0

    for i, row in df.iterrows():
        log = {
            "Campaign ID": st.session_state.campaign_id,
            "Campaign Name": campaign_name,
            "Email": row["Email"],
            "Status": "",
            "Error": "",
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            link = generate_tracking_link(
                st.session_state.campaign_id,
                campaign_name,
                row["Name"],
                row["Email"]
            )
            send_email(server, row["Email"], subject, image_bytes, link)
            log["Status"] = "Sent"
            sent += 1
        except Exception as e:
            log["Status"] = "Failed"
            log["Error"] = str(e)
            failed += 1

        campaign_log.append(log)
        progress.progress((i + 1) / len(df))
        status.text(f"Sent: {sent} | Failed: {failed}")
        time.sleep(SEND_DELAY_SECONDS)

    server.quit()

    log_df = pd.DataFrame(campaign_log)

    st.success("✅ Campaign completed successfully")

    st.download_button(
        "📥 Download Campaign Log (CSV)",
        log_df.to_csv(index=False),
        f"{campaign_name.replace(' ', '_')}_{st.session_state.campaign_id}.csv",
        "text/csv"
    )



