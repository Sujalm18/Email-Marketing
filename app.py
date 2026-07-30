import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
import uuid
import base64
import os
import csv
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import streamlit.components.v1 as components

# ================= CONFIG =================
CONFIG = {
    "SEND_DELAY_SECONDS": 30,
    "RECONNECT_AFTER": 20,
    "SMTP_TIMEOUT": 30,
    "RETRY_COUNT": 2,
    "RETRY_DELAY": 5,
}

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = st.secrets.get("SENDER_EMAIL", "")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "")
CTA_URL = "https://forms.gle/DHYsZQsgobdQSQAHA"
PREHEADER_TEXT = "🚀 Job Opportunity at Autoline Industries | Apply through Navyanta Group."
TEST_EMAIL_RECIPIENTS = [SENDER_EMAIL, "sujalmandape@gmail.com"]

# ================= STORAGE =================
DATA_DIR = "data"
LOGS_DIR = "logs"
SENT_EMAILS_FILE = os.path.join(DATA_DIR, "sent_emails.csv")
FAILED_EMAILS_FILE = os.path.join(DATA_DIR, "failed_emails.csv")
CAMPAIGN_HISTORY_FILE = os.path.join(DATA_DIR, "campaign_history.csv")
LOCK_FILE = os.path.join(DATA_DIR, "campaign.lock")

