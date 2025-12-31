#@title Installation and Imports

# --- 1. Library Installation ---
# Installs dependencies for Google and Gemini APIs.
!pip install -q -U google-genai google-api-python-client google-auth-httplib2 google-auth-oauthlib

# --- 2. Public Library Imports ---
# Imports all third-party and standard libraries needed for the
# classes that will be defined in the subsequent cells.
# Google API and Gemini Libraries
from google import genai
from google.colab import auth, userdata
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# IPython/Jupyter Libraries
from IPython.display import display, HTML

print("✅ Libraries installed and imported.")

