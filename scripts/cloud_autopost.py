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


def log_summary(text: str) -> None:
    print(text)
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass


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
        log_summary("### ⏱️ Schedule check: IDLE\nNo post is due right now.")
        return 0

    try:
        draft = json.loads(output)
    except Exception as e:
        msg = f"❌ Error parsing draft JSON: {e}\nRaw output: {output[:200]}"
        log_summary(f"### {msg}")
        return 1

    slot = draft.get("slot")
    text = draft.get("text", "")
    date = draft.get("date")

    if not slot or not text:
        log_summary(f"### ❌ Draft missing slot or text:\n```json\n{json.dumps(draft, indent=2)}\n```")
        return 1

    log_summary(f"### 🔔 Slot `{slot}` is DUE! Publishing via Twitter API v2...")

    # 2. Publish via API
    try:
        res = post_api.post_tweet(text)
    except Exception as err:
        log_summary(f"### ❌ Exception in post_tweet:\n```\n{err}\n```")
        return 1

    if not res.get("ok"):
        status = res.get("status_code", "unknown")
        err = res.get("error", {})
        raw = res.get("raw", "")
        log_summary(f"### ❌ Tweet publication failed!\n* **Status Code:** `{status}`\n* **Error Details:**\n```json\n{json.dumps(err, indent=2) if isinstance(err, dict) else str(err)}\n```\n```\n{raw}\n```")
        return 1

    tweet_url = res.get("tweet_url", "")
    log_summary(f"### 🎉 Successfully published tweet!\n* **URL:** [{tweet_url}]({tweet_url})")

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
    log_summary(f"✅ Slot `{slot}` marked as POSTED in schedule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
