# =============================================================================
# config.py — Settings for the YouTube Analytics Tool
# =============================================================================
# This is the only file you should need to edit regularly.
# Everything else in the tool reads from here.
# =============================================================================

from datetime import datetime

# --- Date range ---
# The tool will pull data for videos published between these two dates.
# START_DATE: how far back to go (format: "YYYY-MM-DD")
# END_DATE: defaults to today automatically — you can hardcode one if you want
START_DATE = "2020-01-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")

# --- Access duration ---
# How many days a creator's OAuth access lasts before the script stops using it.
# After this many days the creator will need to log in again to re-grant access.
ACCESS_DURATION_DAYS = 30

# --- File paths ---
# Where the client_secret.json file lives (should be in the same folder as these scripts)
CLIENT_SECRET_FILE = "client_secret.json"

# Where per-channel tokens are stored (one file per channel, created automatically)
TOKENS_DIR = "tokens"

# Where output CSV files are saved
OUTPUT_DIR = "output"
