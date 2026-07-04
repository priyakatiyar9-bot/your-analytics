# =============================================================================
# fetch_video_stats.py — Pulls per-video stats and saves to video_stats.csv
# =============================================================================
# What this file does:
#   Step 1: Gets the full list of videos on the channel (title, publish date,
#           duration) from the YouTube Data API.
#   Step 2: Queries the YouTube Analytics API for each video's performance
#           metrics (views, watch time, impressions, likes, etc.)
#   Step 3: Combines both and saves to output/video_stats.csv
#
# Output columns match your existing video_stats.csv exactly:
#   video_id, content, video_title, video_publish_time, duration, views,
#   watch_time_hours, subscribers, average_view_duration,
#   average_percentage_viewed, impressions, impression_click_through_rate,
#   unique_viewers, returning_viewers, casual_viewers, regular_viewers,
#   subscribers_gained, subscribers_lost, likes, dislikes
#
# Note on unique_viewers / returning_viewers / casual_viewers / regular_viewers:
#   These viewer-type breakdowns are not consistently available via the
#   Analytics API for all channels and date ranges. The script will attempt
#   to fetch them, but if the API returns nothing it will write 0 rather
#   than crashing. Flag these for manual verification against YouTube Studio.
# =============================================================================

import csv
import os
import isodate  # converts YouTube's ISO 8601 duration format (e.g. PT5M30S) to seconds

from config import START_DATE, END_DATE, OUTPUT_DIR


def iso_duration_to_seconds(iso_str):
    """
    Converts YouTube's ISO 8601 duration string to total seconds.
    Example: "PT22M50S" → 1370 seconds
    """
    try:
        return int(isodate.parse_duration(iso_str).total_seconds())
    except Exception:
        return 0


def get_all_video_ids(youtube):
    """
    Returns a list of all video IDs and basic metadata for the authenticated channel,
    by walking through the channel's uploads playlist.

    Returns a dict: { video_id: { "title": ..., "publish_time": ..., "duration": ... } }
    """
    print("  → Getting uploads playlist ID...")

    # Get the uploads playlist ID for this channel
    channel_response = youtube.channels().list(
        part="contentDetails", mine=True
    ).execute()
    uploads_playlist_id = (
        channel_response["items"][0]["contentDetails"]
        ["relatedPlaylists"]["uploads"]
    )

    print("  → Fetching video list from uploads playlist...")

    videos = {}
    next_page_token = None

    # Loop through all pages of the uploads playlist
    while True:
        playlist_response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        video_ids = [
            item["contentDetails"]["videoId"]
            for item in playlist_response.get("items", [])
        ]

        # Fetch details for these video IDs (title, publish date, duration)
        if video_ids:
            details_response = youtube.videos().list(
                part="snippet,contentDetails",
                id=",".join(video_ids),
            ).execute()

            for item in details_response.get("items", []):
                vid_id = item["id"]
                videos[vid_id] = {
                    "title": item["snippet"]["title"],
                    "publish_time": item["snippet"]["publishedAt"][:10],  # "YYYY-MM-DD"
                    "duration": iso_duration_to_seconds(
                        item["contentDetails"]["duration"]
                    ),
                }

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    print(f"  → Found {len(videos)} videos on the channel.")
    return videos


def fetch_analytics_for_all_videos(youtube_analytics, channel_id):
    """
    Queries the Analytics API for core metrics across all videos in one call.
    Returns a dict: { video_id: { metric_name: value, ... } }
    """
    print("  → Querying Analytics API for core video metrics...")

    response = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=START_DATE,
        endDate=END_DATE,
        dimensions="video",
        metrics=(
            "views,"
            "estimatedMinutesWatched,"
            "averageViewDuration,"
            "averageViewPercentage,"
            "impressions,"
            "impressionsClickThroughRate,"
            "subscribersGained,"
            "subscribersLost,"
            "likes,"
            "dislikes,"
            "comments"
        ),
        sort="-views",
        maxResults=200,  # increase if you have more than 200 videos
    ).execute()

    analytics = {}
    column_headers = [h["name"] for h in response.get("columnHeaders", [])]

    for row in response.get("rows", []):
        row_dict = dict(zip(column_headers, row))
        vid_id = row_dict.get("video")
        if vid_id:
            analytics[vid_id] = {
                "views": int(row_dict.get("views", 0)),
                # Convert minutes → hours, rounded to 1 decimal
                "watch_time_hours": round(
                    float(row_dict.get("estimatedMinutesWatched", 0)) / 60, 1
                ),
                # averageViewDuration is in seconds
                "average_view_duration": int(
                    row_dict.get("averageViewDuration", 0)
                ),
                "average_percentage_viewed": round(
                    float(row_dict.get("averageViewPercentage", 0)), 2
                ),
                "impressions": int(row_dict.get("impressions", 0)),
                "impression_click_through_rate": round(
                    float(row_dict.get("impressionsClickThroughRate", 0)), 2
                ),
                "subscribers_gained": int(row_dict.get("subscribersGained", 0)),
                "subscribers_lost": int(row_dict.get("subscribersLost", 0)),
                "likes": int(row_dict.get("likes", 0)),
                "dislikes": int(row_dict.get("dislikes", 0)),
            }

    return analytics


