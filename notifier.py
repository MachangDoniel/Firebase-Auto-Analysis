"""
Multi-Channel Notifier & Document Generator Module
Converts AI analysis and visual charts into styled HTML & PDF documents and delivers:
1. Telegram Bot (Executive text summary + PDF Document + Visual Charts)
2. Discord Webhook (Executive text summary + PDF File + Visual Charts)
3. Email / Gmail (Rich HTML summary + Embedded Charts + PDF Attachment)
4. macOS Desktop Notification Banner (terminal-notifier with direct open)
5. Saved Local Documents (reports/analysis_YYYY-MM-DD.pdf, .html, & .md)
"""

import os
import sys
import smtplib
import subprocess
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
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
    """Clean, presentation-grade CSS styling for PDF and HTML."""
    return """
    @page {
        size: a4 portrait;
        margin: 1.2cm 1.2cm 1.2cm 1.2cm;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.45;
        font-size: 9pt;
        background-color: #ffffff;
        margin: 0;
        padding: 0;
    }
    .container {
        max-width: 900px;
        margin: 0 auto;
        padding: 10px;
    }
    h1 {
        font-size: 16pt;
        color: #0f172a;
        border-bottom: 2px solid #4f46e5;
        padding-bottom: 5px;
        margin-top: 0;
        margin-bottom: 8px;
    }
    h2 {
        font-size: 12pt;
        color: #1e293b;
        background-color: #f1f5f9;
        padding: 6px 10px;
        border-left: 4px solid #4f46e5;
        margin-top: 14px;
        margin-bottom: 8px;
        border-radius: 2px;
    }
    h3 {
        font-size: 10.5pt;
        color: #334155;
        margin-top: 10px;
        margin-bottom: 4px;
    }
    p, li {
        font-size: 8.5pt;
        color: #334155;
    }
    ul, ol {
        margin-top: 2px;
        margin-bottom: 6px;
        padding-left: 18px;
    }
    li {
        margin-bottom: 2px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        margin-top: 6px;
        margin-bottom: 12px;
        font-size: 8pt;
    }
    th {
        background-color: #4f46e5;
        color: #ffffff;
        text-align: left;
        padding: 5px 8px;
        font-weight: bold;
        word-wrap: break-word;
        overflow: hidden;
    }
    td {
        border-bottom: 1px solid #e2e8f0;
        padding: 5px 8px;
        word-wrap: break-word;
        overflow: hidden;
        vertical-align: top;
    }
    tr:nth-child(even) td {
        background-color: #f8fafc;
    }
    pre, code {
        font-family: "SF Mono", Monaco, Menlo, Consolas, Courier, monospace;
        font-size: 7.5pt;
        background-color: #f8fafc;
    }
    pre {
        padding: 8px;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        white-space: pre-wrap;
    }
    .header-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 8px 12px;
        margin-bottom: 10px;
        font-size: 8.5pt;
    }
    .console-links-box {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #4f46e5;
        padding: 8px 12px;
        margin-bottom: 14px;
        font-size: 8pt;
    }
    .console-links-box a {
        color: #4f46e5;
        text-decoration: underline;
        font-weight: bold;
    }
    .charts-grid {
        text-align: center;
        margin-top: 10px;
        margin-bottom: 14px;
    }
    .chart-card {
        margin-bottom: 12px;
        text-align: center;
    }
    .chart-img {
        max-width: 100%;
        height: auto;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
    }
    .footer-note {
        margin-top: 18px;
        border-top: 1px solid #e2e8f0;
        padding-top: 8px;
        font-size: 7.5pt;
        color: #64748b;
        text-align: center;
    }
    """


def generate_documents(markdown_text, target_date=None, chart_images=None):
    """
    Converts markdown analysis and embeds visual charts into styled HTML and PDF files.
    Also produces a rich, standalone Markdown file with embedded charts & links.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    # 1. Build enriched Markdown file with relative chart links & console links
    md_header = f"""# 📊 Daily Mobile Analytics & Growth Intelligence Report ({target_date})

> **Automated Intelligence Briefing** &bull; Generated for Neural Sound Portfolio &bull; *{target_date}*

---

