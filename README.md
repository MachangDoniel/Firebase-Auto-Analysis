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

## 📂 Project Structure

```
.
├── README.md               # Complete project documentation & setup guide
├── requirements.txt        # Pinned Python package dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Protects keys, logs, and virtual environments
├── main.py                 # Core GA4 data extraction and Gemini analysis script
├── daily_analysis.log      # Output log file (generated after runs)
└── serviceAccountKey.json  # Service Account Key (keep private, ignored by git)
```

---

## ⚙️ Running & Testing Manually

```bash
python3 main.py
```

---

## ⏰ Daily Scheduling Guide

### Option A: macOS & Linux (`cron`)
1. Open cron configuration:
   ```bash
   crontab -e
   ```
2. Add the following entry to run every day at 8:00 AM (replace `/absolute/path/to/` with your local path):
   ```cron
   0 8 * * * /absolute/path/to/firebase-gemini-analysis/venv/bin/python "/absolute/path/to/firebase-gemini-analysis/main.py" >> "/absolute/path/to/firebase-gemini-analysis/cron_runner.log" 2>&1
   ```

### Option B: Windows Task Scheduler
1. Open **Task Scheduler** > **Create Basic Task**.
2. **Name**: `Daily Gemini Firebase Analytics`.
3. **Trigger**: Daily at desired time (e.g., 08:00 AM).
4. **Action**: `Start a program`.
5. **Program/script**: `C:\path\to\project\venv\Scripts\python.exe`
6. **Add arguments**: `main.py`
7. **Start in**: `C:\path\to\project`
