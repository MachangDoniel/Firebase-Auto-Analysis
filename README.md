# Daily Firebase / Google Analytics (GA4) to Gemini AI Analysis Pipeline

## 📌 Project Overview
Automated Python pipeline running on a local machine (macOS/Linux/Windows) that:
1. Connects to **Firebase Analytics / Google Analytics 4 (GA4)** via the **Google Analytics Data API**.
2. Fetches daily metrics (Active Users, New Users, Sessions, Engagement Duration, In-App Events, App Version adoption).
3. Passes the structured daily report to the **Google Gemini API** (using the modern `google-genai` SDK with `gemini-2.5-flash` / `gemini-1.5-flash` / `gemini-1.5-pro`).
4. Generates an executive briefing covering user engagement, key feature usage, version adoption, and actionable product recommendations.
5. Runs automatically on a daily schedule using OS-level task runners (**cron** / **Task Scheduler**).

---

## 💰 Free Tier & Limits

| Service | Free Tier / Plan | Limits & Notes |
| :--- | :--- | :--- |
| **Firebase / Google Analytics (GA4)** | **Standard (Free)** | • Free unlimited standard event collection & reporting<br>• Standard API quotas for Analytics Data API (more than enough for daily automation) |
| **Gemini Developer API** | **Google AI Studio (Free Tier)** | • Free rate limits (RPM/TPM/RPD)<br>• Separate from consumer Gemini Advanced/Pro subscription |

---

## 🛠️ Tech Stack & Dependencies
- **Language**: Python 3.10+ (Python 3.9+ compatible)
- **Analytics SDK**: `google-analytics-data` (GA4 Data API v1beta)
- **Gemini SDK**: `google-genai` (Unified modern SDK)
- **Environment Management**: `python-dotenv`
- **Pinned Dependencies**: Exact versions locked in `requirements.txt` for cross-machine reproducibility.

---

## 🚀 Setup & Installation

### 1. Clone & Navigate to Project Directory
```bash
git clone https://github.com/MachangDoniel/firebase-gemini-analysis.git
cd firebase-gemini-analysis
```

### 2. Set Up Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Firebase & GA4 Credentials Setup

