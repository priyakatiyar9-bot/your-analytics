# =============================================================================
# fetch_retention.py — Audience retention curve data per video
# =============================================================================
# What this file does:
#   For each video, queries the Analytics API for its audience retention curve —
#   i.e. what percentage of viewers are still watching at each point in the video.
#
#   It also attempts to split this by viewer type (subscribed vs unsubscribed
#   as a proxy for returning vs new viewers). If that split isn't available for
#   a video, it falls back to fetching the combined curve instead.
#
# How the time axis works:
#   The API returns retention in terms of "elapsed video time ratio" — a
#   percentage from 0.0 (start) to 1.0 (end) — not in actual seconds.
#   We convert this to seconds using each video's known duration, then
#   round to the nearest 15 seconds to match your existing CSV format.
#
# Output columns (retention_curves.csv):
#   video_id, video_title, viewer_type, timestamp_seconds, retention_pct
#
# viewer_type values:
#   "returning"  → SUBSCRIBED viewers (closest available proxy for returning)
#   "new"        → UNSUBSCRIBED viewers (closest available proxy for new)
#   "all"        → combined (used as fallback if split is unavailable)
#
# Note: The subscribed/unsubscribed split is the best approximation the API
# provides. It is not identical to "returning vs new" in YouTube Studio,
# but it is the closest available via the API.
# =============================================================================

import csv
import os

from config import START_DATE, END_DATE, OUTPUT_DIR


def ratio_to_seconds(ratio, duration_seconds):
    """
    Converts a 0.0–1.0 elapsed time ratio to seconds,
    rounded to the nearest 15 seconds.

    Example: ratio=0.25, duration=1200s → 300s (5 minutes)
    """
    raw_seconds = ratio * duration_seconds
    return int(round(raw_seconds / 15) * 15)


def fetch_retention_for_video(youtube_analytics, channel_id, video_id,
                               video_title, duration_seconds, start_date):
    """
    Fetches retention curve data for a single video.

    First attempts to get the SUBSCRIBED / UNSUBSCRIBED split.
    Falls back to the combined curve if the split isn't available.

    Returns a list of row dicts ready to be written to CSV.
    """
    rows = []

    # --- Attempt 1: Split by subscribed status ---
    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=END_DATE,
            dimensions="elapsedVideoTimeRatio,subscribedStatus",
            metrics="audienceWatchRatio",
            filters=f"video=={video_id}",
        ).execute()

        api_rows = response.get("rows", [])

        if api_rows:
            column_headers = [h["name"] for h in response.get("columnHeaders", [])]
            for row in api_rows:
                row_dict = dict(zip(column_headers, row))
                ratio = float(row_dict.get("elapsedVideoTimeRatio", 0))
                subscribed_status = row_dict.get("subscribedStatus", "").upper()
                retention = round(
                    float(row_dict.get("audienceWatchRatio", 0)) * 100, 2
                )

                # Map API labels to viewer_type labels
                viewer_type = "returning" if subscribed_status == "SUBSCRIBED" else "new"

                rows.append({
                    "video_id": video_id,
                    "video_title": video_title,
                    "viewer_type": viewer_type,
                    "timestamp_seconds": ratio_to_seconds(ratio, duration_seconds),
                    "retention_pct": retention,
                })
            return rows

    except Exception:
        pass  # Fall through to the combined query below

    # --- Fallback: Combined curve (no split) ---
    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=END_DATE,
            dimensions="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio",
            filters=f"video=={video_id}",
        ).execute()

        api_rows = response.get("rows", [])
        column_headers = [h["name"] for h in response.get("columnHeaders", [])]

        for row in api_rows:
            row_dict = dict(zip(column_headers, row))
            ratio = float(row_dict.get("elapsedVideoTimeRatio", 0))
            retention = round(
                float(row_dict.get("audienceWatchRatio", 0)) * 100, 2
            )

            rows.append({
                "video_id": video_id,
                "video_title": video_title,
                "viewer_type": "all",
                "timestamp_seconds": ratio_to_seconds(ratio, duration_seconds),
                "retention_pct": retention,
            })

    except Exception as e:
        print(f"    ⚠️  Could not fetch retention for video {video_id}: {e}")

    return rows


def run(youtube_analytics, channel_id, video_map):
    """
    Main function — loops through all videos, fetches retention curves,
    and writes retention_curves.csv.
    Called by run_all.py.

    video_map: dict of { video_id: { "title": ..., "publish_time": ..., "duration": ... } }
    """
    print("\n📈  Fetching retention curves per video...")

    output_path = os.path.join(OUTPUT_DIR, "retention_curves.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = [
        "video_id", "video_title", "viewer_type",
        "timestamp_seconds", "retention_pct"
    ]

    total_rows = 0
    videos_done = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for video_id, meta in video_map.items():
            videos_done += 1
            title = meta.get("title", "Unknown")
            duration = meta.get("duration", 0)
            publish_date = meta.get("publish_time", START_DATE)

            print(f"  → [{videos_done}/{len(video_map)}] Fetching retention: {title[:50]}...")

            if duration == 0:
                print(f"    ⚠️  Skipping — duration unknown, can't convert ratios to seconds.")
                continue

            rows = fetch_retention_for_video(
                youtube_analytics, channel_id,
                video_id, title, duration, publish_date
            )

            writer.writerows(rows)
            total_rows += len(rows)

    print(f"  ✅  retention_curves.csv written — {total_rows} data points across "
          f"{videos_done} videos saved to {output_path}")
