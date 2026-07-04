# =============================================================================
# run_all.py — Main script: run this to pull all YouTube Analytics data
# =============================================================================
# HOW TO USE:
#   1. Open your terminal / command prompt
#   2. Navigate to this folder:   cd path/to/youtube_analytics_tool
#   3. Run:                        python run_all.py
#
# The first time you run this for a channel, a browser window will open
# and the channel owner needs to log in with their Google account and
# click "Allow". After that, the token is saved locally and the browser
# won't open again for 30 days.
#
# Output files will appear in the output/ folder:
#   output/video_stats.csv
#   output/traffic_sources.csv
#   output/retention_curves.csv
#   output/audience_demographics.csv
#
# To revoke access for a channel at any time, uncomment the revoke line
# at the bottom of this file and run the script.
# =============================================================================

import sys
import os

from auth import get_authenticated_services, get_channel_id, revoke_access
import fetch_video_stats
import fetch_traffic_sources
import fetch_retention
import fetch_demographics


# =============================================================================
# SETTINGS — edit these before running
# =============================================================================

# A short nickname for the channel you're pulling data for.
# This becomes the name of the token file (e.g. tokens/test_channel.json)
# Use the same label each time for the same creator.
CHANNEL_LABEL = "test_channel"

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  YouTube Analytics Tool")
    print("=" * 60)

    # Step 1: Authenticate and get API service objects
    youtube, youtube_analytics = get_authenticated_services(CHANNEL_LABEL)

    if youtube is None:
        print("\n❌  Could not authenticate. Exiting.")
        print("    If access expired, re-run this script to trigger a new login.")
        sys.exit(1)

    # Step 2: Get the channel ID (needed for Analytics API queries)
    channel_id = get_channel_id(youtube)

    # Step 3: Get the video list once — shared across fetch scripts
    print("\n📋  Building video list (shared across all fetch steps)...")
    video_map = fetch_video_stats.get_all_video_ids(youtube)

    # Step 4: Fetch video stats → output/video_stats.csv
    fetch_video_stats.run(youtube, youtube_analytics, channel_id)

    # Step 5: Fetch traffic sources → output/traffic_sources.csv
    fetch_traffic_sources.run(youtube_analytics, channel_id, video_map)

    # Step 6: Fetch retention curves → output/retention_curves.csv
    fetch_retention.run(youtube_analytics, channel_id, video_map)

    # Step 7: Fetch demographics → output/audience_demographics.csv
    fetch_demographics.run(youtube_analytics, channel_id)

    # Done
    print("\n" + "=" * 60)
    print("  ✅  All done! Output files saved to the output/ folder.")
    print("=" * 60 + "\n")


# =============================================================================
# To immediately revoke a creator's access, uncomment this block,
# change the label to match theirs, and run the script.
# =============================================================================
# if __name__ == "__main__":
#     revoke_access("test_channel")
#     sys.exit(0)

if __name__ == "__main__":
    main()