### 🔗 Direct Cloud Console Quick Links:
* 📊 **Google Analytics 4 (GA4):** [GA4 Intelligent Home](https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/intelligenthome) | [Realtime Live Users](https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/dashboard?r=realtime-overview) | [In-App Events](https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/explorer?params=_u..nav%3Ddefault&r=events-overview)
* 🔥 **Firebase Console:** [Firebase Analytics Dashboard](https://console.firebase.google.com/u/0/project/neural-sound-ios/analytics) | [Crashlytics Stability](https://console.firebase.google.com/u/0/project/neural-sound-ios/crashlytics) | [Project Settings](https://console.firebase.google.com/u/0/project/neural-sound-ios/settings/general)

---

"""

    md_charts_block = "\n\n## 📊 Visual Graphs & Performance Charts\n\n"
    if chart_images:
        for c_path in chart_images:
            if os.path.exists(c_path):
                rel_chart_path = os.path.relpath(c_path, REPORTS_DIR)
                chart_name = Path(c_path).stem.replace("_", " ").title()
                md_charts_block += f"### {chart_name}\n![{chart_name}]({rel_chart_path})\n\n"

    full_md_content = md_header + markdown_text + md_charts_block

    md_path = REPORTS_DIR / f"analysis_{target_date}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(full_md_content)
    print(f"✅ Generated Markdown Document: {md_path}")

    # 2. Build HTML Content
    html_body = markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )

    # Convert chart images for HTML (both relative path and absolute path for PDF)
    html_charts_block = ""
    pdf_charts_block = ""
    if chart_images:
        html_charts_block = "<h2>📊 Visual Graphs & Performance Charts</h2><div class='charts-grid'>"
        pdf_charts_block = "<h2>📊 Visual Graphs & Performance Charts</h2><div class='charts-grid'>"
        for c_path in chart_images:
            if os.path.exists(c_path):
                rel_chart_path = os.path.relpath(c_path, REPORTS_DIR)
                chart_name = Path(c_path).stem.replace("_", " ").title()
                html_charts_block += f"<div class='chart-card'><h3>{chart_name}</h3><img class='chart-img' src='{rel_chart_path}' alt='{chart_name}' /></div>"
                pdf_charts_block += f"<div class='chart-card'><h3>{chart_name}</h3><img class='chart-img' src='{c_path}' alt='{chart_name}' /></div>"
        html_charts_block += "</div>"
        pdf_charts_block += "</div>"

    css = get_css_styling()

    # Full HTML (standalone for browsers)
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mobile Analytics Intelligence Report - {target_date}</title>
    <style>
        {css}
    </style>
</head>
<body>
<div class="container">
    <div class="header-box">
        <strong>Mobile Product Analytics Portfolio</strong> &bull; Automated Daily Briefing &bull; <em>{target_date}</em>
    </div>

    <!-- Direct Cloud Console Quick Access -->
    <div class="console-links-box">
        <strong>🔗 Direct Cloud Console Quick Access:</strong><br>
        &bull; <strong>GA4 Property (533563138):</strong> 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/intelligenthome" target="_blank">GA4 Main Reports</a> | 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/dashboard?r=realtime-overview" target="_blank">Realtime Users</a> | 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/explorer?params=_u..nav%3Ddefault&r=events-overview" target="_blank">Events Explorer</a><br>
        &bull; <strong>Firebase (neural-sound-ios):</strong> 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/analytics" target="_blank">Firebase Analytics</a> | 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/crashlytics" target="_blank">Crashlytics Stability</a> | 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/settings/general" target="_blank">Project Settings</a>
    </div>

    {html_body}
    {html_charts_block}

    <div class="footer-note">
        <strong>Direct Console Links:</strong><br>
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/intelligenthome" target="_blank">🔗 Open Google Analytics 4 Dashboard</a> &bull;
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/analytics" target="_blank">🔥 Open Firebase Analytics Console</a> &bull;
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/crashlytics" target="_blank">💥 Open Firebase Crashlytics</a>
        <br><br>
        Generated automatically by Neural Sound Analytics Pipeline &bull; Gemini AI &bull; {target_date}
    </div>
</div>
</body>
</html>"""

    html_path = REPORTS_DIR / f"analysis_{target_date}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"✅ Generated HTML Dashboard: {html_path}")

    # 3. Build PDF HTML (with absolute paths for pisa engine)
    pdf_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mobile Analytics Intelligence Report - {target_date}</title>
    <style>
        {css}
    </style>
</head>
<body>
    <div class="header-box">
        <strong>Mobile Product Analytics Portfolio</strong> &bull; Automated Daily Briefing &bull; <em>{target_date}</em>
    </div>

    <div class="console-links-box">
        <strong>🔗 Direct Cloud Console Quick Access:</strong><br>
        &bull; <strong>GA4 Property (533563138):</strong> 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/intelligenthome">GA4 Main Reports</a> | 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/dashboard?r=realtime-overview">Realtime Users</a> | 
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/explorer?params=_u..nav%3Ddefault&r=events-overview">Events Explorer</a><br>
        &bull; <strong>Firebase (neural-sound-ios):</strong> 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/analytics">Firebase Analytics</a> | 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/crashlytics">Crashlytics Stability</a> | 
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/settings/general">Project Settings</a>
    </div>

    {html_body}
    {pdf_charts_block}

    <div class="footer-note">
        <strong>Direct Console Links:</strong><br>
        <a href="https://analytics.google.com/analytics/web/#/a371473317p533563138/reports/intelligenthome">🔗 Open Google Analytics 4 Dashboard</a> &bull;
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/analytics">🔥 Open Firebase Analytics Console</a> &bull;
        <a href="https://console.firebase.google.com/u/0/project/neural-sound-ios/crashlytics">💥 Open Firebase Crashlytics</a>
        <br><br>
        Generated automatically by Neural Sound Analytics Pipeline &bull; Gemini AI &bull; {target_date}
    </div>
</body>
</html>"""

    pdf_path = REPORTS_DIR / f"analysis_{target_date}.pdf"
    with open(pdf_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(pdf_html, dest=pdf_file)
    
    if pisa_status.err:
        print(f"⚠️ PDF creation error: {pisa_status.err}", file=sys.stderr)
        pdf_path = None
    else:
        print(f"✅ Generated PDF Document: {pdf_path}")

    return html_path, pdf_path


def extract_executive_summary(report_text, max_length=950):
    """Extracts a punchy summary for message captions."""
    lines = report_text.strip().split("\n")
    summary_lines = []
    
    for line in lines:
        if line.startswith("# ") or line.startswith("###") or "Health Score" in line or line.startswith("* ") or line.startswith("- "):
            summary_lines.append(line)
        if len("\n".join(summary_lines)) > max_length:
            break
            
    summary = "\n".join(summary_lines[:16]).strip()
    if not summary:
        summary = report_text[:max_length]
    return summary


def send_macos_notification(title, message, pdf_path=None):
    """
    Sends native macOS desktop notification.
    Uses terminal-notifier so clicking the banner opens the PDF directly in Preview!
    """
    if sys.platform != "darwin":
        return
    try:
        clean_msg = message.replace('"', '\\"').replace("'", "\\'")[:160]
        pdf_file = str(pdf_path) if pdf_path and os.path.exists(pdf_path) else None
        
        terminal_notifier_bin = "/opt/homebrew/bin/terminal-notifier"
        if not os.path.exists(terminal_notifier_bin):
            terminal_notifier_bin = "terminal-notifier"
            
        cmd = [
            terminal_notifier_bin,
            "-title", title,
            "-subtitle", "Daily Mobile Intelligence",
            "-message", "Click here to open the full PDF report 📄",
            "-sound", "default"
        ]
        if pdf_file:
            cmd.extend(["-open", f"file://{pdf_file}"])
            
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print("✅ macOS notification banner sent (Clicking opens PDF).")
            return

        # Fallback: Native AppleScript via System Events
        script = f'tell application "System Events" to display notification "{clean_msg}" with title "{title}" subtitle "Neural Sound Analytics"'
        subprocess.run(["osascript", "-e", script], check=False)
        print("✅ macOS notification banner sent.")
    except Exception as e:
        print(f"⚠️ Failed to send macOS notification: {e}", file=sys.stderr)


def send_telegram_document(report_text, pdf_path=None, md_path=None, chart_images=None):
    """Sends executive text summary + PDF Document + Markdown File + Visual Charts to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return
    
    print("Sending report, PDF & Markdown to Telegram...")
    try:
        summary = extract_executive_summary(report_text)
        caption = f"📊 *Mobile Analytics Portfolio — Daily Intelligence Briefing*\n\n{summary}\n\n📄 _Full PDF & Markdown documents attached below._"
        doc_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        
        # 1. Send PDF Document
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                files = {"document": (os.path.basename(pdf_path), f, "application/pdf")}
                data = {"chat_id": chat_id, "caption": caption[:1024]}
                resp = requests.post(doc_url, data=data, files=files, timeout=30)
                resp.raise_for_status()

        # 2. Send Markdown File (.md)
        if md_path and os.path.exists(md_path):
            with open(md_path, "rb") as f:
                files = {"document": (os.path.basename(md_path), f, "text/markdown")}
                data = {"chat_id": chat_id, "caption": "📑 Raw Markdown Report (.md)"}
                requests.post(doc_url, data=data, files=files, timeout=20)

        # 3. Send Chart Photos
        if chart_images:
            photo_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            for c_path in chart_images[:3]:
                if os.path.exists(c_path):
                    with open(c_path, "rb") as f:
                        files = {"photo": (os.path.basename(c_path), f, "image/png")}
                        data = {"chat_id": chat_id}
                        requests.post(photo_url, data=data, files=files, timeout=20)
            
        print("✅ Telegram notification, PDF & Markdown delivered successfully.")
    except Exception as e:
        print(f"⚠️ Telegram delivery failed: {e}", file=sys.stderr)


def send_discord_document(report_text, pdf_path=None, md_path=None, chart_images=None):
    """Sends executive summary + PDF File + Markdown File + Chart Upload to Discord."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    print("Sending report, PDF & Markdown to Discord...")
    try:
        summary = extract_executive_summary(report_text, max_length=1200)
        content = f"📊 **Mobile Analytics Portfolio — Daily AI Intelligence Briefing**\n\n{summary}\n\n📎 *See attached PDF, Markdown report, and visual charts below.*"
        
        files_payload = {}
        file_handles = []
        
        if pdf_path and os.path.exists(pdf_path):
            f_pdf = open(pdf_path, "rb")
            file_handles.append(f_pdf)
            files_payload["file_pdf"] = (os.path.basename(pdf_path), f_pdf, "application/pdf")

        if md_path and os.path.exists(md_path):
            f_md = open(md_path, "rb")
            file_handles.append(f_md)
            files_payload["file_md"] = (os.path.basename(md_path), f_md, "text/markdown")
            
        if chart_images:
            for idx, c_path in enumerate(chart_images[:2]):
                if os.path.exists(c_path):
                    f_img = open(c_path, "rb")
                    file_handles.append(f_img)
                    files_payload[f"chart_{idx}"] = (os.path.basename(c_path), f_img, "image/png")
                    
        payload = {"content": content[:1900]}
        resp = requests.post(webhook_url, data=payload, files=files_payload, timeout=35)
        resp.raise_for_status()
        
        for fh in file_handles:
            fh.close()
            
        print("✅ Discord notification, PDF & Markdown delivered successfully.")
    except Exception as e:
        print(f"⚠️ Discord delivery failed: {e}", file=sys.stderr)


def send_gmail_document(report_text, html_path=None, pdf_path=None, md_path=None, chart_images=None):
    """Sends formatted HTML email with PDF and Markdown (.md) attached."""
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    sender_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient_email = os.getenv("GMAIL_RECIPIENT_EMAIL", sender_email)
    
    if not sender_email or not sender_password or not recipient_email:
        return
    
    print(f"Sending email report with PDF & Markdown to {recipient_email}...")
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"📊 Daily Mobile Analytics Portfolio Report - {today_str}"
        
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"Neural Sound Analytics <{sender_email}>"
        msg["To"] = recipient_email
        
        alt_part = MIMEMultipart("alternative")
        if html_path and os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            alt_part.attach(MIMEText(html_content, "html", "utf-8"))
        else:
            alt_part.attach(MIMEText(report_text, "plain", "utf-8"))
        msg.attach(alt_part)
        
        # Attach PDF
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition", "attachment", filename=os.path.basename(pdf_path)
                )
                msg.attach(pdf_attachment)

        # Attach Markdown File (.md)
        if md_path and os.path.exists(md_path):
            with open(md_path, "rb") as f:
                md_attachment = MIMEApplication(f.read(), _subtype="octet-stream")
                md_attachment.add_header(
                    "Content-Disposition", "attachment", filename=os.path.basename(md_path)
                )
                msg.attach(md_attachment)
                
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
            
        print("✅ Email report, PDF & Markdown attachment delivered successfully.")
    except Exception as e:
        print(f"⚠️ Email delivery failed: {e}", file=sys.stderr)


def dispatch_all_notifications(report_text, date_str=None, chart_images=None):
    """Generates documents with embedded charts and dispatches across all channels."""
    html_path, pdf_path = generate_documents(report_text, date_str, chart_images)
    
    target_d = date_str or datetime.now().strftime("%Y-%m-%d")
    md_path = REPORTS_DIR / f"analysis_{target_d}.md"
    if not os.path.exists(md_path):
        md_path = None
    
    send_macos_notification(
        title="Mobile Analytics Report Ready",
        message="Daily Analytics PDF & Markdown report has been generated.",
        pdf_path=pdf_path
    )
    
    send_telegram_document(report_text, pdf_path, md_path, chart_images)
    send_discord_document(report_text, pdf_path, md_path, chart_images)
    send_gmail_document(report_text, html_path, pdf_path, md_path, chart_images)
