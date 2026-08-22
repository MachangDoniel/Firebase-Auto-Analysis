"""
Multi-Channel Notifier & Document Generator Module
Converts AI analysis into styled HTML & PDF documents and delivers:
1. Telegram Bot (Executive text summary + PDF Document attachment)
2. Discord Webhook (Executive text summary + PDF File upload)
3. Email / Gmail (Rich HTML summary + PDF Attachment)
4. macOS Desktop Notification Banner
5. Saved Local Documents (reports/analysis_YYYY-MM-DD.pdf & .html)
"""

import os
import sys
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import markdown
from xhtml2pdf import pisa
import requests

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
REPORTS_DIR = BASE_DIR / "reports"


def get_css_styling():
    """Clean, robust CSS styling compatible with xhtml2pdf."""
    return """
    @page {
        size: a4 portrait;
        margin: 1.5cm 1.2cm 1.5cm 1.2cm;
    }
    body {
        font-family: Helvetica, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.4;
        font-size: 9.5pt;
    }
    h1 {
        font-size: 16pt;
        color: #0f172a;
        border-bottom: 2px solid #4f46e5;
        padding-bottom: 4px;
        margin-top: 0;
        margin-bottom: 10px;
    }
    h2 {
        font-size: 12pt;
        color: #1e293b;
        background-color: #f1f5f9;
        padding: 5px 8px;
        border-left: 4px solid #4f46e5;
        margin-top: 14px;
        margin-bottom: 8px;
    }
    h3 {
        font-size: 10.5pt;
        color: #334155;
        margin-top: 10px;
        margin-bottom: 4px;
    }
    p, li {
        font-size: 9pt;
        color: #334155;
    }
    ul, ol {
        margin-top: 3px;
        margin-bottom: 6px;
        padding-left: 18px;
    }
    li {
        margin-bottom: 3px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
        margin-bottom: 10px;
        font-size: 8.5pt;
    }
    th {
        background-color: #4f46e5;
        color: #ffffff;
        text-align: left;
        padding: 5px 6px;
        font-weight: bold;
    }
    td {
        border-bottom: 1px solid #e2e8f0;
        padding: 4px 6px;
    }
    tr:nth-child(even) td {
        background-color: #f8fafc;
    }
    pre, code {
        font-family: Courier, monospace;
        font-size: 8pt;
        background-color: #f8fafc;
    }
    pre {
        padding: 6px;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        white-space: pre-wrap;
    }
    blockquote {
        border-left: 3px solid #cbd5e1;
        padding-left: 8px;
        margin-left: 0;
        color: #64748b;
        font-style: italic;
    }
    .header-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 8px 12px;
        margin-bottom: 12px;
        font-size: 9pt;
    }
    .footer-note {
        margin-top: 20px;
        border-top: 1px solid #e2e8f0;
        padding-top: 6px;
        font-size: 7.5pt;
        color: #94a3b8;
        text-align: center;
    }
    """


def generate_documents(markdown_text, target_date=None):
    """
    Converts markdown analysis into styled HTML and PDF files.
    Returns (html_path, pdf_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    html_content = markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    
    css = get_css_styling()
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Firebase Analytics Report - {target_date}</title>
    <style>
        {css}
    </style>
</head>
<body>
    <div class="header-box">
        <strong>Neural Sound iOS</strong> &bull; Automated Daily Analytics Briefing &bull; <em>{target_date}</em>
    </div>
    {html_content}
    <div class="footer-note">
        Generated automatically by Neural Sound Analytics Pipeline &bull; Gemini AI &bull; {target_date}
    </div>
</body>
</html>"""

    # 1. Save HTML
    html_path = REPORTS_DIR / f"analysis_{target_date}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # 2. Save PDF
    pdf_path = REPORTS_DIR / f"analysis_{target_date}.pdf"
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_file)
    
    if pisa_status.err:
        print(f"⚠️ PDF creation error: {pisa_status.err}", file=sys.stderr)
        pdf_path = None
    else:
        print(f"✅ Generated PDF Document: {pdf_path}")

    # Also save Markdown copy
    md_path = REPORTS_DIR / f"analysis_{target_date}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    return html_path, pdf_path


def extract_executive_summary(report_text, max_length=950):
    """Extracts a clean, punchy summary for message captions."""
    lines = report_text.strip().split("\n")
    summary_lines = []
    
    for line in lines:
        if line.startswith("# ") or line.startswith("### **Product Overview**") or "Health Score" in line or line.startswith("* ") or line.startswith("- "):
            summary_lines.append(line)
        if len("\n".join(summary_lines)) > max_length:
            break
            
    summary = "\n".join(summary_lines[:16]).strip()
    if not summary:
        summary = report_text[:max_length]
    return summary