def fetch_viewer_types(youtube_analytics, channel_id):
    """
    Attempts to fetch unique viewer counts broken down by viewer type.

    These columns (unique_viewers, returning_viewers, casual_viewers,
    regular_viewers) are not always available via the Analytics API —
    availability depends on channel size and data thresholds.

    If the API returns nothing, all values default to 0.
    Returns a dict: { video_id: { "unique_viewers": ..., etc. } }
    """
    print("  → Attempting to fetch viewer type breakdown (may not be available for all channels)...")

    viewer_data = {}

    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=START_DATE,
            endDate=END_DATE,
            dimensions="video,viewerType",
            metrics="views",
            maxResults=500,
        ).execute()

        column_headers = [h["name"] for h in response.get("columnHeaders", [])]

        for row in response.get("rows", []):
            row_dict = dict(zip(column_headers, row))
            vid_id = row_dict.get("video")
            viewer_type = row_dict.get("viewerType", "").lower()
            count = int(row_dict.get("views", 0))

            if vid_id not in viewer_data:
                viewer_data[vid_id] = {
                    "unique_viewers": 0,
                    "returning_viewers": 0,
                    "casual_viewers": 0,
                    "regular_viewers": 0,
                }

            # Map API's viewer type labels to your CSV column names
            if viewer_type == "returning":
                viewer_data[vid_id]["returning_viewers"] = count
            elif viewer_type == "casual":
                viewer_data[vid_id]["casual_viewers"] = count
            elif viewer_type == "regular":
                viewer_data[vid_id]["regular_viewers"] = count

            # unique_viewers = sum of all types
            viewer_data[vid_id]["unique_viewers"] += count

    except Exception as e:
        print(f"  ⚠️  Viewer type data not available: {e}")
        print("      Columns will be written as 0. Check YouTube Studio manually if needed.")

    return viewer_data


def fetch_channel_subscriber_count(youtube):
    """
    Returns the channel's current subscriber count.
    Used to populate the 'subscribers' column.
    """
    response = youtube.channels().list(
        part="statistics", mine=True
    ).execute()
    return int(
        response["items"][0]["statistics"].get("subscriberCount", 0)
    )


def run(youtube, youtube_analytics, channel_id):
    """
    Main function — fetches everything and writes video_stats.csv.
    Called by run_all.py.
    """
    print("\n📊  Fetching video stats...")

    # Step 1: Get all videos and their metadata
    videos = get_all_video_ids(youtube)

    # Step 2: Get analytics metrics for all videos
    analytics = fetch_analytics_for_all_videos(youtube_analytics, channel_id)

    # Step 3: Get viewer type breakdown (best effort)
    viewer_types = fetch_viewer_types(youtube_analytics, channel_id)

    # Step 4: Get current subscriber count
    subscriber_count = fetch_channel_subscriber_count(youtube)

    # Step 5: Combine everything and write to CSV
    output_path = os.path.join(OUTPUT_DIR, "video_stats.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = [
        "video_id", "content", "video_title", "video_publish_time",
        "duration", "views", "watch_time_hours", "subscribers",
        "average_view_duration", "average_percentage_viewed",
        "impressions", "impression_click_through_rate",
        "unique_viewers", "returning_viewers", "casual_viewers",
        "regular_viewers", "subscribers_gained", "subscribers_lost",
        "likes", "dislikes",
    ]

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for video_id, meta in videos.items():
            a = analytics.get(video_id, {})
            v = viewer_types.get(video_id, {})

            writer.writerow({
                "video_id": video_id,
                "content": "Video",
                "video_title": meta["title"],
                "video_publish_time": meta["publish_time"],
                "duration": meta["duration"],
                "views": a.get("views", 0),
                "watch_time_hours": a.get("watch_time_hours", 0),
                "subscribers": subscriber_count,
                "average_view_duration": a.get("average_view_duration", 0),
                "average_percentage_viewed": a.get("average_percentage_viewed", 0),
                "impressions": a.get("impressions", 0),
                "impression_click_through_rate": a.get("impression_click_through_rate", 0),
                "unique_viewers": v.get("unique_viewers", 0),
                "returning_viewers": v.get("returning_viewers", 0),
                "casual_viewers": v.get("casual_viewers", 0),
                "regular_viewers": v.get("regular_viewers", 0),
                "subscribers_gained": a.get("subscribers_gained", 0),
                "subscribers_lost": a.get("subscribers_lost", 0),
                "likes": a.get("likes", 0),
                "dislikes": a.get("dislikes", 0),
            })
            rows_written += 1

    print(f"  ✅  video_stats.csv written — {rows_written} videos saved to {output_path}")
