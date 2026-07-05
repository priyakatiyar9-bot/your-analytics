# =============================================================================
# fetch_comments.py — Pulls all public comments per video
# =============================================================================
# What this file does:
#   Uses the YouTube Data API v3 to fetch all public comments (and replies)
#   for every video on the channel, and saves them to comments.csv.
#
#   This is official API data — same source as what you see in YouTube Studio
#   under Comments, just pulled automatically for all videos at once.
#
# Output columns (comments.csv):
#   video_id, video_title, comment_id, parent_comment_id, author,
#   comment_text, like_count, reply_count, published_at, updated_at,
#   is_reply
#
# Notes:
#   - Only public comments are returned — if a creator has comments
#     disabled on a video, that video will have no rows.
#   - Replies to comments are included as separate rows, with
#     parent_comment_id filled in so you can link them back.
#   - The API returns max 100 comments per page — the script
#     automatically handles pagination to get all comments.
#   - Very high comment counts (10,000+) will make many API calls.
#     For a small channel this is not an issue.
# =============================================================================

import csv
import os

from config import OUTPUT_DIR


def fetch_comments_for_video(youtube, video_id, video_title):
    """
    Fetches all top-level comments and their replies for a single video.
    Returns a list of row dicts ready to write to CSV.
    """
    rows = []
    next_page_token = None

    while True:
        try:
            response = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText",  # strip HTML tags from comment text
            ).execute()
        except Exception as e:
            error_str = str(e)
            if "commentsDisabled" in error_str or "403" in error_str:
                # Comments are turned off for this video — skip silently
                break
            else:
                print(f"    ⚠️  Could not fetch comments for {video_id}: {e}")
                break

        for item in response.get("items", []):
            thread_id = item["id"]
            top = item["snippet"]["topLevelComment"]["snippet"]

            # Top-level comment
            rows.append({
                "video_id":          video_id,
                "video_title":       video_title,
                "comment_id":        thread_id,
                "parent_comment_id": "",
                "author":            top.get("authorDisplayName", ""),
                "comment_text":      top.get("textDisplay", "").replace("\n", " "),
                "like_count":        int(top.get("likeCount", 0)),
                "reply_count":       int(item["snippet"].get("totalReplyCount", 0)),
                "published_at":      top.get("publishedAt", "")[:10],
                "updated_at":        top.get("updatedAt", "")[:10],
                "is_reply":          "no",
            })

            # Replies to this comment (if any are included in the response)
            for reply in item.get("replies", {}).get("comments", []):
                r = reply["snippet"]
                rows.append({
                    "video_id":          video_id,
                    "video_title":       video_title,
                    "comment_id":        reply["id"],
                    "parent_comment_id": thread_id,
                    "author":            r.get("authorDisplayName", ""),
                    "comment_text":      r.get("textDisplay", "").replace("\n", " "),
                    "like_count":        int(r.get("likeCount", 0)),
                    "reply_count":       0,
                    "published_at":      r.get("publishedAt", "")[:10],
                    "updated_at":        r.get("updatedAt", "")[:10],
                    "is_reply":          "yes",
                })

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return rows


def run(youtube, video_map):
    """
    Main function — loops through all videos, fetches comments,
    and writes comments.csv.
    Called by run_all.py.

    video_map: dict of { video_id: { "title": ..., ... } }
    """
    print("\n💬  Fetching comments per video...")

    output_path = os.path.join(OUTPUT_DIR, "comments.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = [
        "video_id", "video_title", "comment_id", "parent_comment_id",
        "author", "comment_text", "like_count", "reply_count",
        "published_at", "updated_at", "is_reply",
    ]

    total_comments = 0
    videos_done = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for video_id, meta in video_map.items():
            videos_done += 1
            title = meta.get("title", "Unknown")
            print(f"  → [{videos_done}/{len(video_map)}] Comments: {title[:50]}...")

            rows = fetch_comments_for_video(youtube, video_id, title)
            writer.writerows(rows)
            total_comments += len(rows)
            print(f"    {len(rows)} comments fetched.")

    print(f"  ✅  comments.csv written — {total_comments} comments across "
          f"{videos_done} videos saved to {output_path}")
