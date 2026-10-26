#!/usr/bin/env python
"""Publish tweets directly via Twitter API v2 using OAuth 1.0a.

Uses requests-oauthlib for 100% reliable Twitter API v2 authentication.
Handles multiple environment variable naming conventions and strips quotes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = ROOT / "secrets.json"


def _clean(val: str | None) -> str:
    if not val:
        return ""
    return str(val).strip().strip('"').strip("'").strip()


def get_first_env(*keys: str) -> str:
    for k in keys:
        val = os.getenv(k)
        if val:
            return _clean(val)
    return ""


def get_credentials() -> dict[str, str]:
    """Load credentials from environment variables or secrets.json."""
    creds = {
        "consumer_key": get_first_env(
            "TWITTER_CONSUMER_KEY", "TWITTER_API_KEY", "API_KEY", "CONSUMER_KEY"
        ),
        "consumer_secret": get_first_env(
            "TWITTER_CONSUMER_SECRET",
            "TWITTER_API_SECRET",
            "API_KEY_SECRET",
            "API_SECRET",
            "CONSUMER_SECRET",
        ),
        "access_token": get_first_env("TWITTER_ACCESS_TOKEN", "ACCESS_TOKEN"),
        "access_token_secret": get_first_env(
            "TWITTER_ACCESS_TOKEN_SECRET", "ACCESS_TOKEN_SECRET", "ACCESS_SECRET"
        ),
    }

    if not all(creds.values()) and SECRETS_FILE.exists():
        try:
            saved = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
            for k in creds:
                if not creds[k]:
                    creds[k] = _clean(saved.get(k, ""))
        except Exception as e:
            print(f"Warning: could not read {SECRETS_FILE}: {e}", file=sys.stderr)

    # Print credential diagnostic summary (masks actual values)
    print("--- Twitter API Credentials Diagnostic ---")
    for k, v in creds.items():
        if v:
            masked = v[:3] + "..." + v[-3:] if len(v) > 6 else "***"
            print(f"  {k}: [FOUND] (length={len(v)}, sample={masked})")
        else:
            print(f"  {k}: [MISSING]")
    print("------------------------------------------")

    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise ValueError(
            f"Missing Twitter API credentials: {', '.join(missing)}.\n"
            f"Please verify these secrets are added in your GitHub repository settings."
        )

    return creds


def post_tweet(text: str) -> dict:
    """Post a tweet using Twitter API v2 endpoint via requests-oauthlib."""
    try:
        from requests_oauthlib import OAuth1
        import requests
    except ImportError:
        raise RuntimeError("Missing dependencies. Run: pip install requests requests-oauthlib")

    creds = get_credentials()
    url = "https://api.twitter.com/2/tweets"

    auth = OAuth1(
        client_key=creds["consumer_key"],
        client_secret=creds["consumer_secret"],
        resource_owner_key=creds["access_token"],
        resource_owner_secret=creds["access_token_secret"],
    )

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TweetyTweets/1.0",
    }

    payload = {"text": text}

    try:
        response = requests.post(url, auth=auth, json=payload, headers=headers, timeout=30)
        status_code = response.status_code
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        if 200 <= status_code < 300 and "data" in data and "id" in data["data"]:
            tweet_id = data["data"]["id"]
            tweet_url = f"https://x.com/i/status/{tweet_id}"
            return {
                "ok": True,
                "id": tweet_id,
                "tweet_url": tweet_url,
                "text": text,
                "response": data,
            }
        else:
            return {
                "ok": False,
                "status_code": status_code,
                "error": data,
                "raw": response.text,
            }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Post a tweet via Twitter API v2.")
    parser.add_argument("--text", help="Tweet text to publish")
    parser.add_argument("--text-file", help="Path to text file containing tweet text")
    args = parser.parse_args()

    text = ""
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text.strip()
    else:
        text = sys.stdin.read().strip()

    if not text:
        print("Error: No tweet text provided.", file=sys.stderr)
        return 1

    result = post_tweet(text)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
