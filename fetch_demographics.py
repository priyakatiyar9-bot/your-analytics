# =============================================================================
# fetch_demographics.py — Channel-level audience demographics
# =============================================================================
# What this file does:
#   Queries the YouTube Analytics API for age group and gender breakdown
#   of the channel's audience — what percentage of views and watch time
#   comes from each age/gender group.
#
#   This is channel-level only — YouTube does not expose per-video
#   demographics via the API (or in Studio).
#
# Output columns (audience_demographics.csv):
#   viewer_age, viewer_gender, views_pct, watch_time_hours_pct
#
# Age groups returned by the API:
#   age13-17, age18-24, age25-34, age35-44, age45-54, age55-64, age65-
#
# Gender values:
#   female, male, user_specified
# =============================================================================

import csv
import os

from config import START_DATE, END_DATE, OUTPUT_DIR


# Maps the API's age group codes to the format used in your CSV
AGE_GROUP_LABELS = {
    "age13-17": "13–17 years",
    "age18-24": "18–24 years",
    "age25-34": "25–34 years",
    "age35-44": "35–44 years",
    "age45-54": "45–54 years",
    "age55-64": "55–64 years",
    "age65-":   "65+ years",
}

GENDER_LABELS = {
    "female":         "female",
    "male":           "male",
    "user_specified": "user specified",
}


def run(youtube_analytics, channel_id):
    """
    Main function — fetches demographic data and writes audience_demographics.csv.
    Called by run_all.py.
    """
    print("\n👥  Fetching channel-level audience demographics...")

    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=START_DATE,
            endDate=END_DATE,
            dimensions="ageGroup,gender",
            metrics="viewerPercentage",
        ).execute()
    except Exception as e:
        print(f"  ❌  Failed to fetch demographics: {e}")
        print("      This can happen if the channel has insufficient data.")
        return

    column_headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows", [])

    if not rows:
        print("  ⚠️  No demographic data returned. The channel may not have enough")
        print("      views yet for YouTube to generate demographic breakdowns.")
        return

    print(f"  → Received {len(rows)} age/gender combinations.")

    # The API only returns viewerPercentage (views %).
    # Watch time % is not directly returned separately — we write the same
    # value for both columns as a placeholder, matching the shape of your CSV.
    # If you need true watch_time_hours_pct, this would require a second query
    # with estimatedMinutesWatched and manual percentage calculation.
    # Flag this for your brother to enhance if needed.

    output_path = os.path.join(OUTPUT_DIR, "audience_demographics.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fieldnames = ["viewer_age", "viewer_gender", "views_pct", "watch_time_hours_pct"]

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            row_dict = dict(zip(column_headers, row))
            age_code = row_dict.get("ageGroup", "")
            gender_code = row_dict.get("gender", "")
            pct = round(float(row_dict.get("viewerPercentage", 0)), 1)

            writer.writerow({
                "viewer_age":           AGE_GROUP_LABELS.get(age_code, age_code),
                "viewer_gender":        GENDER_LABELS.get(gender_code, gender_code),
                "views_pct":            pct,
                "watch_time_hours_pct": pct,  # placeholder — see note above
            })
            rows_written += 1

    print(f"  ✅  audience_demographics.csv written — {rows_written} rows saved to {output_path}")
