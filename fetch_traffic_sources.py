# =============================================================================
# fetch_traffic_sources.py — Traffic source breakdown per video
# =============================================================================
# What this file does:
#   Queries the YouTube Analytics API with dimensions "video" and
#   "insightTrafficSourceType" to get a row for every (video, traffic source)
#   combination — e.g. how many views Video A got from Browse features,
#   how many from Suggested videos, etc.
#
#   This is the data that is NOT easily available via manual CSV export
#   at the per-video level, which is the main reason this tool exists.
#
# Output columns (traffic_sources.csv):
#   video_id, video_title, traffic_source_type, views, watch_time_hours,
#   average_view_duration, average_percentage_viewed, impressions,
#   impressions_click_through_rate
#
# Traffic source types you'll see in the output (these are Google's labels):
#   BROWSE          → Browse features (YouTube home page, Subscriptions feed)
#   SUGGESTED       → Suggested videos (sidebar / end screen suggestions)
#   YT_SEARCH       → YouTube Search
#   EXT_URL         → External websites and apps
#   DIRECT_OR_UNKNOWN → Direct or unknown (someone typed the URL or source unknown)
#   NOTIFICATION    → Notifications
#   PLAYLIST        → Playlists
#   SUBSCRIBER      → Subscriber feed
#   END_SCREEN      → End screens
#   CAMPAIGN_CARD   → Campaign cards
#   VIDEO_REMIXED   → Remixed / Shorts
#   NO_LINK_OTHER   → Other no-link sources
# =============================================================================

import csv
import os

from config import START_DATE, END_DATE, OUTPUT_DIR


# Maps the API's internal source type codes to friendlier labels.
# If a code appears that isn't in this map, it will be written as-is.
SOURCE_TYPE_LABELS = {
    "BROWSE":                "Browse features",
    "SUGGESTED":             "Suggested videos",
    "YT_SEARCH":             "YouTube Search",
    "EXT_URL":               "External",
    "DIRECT_OR_UNKNOWN":     "Direct or unknown",
    "NOTIFICATION":          "Notifications",
    "PLAYLIST":              "Playlists",
    "SUBSCRIBER":            "Subscriber feed",
    "END_SCREEN":            "End screen",
    "CAMPAIGN_CARD":         "Campaign cards",
    "VIDEO_REMIXED":         "Remixed / Shorts",
    "NO_LINK_OTHER":         "No link (other)",
    "NO_LINK_EMBEDDED":      "No link (embedded)",
    "SHORTS":                "YouTube Shorts feed",
    "PRODUCT_PAGE":          "Product page",
    "HASHTAG":               "Hashtag pages",
    "LIVE_REDIRECT":         "Live redirect",
}


def run(youtube_analytics, channel_id, video_map):
    """
    Main function — fetches traffic source data and writes traffic_sources.csv.
    Called by run_all.py.

    video_map: dict of { video_id: { "title": ..., ... } }
               passed in from run_all.py so we can look up video titles.
    """
    print("\n🚦  Fetching traffic source breakdown per video...")

    # Query Analytics API — one call gets all videos × all traffic source types
    print("  → Querying Analytics API for traffic sources...")
    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=START_DATE,
            endDate=END_DATE,
            dimensions="video,insightTrafficSourceType",
            metrics=(
                "views,"
                "estimatedMinutesWatched,"
                "averageViewDuration,"
                "averageViewPercentage,"
                "impressions,"
                "impressionsClickThroughRate"
            ),
            sort="video,-views",
            maxResults=500,  # covers ~25 videos × ~20 source types; increase if needed
        ).execute()
    except Exception as e:
        print(f"  ❌  Failed to fetch traffic source data: {e}")
        return

    column_headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows", [])
    print(f"  → Received {len(rows)} rows (video × source type combinations).")

    # Write to CSV
    output_path = os.path.join(OUTPUT_DIR, "traffic_sources.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = [
        "video_id",
        "video_title",
        "traffic_source_type",
        "views",
        "watch_time_hours",
        "average_view_duration",
        "average_percentage_viewed",
        "impressions",
        "impressions_click_through_rate",
    ]

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            row_dict = dict(zip(column_headers, row))
            vid_id = row_dict.get("video", "")
            source_code = row_dict.get("insightTrafficSourceType", "")

            # Look up the friendly label for this source type
            source_label = SOURCE_TYPE_LABELS.get(source_code, source_code)

            # Look up the video title from the video_map
            video_title = video_map.get(vid_id, {}).get("title", "Unknown")

            writer.writerow({
                "video_id": vid_id,
                "video_title": video_title,
                "traffic_source_type": source_label,
                "views": int(row_dict.get("views", 0)),
                "watch_time_hours": round(
                    float(row_dict.get("estimatedMinutesWatched", 0)) / 60, 1
                ),
                "average_view_duration": int(
                    row_dict.get("averageViewDuration", 0)
                ),
                "average_percentage_viewed": round(
                    float(row_dict.get("averageViewPercentage", 0)), 2
                ),
                "impressions": int(row_dict.get("impressions", 0) or 0),
                "impressions_click_through_rate": round(
                    float(row_dict.get("impressionsClickThroughRate", 0) or 0), 2
                ),
            })
            rows_written += 1

    print(f"  ✅  traffic_sources.csv written — {rows_written} rows saved to {output_path}")