def initialize_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    files = [
        (SENT_EMAILS_FILE, ["Campaign ID", "Campaign Name", "Email", "Sent Time"]),
        (FAILED_EMAILS_FILE, ["Campaign ID", "Campaign Name", "Email", "Reason", "Time"]),
        (CAMPAIGN_HISTORY_FILE, ["Campaign ID", "Campaign Name", "Start Time", "End Time", "Total", "Sent", "Skipped", "Failed", "Duration", "Status"])
    ]
    for fp, headers in files:
        if not os.path.exists(fp):
            with open(fp, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(headers)

def get_logger():
    logger = logging.getLogger("navyanta")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        
        log_file = os.path.join(LOGS_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger

initialize_storage()
app_logger = get_logger()

def normalize_email(email):
    return str(email).strip().lower() if pd.notna(email) and email else ""

def write_csv_sync(filepath, row):
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())

def log_sent_email(campaign_id, campaign_name, email):
    write_csv_sync(SENT_EMAILS_FILE, [campaign_id, campaign_name, email, datetime.now().isoformat()])
    app_logger.info(f"SENT: {email} (Campaign: {campaign_name})")

def log_failed_email(campaign_id, campaign_name, email, reason):
    write_csv_sync(FAILED_EMAILS_FILE, [campaign_id, campaign_name, email, reason, datetime.now().isoformat()])
    app_logger.error(f"FAILED: {email} - {reason} (Campaign: {campaign_name})")

def update_campaign_status(campaign_id, campaign_name, start_time, end_time, total, sent, skipped, failed, status):
    duration = (end_time - start_time).total_seconds() if end_time else 0
    write_csv_sync(CAMPAIGN_HISTORY_FILE, [campaign_id, campaign_name, start_time.isoformat(), end_time.isoformat() if end_time else "", total, sent, skipped, failed, duration, status])

def load_sent_emails(campaign_name):
    sent_set = set()
    if os.path.exists(SENT_EMAILS_FILE):
        with open(SENT_EMAILS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Campaign Name") == campaign_name:
                    sent_set.add(row.get("Email"))
    return sent_set

def get_campaign_id(campaign_name):
    if os.path.exists(CAMPAIGN_HISTORY_FILE):
        with open(CAMPAIGN_HISTORY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("Campaign Name") == campaign_name:
                    return row.get("Campaign ID")
    return str(uuid.uuid4())

def delete_campaign_records(campaign_name):
    for fp, headers in [
        (SENT_EMAILS_FILE, ["Campaign ID", "Campaign Name", "Email", "Sent Time"]),
        (FAILED_EMAILS_FILE, ["Campaign ID", "Campaign Name", "Email", "Reason", "Time"]),
        (CAMPAIGN_HISTORY_FILE, ["Campaign ID", "Campaign Name", "Start Time", "End Time", "Total", "Sent", "Skipped", "Failed", "Duration", "Status"])
    ]:
        if os.path.exists(fp):
            rows = []
            with open(fp, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = headers
                for row in reader:
                    if len(row) > 1 and row[1] != campaign_name:
                        rows.append(row)
            with open(fp, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        return False
    with open(LOCK_FILE, "w") as f:
        f.write(str(time.time()))
    return True

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

# ================= EMAIL BUILDER =================
def build_email_html(body, image_cid):
    body_html = ""
    if body:
        body_html = f"""
        <p style="font-size:14px;color:#374151;line-height:1.6;">
          {body.replace("\n", "<br>")}
        </p>
        """
    img_html = ""
    if image_cid:
        img_html = f"""
        <div style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
            <img src="cid:{image_cid}" alt="Recruitment Flyer" style="max-width: 100%; border-radius: 8px;">
        </div>
        """

    return f"""
    <html>
      <body>
        <div style="display:none;font-size:1px;opacity:0;">
          {PREHEADER_TEXT}
        </div>
        {body_html}
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" style="padding-top:22px; padding-bottom:22px;">
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
        {img_html}
      </body>
    </html>
    """

def send_email(server, to_email, subject, body, image_bytes):
    msg = MIMEMultipart("related")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject.strip()

    alt = MIMEMultipart("alternative")
    msg.attach(alt)

    html = build_email_html(body, "creative" if image_bytes else None)
    alt.attach(MIMEText(html, "html"))

    if image_bytes:
        attachment = MIMEImage(image_bytes)
        attachment.add_header('Content-ID', '<creative>')
        attachment.add_header("Content-Disposition","inline",filename="Navyanta Recruitment Flyer.png")
        msg.attach(attachment)

    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

def reconnect_server():
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=CONFIG["SMTP_TIMEOUT"])
    server.ehlo()
    server.starttls(context=ssl.create_default_context())
    server.ehlo()
    server.login(SENDER_EMAIL, EMAIL_PASSWORD)
    return server

# ================= SESSION =================
if "test_email_sent" not in st.session_state:
    st.session_state.test_email_sent = False
if "campaign_state" not in st.session_state:
    st.session_state.campaign_state = "idle" # idle, prompt_resume, running, paused, completed
if "campaign_id" not in st.session_state:
    st.session_state.campaign_id = None
if "resume_choice" not in st.session_state:
    st.session_state.resume_choice = None
if "df" not in st.session_state:
    st.session_state.df = None

# ================= UI =================
st.set_page_config(page_title="Navyanta Talent Outreach", layout="centered")
st.title("🚀 Navyanta Talent Outreach System")
st.caption("Candidate Outreach & Recruitment Automation")

campaign_name = st.text_input("📌 Campaign Name")
subject = st.text_input("✉ Email Subject")

content_type = st.radio(
    "📬 Email Content Type",
    ["Only Body Text", "Only Creative", "Creative + Body"],
    horizontal=True
)

body_text = st.text_area(
    "📝 Email Body",
    placeholder="Write your message here...",
    height=140
)

excel_file = st.file_uploader("📄 Upload Excel", type=["xlsx"])
image_file = st.file_uploader("🖼 Upload Creative", type=["png", "jpg", "jpeg"])

image_bytes = image_file.getvalue() if image_file else None

if content_type != "Only Body Text" and not image_bytes:
    st.warning("🖼 Image required for Creative options")

# ================= PREVIEW =================
if st.button("👀 Preview Email"):
    html = build_email_html(body_text, "creative" if image_bytes else None)
    if image_bytes:
        html = html.replace("cid:creative", f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}")
    components.html(html, height=520, scrolling=True)

# ================= TEST EMAIL =================
if st.button("🧪 Send Test Email"):
    try:
        server = reconnect_server()
    except Exception as e:
        st.error(f"SMTP Error: {e}")
        st.stop()

    for r in TEST_EMAIL_RECIPIENTS:
        clean = normalize_email(r)
        if clean:
            try:
                send_email(server, clean, subject, body_text, image_bytes)
            except Exception as e:
                st.error(f"Failed to send to {clean}: {e}")

    server.quit()
    st.session_state.test_email_sent = True
    st.success("✅ Test email sent successfully")

# ================= BULK SEND =================
if st.session_state.campaign_state == "idle":
    if st.button("🚀 PREPARE CAMPAIGN"):
        if not st.session_state.test_email_sent:
            st.error("Send test email first.")
            st.stop()
        if not campaign_name:
            st.error("Campaign Name is required.")
            st.stop()
        if not excel_file:
            st.error("Please upload an Excel file.")
            st.stop()

        df = pd.read_excel(excel_file, engine="openpyxl")
        df.columns = df.columns.str.lower().str.strip()
        email_col = next((c for c in df.columns if "email" in c), None)

        if not email_col:
            st.error("No email column found.")
            st.stop()
            
        df[email_col] = df[email_col].apply(normalize_email)
        df.drop_duplicates(subset=[email_col], inplace=True)
        df = df[df[email_col] != ""]
        
        st.session_state.df = df
        st.session_state.email_col = email_col

        sent_set = load_sent_emails(campaign_name)
        if sent_set:
            st.session_state.campaign_state = "prompt_resume"
        else:
            st.session_state.campaign_state = "running"
            st.session_state.campaign_id = str(uuid.uuid4())
            
        st.rerun()

elif st.session_state.campaign_state == "prompt_resume":
    st.warning(f"Campaign '{campaign_name}' already has sent records.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ Resume Campaign"):
            st.session_state.resume_choice = "resume"
            st.session_state.campaign_id = get_campaign_id(campaign_name)
            st.session_state.campaign_state = "running"
            st.rerun()
    with col2:
        if st.button("🔄 Start Fresh (Delete History)"):
            st.session_state.resume_choice = "fresh"
            delete_campaign_records(campaign_name)
            st.session_state.campaign_id = str(uuid.uuid4())
            st.session_state.campaign_state = "running"
            st.rerun()

elif st.session_state.campaign_state == "paused":
    st.warning("Campaign paused.")
    if st.button("▶ Resume Campaign"):
        st.session_state.campaign_state = "running"
        st.rerun()
    if st.button("🔄 Start New Campaign"):
        st.session_state.campaign_state = "idle"
        st.rerun()

elif st.session_state.campaign_state == "running":
    col1, col2 = st.columns(2)
    if col1.button("⏸ Pause Campaign"):
        st.session_state.campaign_state = "paused"
        st.rerun()
    if col2.button("⏹ Stop Campaign"):
        st.session_state.campaign_state = "idle"
        st.rerun()
        
    if not acquire_lock():
        st.error("⚠ This campaign is already running in another session. Please clear data/campaign.lock if you are sure it is safe.")
        st.stop()

    df = st.session_state.df
    email_col = st.session_state.email_col
    c_id = st.session_state.campaign_id
    
    sent_set = load_sent_emails(campaign_name)
    total = len(df)
    sent = 0
    skipped = 0
    failed = 0
    start_time = datetime.now()

    try:
        st.info(f"📧 Total Emails to Process: {total}")
        progress = st.progress(0)
        status = st.empty()
        stats = st.empty()
        eta = st.empty()
        activity_log = st.empty()

        logs_text = []

        def update_activity(msg):
            logs_text.append(msg)
            display_logs = "\n".join(logs_text[-15:])
            activity_log.code(display_logs, language="text")

        try:
            server = reconnect_server()
        except Exception as e:
            st.error(f"SMTP Error: {e}")
            release_lock()
            st.stop()

        successful_sends_since_reconnect = 0
        total_time_sending = 0
        emails_sent_in_session = 0

        for i, row_data in enumerate(df.iterrows(), start=1):
            _, row = row_data
            email = row[email_col]

            if email in sent_set:
                skipped += 1
                update_activity(f"⏩ Skipped: {email} (Already sent)")
                continue

            status.info(f"📤 Sending to: **{email}**")
            
            send_start = time.time()
            success = False
            for attempt in range(1, CONFIG["RETRY_COUNT"] + 1):
                try:
                    send_email(server, email, subject, body_text, image_bytes)
                    success = True
                    break
                except Exception as e:
                    update_activity(f"⚠ Attempt {attempt} failed for {email}: {e}")
                    app_logger.error(f"Attempt {attempt} failed for {email}: {e}")
                    try:
                        server = reconnect_server()
                    except:
                        pass
                    if attempt < CONFIG["RETRY_COUNT"]:
                        time.sleep(CONFIG["RETRY_DELAY"])

            send_duration = time.time() - send_start

            if success:
                sent += 1
                successful_sends_since_reconnect += 1
                emails_sent_in_session += 1
                
                log_sent_email(c_id, campaign_name, email)
                sent_set.add(email)
                update_activity(f"✔ Sent: {email}")

                if successful_sends_since_reconnect >= CONFIG["RECONNECT_AFTER"]:
                    try:
                        server.quit()
                    except:
                        pass
                    server = reconnect_server()
                    successful_sends_since_reconnect = 0
                    st.toast("SMTP Reconnected successfully")

                time.sleep(CONFIG["SEND_DELAY_SECONDS"])
                total_time_sending += send_duration + CONFIG["SEND_DELAY_SECONDS"]
            else:
                failed += 1
                log_failed_email(c_id, campaign_name, email, "Failed after retries")
                update_activity(f"✖ Failed: {email}")
                total_time_sending += send_duration

            progress.progress(i / total)
            remaining = total - i

            avg_time = total_time_sending / max(emails_sent_in_session, 1)
            if emails_sent_in_session == 0:
                avg_time = CONFIG["SEND_DELAY_SECONDS"] + 2

            eta_seconds = remaining * avg_time
            hrs = int(eta_seconds // 3600)
            mins = int((eta_seconds % 3600) // 60)
            speed = 60 / avg_time if avg_time > 0 else 0

            stats.markdown(f"""
            ### 📊 Campaign Progress
            ✅ **Sent:** {sent} | ⏩ **Skipped:** {skipped} | ❌ **Failed:** {failed}
            
            📧 **Remaining:** {remaining} | 📈 **Progress:** {i}/{total}
            
            ⚡ **Speed:** {speed:.1f} emails / min
            """)

            eta.info(f"⏳ Estimated Time Remaining: {hrs} hr {mins} min")

        try:
            server.quit()
        except:
            pass

        progress.progress(1.0)
        end_time = datetime.now()

        status.success("🎉 Campaign Completed!")
        update_campaign_status(c_id, campaign_name, start_time, end_time, total, sent, skipped, failed, "Completed")
        st.session_state.campaign_state = "completed"

        report_path = os.path.join(DATA_DIR, f"report_{c_id}.csv")
        duration_secs = (end_time - start_time).total_seconds()
        avg_speed = (sent / duration_secs * 60) if duration_secs > 0 else 0
        success_pct = (sent / (sent + failed)) * 100 if (sent + failed) > 0 else 0
        fail_pct = (failed / (sent + failed)) * 100 if (sent + failed) > 0 else 0
        
        with open(report_path, "w", newline="", encoding="utf-8") as rf:
            writer = csv.writer(rf)
            writer.writerow(["Campaign Name", "Campaign ID", "Started", "Completed", "Duration (s)", "Total Emails", "Sent", "Skipped", "Failed", "Average Speed (emails/min)", "Success %", "Failure %"])
            writer.writerow([campaign_name, c_id, start_time.isoformat(), end_time.isoformat(), f"{duration_secs:.1f}", total, sent, skipped, failed, f"{avg_speed:.2f}", f"{success_pct:.1f}%", f"{fail_pct:.1f}%"])

        st.session_state.report_path = report_path
        release_lock()
        st.rerun()

    except BaseException as e:
        app_logger.error(f"Campaign Interrupted: {e}")
        try:
            update_campaign_status(c_id, campaign_name, start_time, datetime.now(), total, sent, skipped, failed, "Interrupted")
        except:
            pass
        finally:
            release_lock()
        raise

elif st.session_state.campaign_state == "completed":
    st.success("Campaign finished successfully. You can download the reports below.")

    def get_file_content(path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    sent_data = get_file_content(SENT_EMAILS_FILE)
    failed_data = get_file_content(FAILED_EMAILS_FILE)
    report_data = get_file_content(st.session_state.report_path) if hasattr(st.session_state, "report_path") else ""

    col1, col2, col3 = st.columns(3)
    col1.download_button("📥 Sent Emails", data=sent_data, file_name="sent_emails.csv", mime="text/csv")
    col2.download_button("📥 Failed Emails", data=failed_data, file_name="failed_emails.csv", mime="text/csv")
    if report_data:
        col3.download_button("📥 Campaign Report", data=report_data, file_name="campaign_report.csv", mime="text/csv")

    if st.button("🔄 Start New Campaign"):
        for key in ["campaign_state", "campaign_id", "df", "resume_choice", "report_path"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
