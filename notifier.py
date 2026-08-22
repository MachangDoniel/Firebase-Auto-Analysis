"""
Multi-Channel Notifier Module
Handles delivery of AI Analytics reports across:
1. Telegram Bot (Instant iPhone/Desktop push)
2. Discord Webhook
3. Email (Gmail SMTP)
4. macOS Desktop Notification Banner
5. Dated Markdown Reports (reports/YYYY-MM-DD.md)
"""

import os
import sys
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"


def save_markdown_report(report_text, target_date=None):
    """Saves the daily analysis to a dated markdown file in reports/."""
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        file_path = REPORTS_DIR / f"analysis_{target_date}.md"
        header = f"# 📊 Firebase Analytics Daily Report ({target_date})\n\n"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(header + report_text + "\n")
        
        print(f"✅ Saved dated report to: {file_path}")
        return file_path
    except Exception as e:
        print(f"⚠️ Failed to save markdown report: {e}", file=sys.stderr)
        return None


def send_macos_notification(title, message):
    """Sends native macOS desktop notification banner."""
    if sys.platform != "darwin":
        return
    try:
        # Keep notification message brief for banner
        clean_msg = message.replace('"', '\\"').replace("'", "\\'")[:200] + "..."
        script = f'display notification "{clean_msg}" with title "{title}" subtitle "Neural Sound Analytics"'
        subprocess.run(["osascript", "-e", script], check=False)
        print("✅ macOS notification banner sent.")
    except Exception as e:
        print(f"⚠️ Failed to send macOS notification: {e}", file=sys.stderr)


def send_telegram_message(report_text):
    """Sends analysis to Telegram Bot (instant iPhone & Mac push)."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return
    
    print("Sending report to Telegram...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        # Telegram has a 4096 character limit per message
        max_len = 4000
        chunks = [report_text[i:i+max_len] for i in range(0, len(report_text), max_len)]
        
        for chunk in chunks:
            payload = {
                "chat_id": chat_id,
                "text": chunk,
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            
        print("✅ Telegram notification delivered successfully.")
    except Exception as e:
        print(f"⚠️ Telegram delivery failed: {e}", file=sys.stderr)


def send_discord_webhook(report_text):
    """Sends analysis to Discord channel via Webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    print("Sending report to Discord...")
    try:
        # Discord limit is 2000 chars per message
        max_len = 1900
        chunks = [report_text[i:i+max_len] for i in range(0, len(report_text), max_len)]
        
        for idx, chunk in enumerate(chunks):
            payload = {
                "content": f"**Daily Analytics AI Report (Part {idx+1}/{len(chunks)})**\n\n{chunk}" if len(chunks) > 1 else f"**Daily Analytics AI Report**\n\n{chunk}"
            }
            resp = requests.post(webhook_url, json=payload, timeout=15)
            resp.raise_for_status()
            
        print("✅ Discord notification delivered successfully.")
    except Exception as e:
        print(f"⚠️ Discord delivery failed: {e}", file=sys.stderr)


def send_gmail_report(report_text):
    """Sends email report using Gmail SMTP."""
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    sender_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient_email = os.getenv("GMAIL_RECIPIENT_EMAIL", sender_email)
    
    if not sender_email or not sender_password or not recipient_email:
        return
    
    print(f"Sending email from {sender_email} to {recipient_email}...")
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"📊 Daily Firebase Analytics AI Report - {today_str}"
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Analytics AI <{sender_email}>"
        msg["To"] = recipient_email
        
        # Plain text and simple HTML formatting
        text_part = MIMEText(report_text, "plain", "utf-8")
        msg.attach(text_part)
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
            
        print("✅ Email report delivered successfully.")
    except Exception as e:
        print(f"⚠️ Email delivery failed: {e}", file=sys.stderr)


def dispatch_all_notifications(report_text, date_str=None):
    """Dispatches the report across all configured channels."""
    # 1. Save local dated markdown file
    save_markdown_report(report_text, date_str)
    
    # 2. Native macOS banner
    send_macos_notification(
        title="Firebase Analytics Ready",
        message="Daily Gemini AI Analysis report has been generated."
    )
    
    # 3. Telegram (iPhone + Desktop)
    send_telegram_message(report_text)
    
    # 4. Discord
    send_discord_webhook(report_text)
    
    # 5. Email (Gmail)
    send_gmail_report(report_text)
