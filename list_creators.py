# =============================================================================
# list_creators.py — Shows all creators who have connected via YouR
# =============================================================================
# Run this to see who has granted access and what their channel IDs are:
#   python3 list_creators.py
# =============================================================================

import os
import datetime
from dotenv import load_dotenv
load_dotenv()

from database import setup_database, list_all_tokens

setup_database()
creators = list_all_tokens()

if not creators:
    print("\nNo creators connected yet.\n")
else:
    print(f"\n{'Channel':<30} {'Label':<20} {'Expires':<15} {'Status'}")
    print("-" * 80)
    now = datetime.datetime.now()
    for c in creators:
        status = "✅ Active" if c["expires_at"] > now else "⏰ Expired"
        print(f"{c['channel_name']:<30} {c['channel_label']:<20} "
              f"{c['expires_at'].strftime('%d %b %Y'):<15} {status}")
        print(f"  Channel ID: {c['channel_id']}")
    print()
