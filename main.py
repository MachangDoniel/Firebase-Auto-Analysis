"""
Daily Firebase to Gemini AI Analysis Pipeline
Fetches documents from Firestore added in the past 24 hours,
sends them to the Gemini API for analysis, and logs the results.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import firebase_admin
from firebase_admin import credentials, firestore
from google import genai

# ==========================================
# Configuration & Environment Variables
# ==========================================
FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", str(BASE_DIR / "serviceAccountKey.json"))
FIREBASE_COLLECTION = os.getenv("FIREBASE_COLLECTION", "daily_metrics")
FIREBASE_TIMESTAMP_FIELD = os.getenv("FIREBASE_TIMESTAMP_FIELD", "timestamp")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LOG_FILE = BASE_DIR / "daily_analysis.log"

# Resolve relative path for credentials if needed
if not os.path.isabs(FIREBASE_KEY_PATH):
    FIREBASE_KEY_PATH = str(BASE_DIR / FIREBASE_KEY_PATH)


def init_firebase():
    """Initializes Firebase Admin SDK."""
    if not os.path.exists(FIREBASE_KEY_PATH):
        raise FileNotFoundError(
            f"Firebase service account key not found at '{FIREBASE_KEY_PATH}'. "
            "Please download your serviceAccountKey.json from Firebase Console."
        )
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
    
    return firestore.client()


def fetch_daily_data(db):
    """
    Fetches documents from Firestore added/modified in the last 24 hours.
    Requires a timestamp field in the documents.
    """
    print(f"[{datetime.now().isoformat()}] Fetching data from Firestore collection: '{FIREBASE_COLLECTION}'...")
    collection_ref = db.collection(FIREBASE_COLLECTION)
    
    # 24 hours ago (UTC and local naive safe fallback)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=1)
    
    daily_data = []
    try:
        # Query Firestore using the configured timestamp field
        query = collection_ref.where(FIREBASE_TIMESTAMP_FIELD, ">=", cutoff_time).stream()
        for doc in query:
            doc_dict = doc.to_dict()
            doc_dict["_id"] = doc.id
            daily_data.append(doc_dict)
    except Exception as e:
        print(f"Firestore query error: {e}", file=sys.stderr)
        raise

    print(f"Found {len(daily_data)} documents from the past 24 hours.")
    return daily_data


def analyze_with_gemini(data):
    """
    Sends fetched daily records to Gemini API for analytical evaluation.
    """
    if not data:
        return "No data recorded for the past 24 hours to analyze."

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in .env or your environment variables.")

    # Initialize modern Google GenAI Client
    client = genai.Client(api_key=gemini_api_key)

    print(f"Sending {len(data)} records to Gemini API ({GEMINI_MODEL})...")
    data_str = json.dumps(data, default=str, indent=2)

    prompt = f"""
You are an expert data analyst and insights specialist.
Please analyze the following daily data records collected over the last 24 hours.

Provide a comprehensive analysis including:
1. Executive Summary (Key highlights)
2. Key Metrics & Trends
3. Anomalies or Outliers (if any)
4. Actionable Recommendations

Data:
```json
{data_str}
```
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text


def log_results(analysis_result):
    """Logs the analysis output to console and appends to the log file."""
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    divider = "=" * 60
    log_entry = f"\n{divider}\n[DAILY AI ANALYSIS - {timestamp_str}]\n{divider}\n{analysis_result}\n"

    print(log_entry)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)

    print(f"Analysis saved to: {LOG_FILE}")


def main():
    print(f"=== Starting Daily AI Analysis Pipeline: {datetime.now()} ===")
    try:
        db = init_firebase()
        data = fetch_daily_data(db)
        result = analyze_with_gemini(data)
        log_results(result)
        print("=== Pipeline Execution Finished Successfully ===")
    except Exception as err:
        print(f"Error during pipeline execution: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