def send_macos_notification(title, message, pdf_path=None):
    """
    Sends native macOS desktop notification attributed to Finder
    (prevents Script Editor from opening on click).
    """
    if sys.platform != "darwin":
        return
    try:
        clean_msg = message.replace('"', '\\"').replace("'", "\\'")[:160]
        # Route through Finder application so clicking the banner does not launch Script Editor
        script = f'tell application "Finder" to display notification "{clean_msg}" with title "{title}" subtitle "Neural Sound Analytics"'
        subprocess.run(["osascript", "-e", script], check=False)
        print("✅ macOS notification banner sent (via Finder).")
        
        # Optional: Auto-open PDF in Preview if AUTO_OPEN_PDF is enabled in .env
        auto_open = os.getenv("AUTO_OPEN_PDF_ON_MAC", "false").lower() in ("true", "1", "yes")
        if auto_open and pdf_path and os.path.exists(pdf_path):
            subprocess.run(["open", "-a", "Preview", str(pdf_path)], check=False)
            print(f"✅ Automatically opened PDF in Preview: {pdf_path}")
    except Exception as e:
        print(f"⚠️ Failed to send macOS notification: {e}", file=sys.stderr)


def send_telegram_document(report_text, pdf_path=None):
    """Sends executive text summary + PDF Document to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return
    
    print("Sending report to Telegram...")
    try:
        summary = extract_executive_summary(report_text)
        caption = f"📊 *Neural Sound iOS - Daily Analytics Briefing*\n\n{summary}\n\n📄 _Full PDF attached below._"
        
        # 1. If PDF exists, send as document
        if pdf_path and os.path.exists(pdf_path):
            doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            with open(pdf_path, "rb") as f:
                files = {"document": (os.path.basename(pdf_path), f, "application/pdf")}
                data = {"chat_id": chat_id, "caption": caption[:1024]}
                resp = requests.post(doc_url, data=data, files=files, timeout=30)
                resp.raise_for_status()
        else:
            msg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            resp = requests.post(msg_url, json={"chat_id": chat_id, "text": report_text[:4000]}, timeout=15)
            resp.raise_for_status()
            
        print("✅ Telegram notification & PDF delivered successfully.")
    except Exception as e:
        print(f"⚠️ Telegram delivery failed: {e}", file=sys.stderr)


def send_discord_document(report_text, pdf_path=None):
    """Sends executive summary + PDF File to Discord."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    print("Sending report to Discord...")
    try:
        summary = extract_executive_summary(report_text, max_length=1200)
        content = f"📊 **Neural Sound iOS — Daily AI Analytics Briefing**\n\n{summary}\n\n📎 *See attached PDF for full breakdown & telemetry tables.*"
        
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
                payload = {"content": content[:1900]}
                resp = requests.post(webhook_url, data=payload, files=files, timeout=30)
                resp.raise_for_status()
        else:
            resp = requests.post(webhook_url, json={"content": report_text[:1900]}, timeout=15)
            resp.raise_for_status()
            
        print("✅ Discord notification & PDF delivered successfully.")
    except Exception as e:
        print(f"⚠️ Discord delivery failed: {e}", file=sys.stderr)


def send_gmail_document(report_text, html_path=None, pdf_path=None):
    """Sends formatted HTML email with PDF Document attached."""
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    sender_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient_email = os.getenv("GMAIL_RECIPIENT_EMAIL", sender_email)
    
    if not sender_email or not sender_password or not recipient_email:
        return
    
    print(f"Sending email report with PDF to {recipient_email}...")
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"📊 Daily Firebase Analytics AI Report - {today_str}"
        
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"Neural Sound AI Analytics <{sender_email}>"
        msg["To"] = recipient_email
        
        # Email body (HTML)
        alt_part = MIMEMultipart("alternative")
        if html_path and os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            alt_part.attach(MIMEText(html_content, "html", "utf-8"))
        else:
            alt_part.attach(MIMEText(report_text, "plain", "utf-8"))
        msg.attach(alt_part)
        
        # PDF Attachment
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition", "attachment", filename=os.path.basename(pdf_path)
                )
                msg.attach(pdf_attachment)
                
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
            
        print("✅ Email report & PDF attachment delivered successfully.")
    except Exception as e:
        print(f"⚠️ Email delivery failed: {e}", file=sys.stderr)


def dispatch_all_notifications(report_text, date_str=None):
    """Generates documents and dispatches across all configured channels."""
    # 1. Generate HTML & PDF Documents
    html_path, pdf_path = generate_documents(report_text, date_str)
    
    # 2. Native macOS banner (routed via Finder)
    send_macos_notification(
        title="Firebase Analytics PDF Ready",
        message="Daily PDF report has been generated and dispatched.",
        pdf_path=pdf_path
    )
    
    # 3. Telegram (Executive summary + PDF document)
    send_telegram_document(report_text, pdf_path)
    
    # 4. Discord (Executive summary + PDF file upload)
    send_discord_document(report_text, pdf_path)
    
    # 5. Email (Formatted HTML + PDF attachment)
    send_gmail_document(report_text, html_path, pdf_path)
