<<<<<<< HEAD
# YouTube Analytics Tool — Setup & Usage Guide

This tool pulls YouTube Analytics data automatically via the YouTube API,
so you don't need to manually export CSVs from YouTube Studio.

---

## What you'll need before starting

- Python installed on your computer (version 3.8 or later)
- The `client_secret.json` file downloaded from Google Cloud Console
- Terminal / Command Prompt access

---

## Folder structure

Once set up, your folder should look like this:

```
youtube_analytics_tool/
├── client_secret.json       ← place this here (downloaded from Google Cloud Console)
├── config.py                ← settings (date range, etc.)
├── auth.py                  ← handles login and token storage
├── fetch_video_stats.py     ← fetches per-video core metrics
├── fetch_traffic_sources.py ← fetches traffic source breakdown per video
├── fetch_retention.py       ← fetches retention curves per video
├── fetch_demographics.py    ← fetches channel-level demographics
├── run_all.py               ← THE MAIN SCRIPT — run this one
├── requirements.txt         ← list of Python packages needed
├── tokens/                  ← created automatically; stores login tokens
└── output/                  ← created automatically; your CSV files appear here
```

---

## One-time setup (do this once)

### 1. Place client_secret.json in the folder
Copy your `client_secret.json` file into the `youtube_analytics_tool/` folder.

### 2. Open Terminal / Command Prompt
- **Mac:** press Cmd+Space, type "Terminal", press Enter
- **Windows:** press Win+R, type "cmd", press Enter

### 3. Navigate to the folder
Type this and press Enter (replace the path with wherever you saved the folder):
```
cd /path/to/youtube_analytics_tool
```

### 4. Install required Python packages
Type this and press Enter:
```
pip install -r requirements.txt
```
Wait for it to finish. You only need to do this once.

---

## Running the tool

### Each time you want to pull fresh data:

1. Open Terminal and navigate to the folder (step 3 above)
2. Run:
```
python run_all.py
```

**First time for a new channel:**
A browser window will open. The channel owner logs in with their Google account
and clicks "Allow". After that, access is saved for 30 days.

**After the first time:**
No browser needed — it uses the saved token automatically.

**After 30 days:**
The token expires automatically. Just run the script again and the browser will
open for the creator to re-grant access.

---

## Changing the channel

To pull data for a different channel, open `run_all.py` in a text editor and
change this line near the top:

```python
CHANNEL_LABEL = "test_channel"
```

Give each creator a short unique label (e.g. `"creator_jane"`, `"channel_2"`).
The label is used to name their token file — use the same label every time
you run for the same creator.

---

## Changing the date range

Open `config.py` and edit these two lines:
```python
START_DATE = "2020-01-01"
END_DATE = ...   # defaults to today
```

---

## Revoking a creator's access

To immediately stop the tool from accessing a creator's channel data,
open `run_all.py` and uncomment the revoke block at the very bottom:

```python
# if __name__ == "__main__":
#     revoke_access("test_channel")    ← change the label to match theirs
#     sys.exit(0)
```

Remove the `#` symbols from those three lines, save the file, and run:
```
python run_all.py
```

Their token file will be deleted. Remember to re-comment those lines afterward.

The creator can also fully remove the app permission on Google's side at:
https://myaccount.google.com/permissions

---

## Output files

All CSV files are saved to the `output/` folder:

| File | What it contains |
|------|-----------------|
| `video_stats.csv` | Per-video core metrics: views, watch time, impressions, CTR, likes, etc. |
| `traffic_sources.csv` | Per-video traffic source breakdown: Browse, Suggested, Search, External, etc. |
| `retention_curves.csv` | Per-video retention curve: what % of viewers are still watching at each point |
| `audience_demographics.csv` | Channel-level age and gender breakdown |

---

## Known limitations / things to check after first run

- **unique_viewers / returning_viewers / casual_viewers / regular_viewers** in
  `video_stats.csv`: These viewer-type breakdowns may show 0 for smaller channels
  if the API doesn't have enough data. Cross-check with YouTube Studio.

- **watch_time_hours_pct** in `audience_demographics.csv`: Currently uses the same
  value as views_pct as a placeholder. A future enhancement can calculate this
  separately.

- **retention viewer_type**: The API splits retention by "subscribed / unsubscribed"
  rather than "returning / new" exactly. Subscribed ≈ returning, unsubscribed ≈ new.
  This is the closest the API allows.

---

## Need help?

If the script crashes, copy the error message and share it — most errors during
first run are either a missing package (fix: re-run `pip install -r requirements.txt`)
or the `client_secret.json` file being in the wrong place.
=======
# your-analytics
>>>>>>> aa5df2c1939604ce7a19c1da6d013d8877edec05
