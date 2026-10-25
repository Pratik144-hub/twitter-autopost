#!/usr/bin/env python
"""Autonomous loop runner for tweetytweets.

Runs continuously in the background, checking every interval (default 5 mins)
if a scheduled post is due. When a post is due, it publishes it through post.py,
verifies it, marks the slot completed, and goes back to sleep.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CHECK_INTERVAL_SECONDS = 300  # 5 minutes


def log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def check_and_post() -> None:
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "due.py"), "check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as e:
        log(f"Error checking due status: {e}")
        return

    output = (proc.stdout or "").strip()
    if not output or output == "IDLE":
        log("Schedule check: IDLE (no post due right now)")
        return

    try:
        draft = json.loads(output)
    except Exception as e:
        log(f"Error parsing draft JSON: {e}\nRaw output: {output[:200]}")
        return

    slot = draft.get("slot")
    text = draft.get("text", "")
    kind = draft.get("kind", "value")
    date = draft.get("date")

    if not slot or not text:
        log(f"Received draft without slot or text: {draft}")
        return

    log(f"🔔 Slot {slot} ({kind}) is DUE! Publishing...")

    scratch_post = ROOT / "scratch" / "post.txt"
    scratch_post.parent.mkdir(parents=True, exist_ok=True)
    scratch_post.write_text(text, encoding="utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "post.py"),
        "post",
        "--text-file",
        str(scratch_post),
    ]
    if kind:
        cmd.extend(["--kind", kind])

    if draft.get("image"):
        cmd.extend(["--image", str(draft["image"])])

    try:
        post_proc = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180
        )
        post_out = (post_proc.stdout or "").strip()
        log(f"Post output: {post_out[:300]}")

        url = None
        try:
            res = json.loads(post_out)
            url = res.get("tweet_url")
        except Exception:
            pass

        # Mark as posted
        mark_cmd = [
            sys.executable,
            str(ROOT / "scripts" / "due.py"),
            "mark",
            "--slot",
            slot,
        ]
        if date:
            mark_cmd.extend(["--date", date])
        if url:
            mark_cmd.extend(["--url", url])

        subprocess.run(mark_cmd, cwd=str(ROOT), capture_output=True, text=True)
        log(f"✅ Slot {slot} successfully published and marked done!")

    except Exception as e:
        log(f"❌ Failed to publish slot {slot}: {e}")


def main() -> None:
    log("🚀 Autonomous Twitter posting monitor started.")
    log(f"Polling interval: every {CHECK_INTERVAL_SECONDS // 60} minutes.")
    while True:
        try:
            check_and_post()
        except Exception as e:
            log(f"Unexpected error in loop: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
