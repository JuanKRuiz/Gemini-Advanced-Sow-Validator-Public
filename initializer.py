# --- User Input Parameter ---
#@markdown 📄 **Paste the SoW URL (Google Doc or Drive file) to be reviewed here:**
SOW_URL = "PUT WORKSPACE DOCUMENT URL HERE" #@param {type:"string"}

# --- Input Validation ---
SOW_URL = SOW_URL.strip() # Remove leading/trailing whitespace

if not SOW_URL:
    print("🟡 **Action required:** Please enter the SoW URL in the field above and re-run the cell (or the entire notebook).")
elif "docs.google.com" not in SOW_URL:
    print(f"⚠️ **Warning:** The provided URL does not seem to be a Google Docs/Drive link. Please verify the URL.")
    print(f"   URL received: {SOW_URL}")
else:
    print(f"✅ SoW URL received: {SOW_URL}")
    print("You can now proceed to run the rest of the notebook.")

# --- System Configuration (Private) ---
PROMPT_URL    = "YOUR_PROMPT_DOC_URL_HERE"
CHECKLIST_URL = "YOUR_CHECKLIST_SHEET_URL_HERE"
TEMPLATE_URL  = "YOUR_REPORT_TEMPLATE_URL_HERE"
TARGET_SHEET_NAME = "Checklist Template"
START_CELL = "B26"
GEMINI_MODEL_NAME = "gemini-3-pro-preview"