#### Step 3A: Get your GA4 Property ID
1. Open [Firebase Console](https://console.firebase.google.com/).
2. Select your project > **Project Settings (Gear icon)** > **Integrations** tab.
3. Under **Google Analytics**, click **Manage** or look at the linked **Property ID** (a 9 or 10-digit number like `312345678`).

#### Step 3B: Download Service Account Key
1. In Firebase Console > **Project Settings** > **Service Accounts** tab.
2. Click **Generate New Private Key**.
3. Save the downloaded JSON file as `serviceAccountKey.json` in this project directory.

#### Step 3C: Grant Service Account Access in Google Analytics (One-time step)
1. Open [Google Analytics](https://analytics.google.com/).
2. Go to **Admin (bottom left gear)** > **Property Access Management**.
3. Click the `+` button > **Add users**.
4. Enter the `client_email` from your `serviceAccountKey.json` (e.g. `firebase-adminsdk-xxx@project.iam.gserviceaccount.com`).
5. Grant the **Viewer** role and save.

#### Step 3D: Ensure Google Analytics Data API is Enabled
In [Google Cloud Console API Library](https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com), select your project and click **Enable** for **Google Analytics Data API**.

---

### 4. Configure Environment Variables
1. Copy template to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in:
   ```ini
   GEMINI_API_KEY="your_actual_gemini_api_key_here"
   GA4_PROPERTY_ID="your_ga4_property_id_here"
   FIREBASE_KEY_PATH="serviceAccountKey.json"
   GEMINI_MODEL="gemini-2.5-flash"
   ```

---

### 5. App Store Connect Income Setup
Income metrics (Units, Proceeds, Sales, Updates, In-App Purchases, App Bundles, Pre-Orders, products and territories) come from the App Store Connect Sales & Trends API.

1. In [App Store Connect](https://appstoreconnect.apple.com/access/integrations/api), open **Users and Access** > **Integrations** > **Team Keys** and create a key with the **Finance** role.
2. Download the `AuthKey_XXXXXXXXXX.p8` file into this directory. Apple only lets you download it once. `*.p8` is git-ignored.
3. Fill in `ASC_ISSUER_ID`, `ASC_KEY_ID`, `ASC_PRIVATE_KEY_PATH` and `ASC_VENDOR_NUMBER` (from **Payments and Financial Reports**) in `.env`.
4. Compare one day with the Trends screen:
   ```bash
   ./venv/bin/python appstore_income.py --date 2026-10-29
   ```

Without these settings the reports still go out, without an income section. USD values use daily ECB exchange rates, so they can differ slightly from Apple's figures.

Each run writes a visual dashboard to `reports/dashboard_YYYY-MM-DD.html` and sends it with the PDF on Telegram, Discord and email.

---

## 📬 Notification Channels Setup (Telegram, Discord, Email, iPhone & Mac)

The pipeline can automatically broadcast each daily report across multiple channels. Simply fill in the ones you want in [.env](file:///Users/donieltripura/Neural%20Sound/Analysis/Workflow/.env):

### 1. 📱 Telegram Bot (Pings iPhone & Mac instantly)
- Talk to [@BotFather](https://t.me/botfather) on Telegram to create a bot and get your `TELEGRAM_BOT_TOKEN`.
- Send a message to your new bot, then open [@userinfobot](https://t.me/userinfobot) to get your numeric `TELEGRAM_CHAT_ID`.
- Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.

### 2. 💬 Discord Webhook
- In your Discord server: **Channel Settings** > **Integrations** > **Webhooks** > **New Webhook**.
- Copy the Webhook URL and paste it into `DISCORD_WEBHOOK_URL` in `.env`.

### 3. 📧 Gmail Reports (Inbox & iPhone Mail)
- **Sender Email**: Any Gmail account you own (`GMAIL_SENDER_EMAIL`).
- **Sender Password**: A 16-character [Google App Password](https://myaccount.google.com/apppasswords) (`GMAIL_APP_PASSWORD`).
- **Recipient Email**: The destination email address (`GMAIL_RECIPIENT_EMAIL`).

### 4. 🔔 macOS Native Notification
- Automatically triggered on your Mac desktop whenever the pipeline runs!

### 5. 📑 Dated Markdown Files
- Every run automatically writes a clean, formatted report to:
  `reports/analysis_YYYY-MM-DD.md`

---

## 📂 Project Structure

```
.
├── README.md                          # Complete project documentation & setup guide
├── requirements.txt                   # Pinned Python package dependencies
├── .env.example                       # Environment variables template
├── .gitignore                         # Protects keys, logs, and virtual environments
├── main.py                            # Core GA4 extraction & Gemini AI analysis
├── notifier.py                        # Multi-channel dispatcher (Telegram, Discord, Email, Mac)
├── install_scheduler.sh               # 1-click 12:00 AM daily scheduler installer
├── run_daily.sh                       # Daily execution wrapper
├── reports/                           # Dated markdown reports (analysis_YYYY-MM-DD.md)
├── daily_analysis.log                 # Cumulative run logs
└── serviceAccountKey.json             # Service Account Key (keep private)
```

---

## ⚙️ Running & Testing Manually

```bash
python3 main.py
```

---

## ⏰ Daily Scheduling Guide (12:00 AM Run)

### Option A: macOS Native Scheduler (`launchd` - Recommended)
`launchd` is Apple's native scheduler and runs reliably even if your Mac wakes up from sleep:

1. Run the one-command installer:
   ```bash
   ./install_scheduler.sh
   ```
2. To verify it is loaded:
   ```bash
   launchctl list | grep neuralsound
   ```
3. To uninstall/disable:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.neuralsound.dailyanalysis.plist
   ```

---

### Option B: Standard Unix Cron (`cron`)
1. Open cron configuration:
   ```bash
   crontab -e
   ```
2. Add this line to run every night at 12:00 AM (00:00):
   ```cron
   0 0 * * * "/path/to/firebase-gemini-analysis/run_daily.sh"
   ```
