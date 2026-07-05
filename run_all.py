# =============================================================================
# run_all.py — Main script: run this to pull all YouTube Analytics data
# =============================================================================
# HOW TO USE:
#   1. Open Terminal and navigate to this folder
#   2. Run: python3 run_all.py
#
# This script pulls data for a creator whose token is stored in the database.
# The creator must have already connected via the YouR web app link,
# OR you can use local login mode (see LOCAL LOGIN below).
#
# Output files are saved to the output/ folder:
#   output/video_stats.csv
#   output/traffic_sources.csv
#   output/retention_curves.csv
#   output/audience_demographics.csv
# =============================================================================

import sys
import os

# Make sure DATABASE_URL is set before importing database module.
# When running locally, copy it from your Render dashboard into a .env file
# or set it in your terminal like: export DATABASE_URL="postgresql://..."
from dotenv import load_dotenv
load_dotenv()  # loads .env file if it exists

from database import setup_database, list_all_tokens
from auth import get_authenticated_services_local, get_services_from_db, get_channel_id
import fetch_video_stats
import fetch_traffic_sources
import fetch_retention
import fetch_demographics


# =============================================================================
# SETTINGS — edit these before running
# =============================================================================

# Choose how to authenticate:
#
# Option A — "web" (recommended once set up):
#   The creator connected via the YouR web link. Loads their token from
#   the database automatically. Set CHANNEL_ID to their YouTube channel ID.
#
# Option B — "local":
#   Opens a browser on your machine for login. Good for testing.
#   Set CHANNEL_LABEL to any short nickname for this channel.

AUTH_MODE = "local"         # change to "web" once creators are connecting via the app

CHANNEL_LABEL = "test_channel"   # used when AUTH_MODE = "local"
CHANNEL_ID    = ""               # used when AUTH_MODE = "web" — paste the creator's channel ID here


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  YouR — YouTube Resonance Analytics")
    print("=" * 60)

    # Make sure the database table exists
    setup_database()

    # Authenticate based on chosen mode
    if AUTH_MODE == "web":
        if not CHANNEL_ID:
            print("\n❌  CHANNEL_ID is empty. Paste the creator's YouTube channel ID")
            print("    (looks like UCxxxxxxxxxxxxxxxx) into run_all.py and try again.\n")
            print("    To see all connected creators and their IDs, run:")
            print("    python3 list_creators.py\n")
            sys.exit(1)

        print(f"\n📡  Loading credentials from database for channel: {CHANNEL_ID}")
        youtube, youtube_analytics = get_services_from_db(CHANNEL_ID)

    else:  # local mode
        print(f"\n💻  Local mode — authenticating as '{CHANNEL_LABEL}'")
        youtube, youtube_analytics = get_authenticated_services_local(CHANNEL_LABEL)

    if youtube is None:
        print("\n❌  Could not authenticate. Exiting.")
        sys.exit(1)

    # Get the channel ID
    channel_id = get_channel_id(youtube)

    # Get the video list — shared across all fetch scripts
    print("\n📋  Building video list...")
    video_map = fetch_video_stats.get_all_video_ids(youtube)

    # Fetch everything
    fetch_video_stats.run(youtube, youtube_analytics, channel_id)
    fetch_traffic_sources.run(youtube_analytics, channel_id, video_map)
    fetch_retention.run(youtube_analytics, channel_id, video_map)
    fetch_demographics.run(youtube_analytics, channel_id)

    print("\n" + "=" * 60)
    print("  ✅  Done! CSV files saved to the output/ folder.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
