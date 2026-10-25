#!/usr/bin/env python
"""Cloud runner for GitHub Actions or headless cron.

Checks if any post is due right now.
If IDLE: exits quietly with 0.
If DUE: publishes via Twitter API v2, marks the slot posted, and exits 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import post_api


def main() -> int:
    # 1. Check schedule
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "due.py"), "check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = (proc.stdout or "").strip()
    if not output or output == "IDLE":
        print("Schedule check: IDLE (nothing due right now).")
        return 0

    try:
        draft = json.loads(output)
    except Exception as e:
        print(f"Error parsing draft JSON: {e}\nRaw output: {output[:200]}", file=sys.stderr)
        return 1

    slot = draft.get("slot")
    text = draft.get("text", "")
    date = draft.get("date")

    if not slot or not text:
        print(f"Draft missing slot or text: {draft}", file=sys.stderr)
        return 1

    print(f"🔔 Slot {slot} is DUE! Publishing via Twitter API v2...")

    # 2. Publish via API
    res = post_api.post_tweet(text)
    if not res.get("ok"):
        print(f"❌ Tweet publication failed: {res.get('error')}", file=sys.stderr)
        return 1

    tweet_url = res.get("tweet_url", "")
    print(f"🎉 Successfully published tweet! URL: {tweet_url}")

    # 3. Mark slot as posted in drafts/
    mark_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "due.py"),
        "mark",
        "--slot",
        slot,
    ]
    if date:
        mark_cmd.extend(["--date", date])
    if tweet_url:
        mark_cmd.extend(["--url", tweet_url])

    subprocess.run(mark_cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(f"✅ Slot {slot} marked as POSTED in plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
