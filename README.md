# Daily Firebase to Gemini AI Analysis Pipeline

## 📌 Project Overview
Automated Python pipeline running on a local machine (macOS/Linux/Windows) that:
1. Connects to **Google Cloud Firestore (Firebase)**.
2. Queries and fetches documents/records created or updated in the last **24 hours**.
3. Formats and sends the daily payload to **Google Gemini API** (using the modern `google-genai` SDK and models like `gemini-2.5-flash` / `gemini-1.5-flash` / `gemini-1.5-pro`).
4. Generates data insights, trend analysis, summaries, and writes results to logs/console.
5. Runs automatically on a daily schedule using OS-level task runners (**cron** / **Task Scheduler**).

---

## 💰 Pricing & Free Tier Clarification

| Service | Free Tier / Plan | Limits & Notes |
| :--- | :--- | :--- |
| **Firebase Firestore** | **Spark Plan (Free)** | • **50,000 document reads/day**<br>• **20,000 document writes/day**<br>• **1 GB total storage**<br>*(No credit card required for Spark plan)* |
| **Gemini Developer API** | **Google AI Studio (Free Tier)** | • Free rate limits (RPM/TPM/RPD)<br>• Separate from consumer Gemini Advanced/Pro subscription<br>• *Note: Free tier prompts may be used for model training. Paid API tier provides privacy opt-out.* |

---

## 🛠️ Tech Stack & Dependencies
- **Language**: Python 3.10+ (Python 3.9+ compatible)
- **Firebase SDK**: `firebase-admin` (v7.5.0)
- **Gemini SDK**: `google-genai` (v1.47.0)
- **Environment Management**: `python-dotenv` (v1.2.1)
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

### 3. Firebase Credentials Setup
1. Go to [Firebase Console](https://console.firebase.google.com/).
2. Select your project > **Project Settings (Gear icon)** > **Service Accounts**.
3. Click **Generate New Private Key**.
4. Save the downloaded JSON file as `serviceAccountKey.json` in this directory.
   *(Make sure `serviceAccountKey.json` is listed in `.gitignore`)*

### 4. Gemini API Key Setup
1. Go to [Google AI Studio](https://aistudio.google.com/) and create an API Key.
2. Create your `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
3. Set your environment variables in `.env`:
   ```ini
   GEMINI_API_KEY="your_actual_gemini_api_key_here"
   FIREBASE_COLLECTION="your_collection_name"
   FIREBASE_KEY_PATH="serviceAccountKey.json"
   GEMINI_MODEL="gemini-2.5-flash"
   ```

---

## 📂 Project Structure

```
.
├── README.md               # Complete project documentation & context
├── requirements.txt        # Pinned Python package dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Protects keys, logs, and virtual environments
├── main.py                 # Core extraction and AI analysis script
├── daily_analysis.log      # Output log file (generated after runs)
└── serviceAccountKey.json  # Firebase Service Account Key (keep private)
```

---

## ⚙️ Running & Testing Manually

Run the script directly inside your virtual environment:
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
2. **Name**: `Daily Gemini Firebase Analysis`.
3. **Trigger**: Daily at desired time (e.g., 08:00 AM).
4. **Action**: `Start a program`.
5. **Program/script**: `C:\path\to\project\venv\Scripts\python.exe`
6. **Add arguments**: `main.py`
7. **Start in**: `C:\path\to\project`

---

## 🔍 Firestore Data Schema Requirements
- Documents queried must have a timestamp field (default: `timestamp`, `createdAt`, or `date`).
- Firestore query filters:
  ```python
  collection_ref.where('timestamp', '>=', yesterday).stream()
  ```
- If your timestamps are stored as ISO strings or custom integer epochs, adjust the `fetch_daily_data()` filter accordingly in `main.py`.
