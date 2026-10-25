#!/usr/bin/env python
"""Publish tweets directly via Twitter API v2 using OAuth 1.0a.

Zero external dependencies - uses standard library urllib, hmac, hashlib.
Works seamlessly in GitHub Actions, cloud servers, or local scripts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_FILE = ROOT / "secrets.json"


def get_credentials() -> dict[str, str]:
    """Load credentials from environment variables or secrets.json."""
    creds = {
        "consumer_key": os.getenv("TWITTER_CONSUMER_KEY", "").strip(),
        "consumer_secret": os.getenv("TWITTER_CONSUMER_SECRET", "").strip(),
        "access_token": os.getenv("TWITTER_ACCESS_TOKEN", "").strip(),
        "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "").strip(),
    }

    if not all(creds.values()) and SECRETS_FILE.exists():
        try:
            saved = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
            for k in creds:
                if not creds[k]:
                    creds[k] = saved.get(k, "").strip()
        except Exception as e:
            print(f"Warning: could not read {SECRETS_FILE}: {e}", file=sys.stderr)

    missing = [k for k, v in creds.items() if not v]
    if missing:
        raise ValueError(
            f"Missing Twitter API credentials: {', '.join(missing)}.\n"
            f"Set them in environment variables or {SECRETS_FILE}."
        )

    return creds


def pct_encode(s: str) -> str:
    """OAuth 1.0 percent-encode conforming to RFC 5849."""
    return urllib.parse.quote(str(s), safe="")


def build_oauth1_header(
    method: str,
    url: str,
    creds: dict[str, str],
    extra_params: dict[str, str] | None = None,
) -> str:
    """Generate OAuth 1.0a Authorization header."""
    params = {
        "oauth_consumer_key": creds["consumer_key"],
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    if extra_params:
        params.update(extra_params)

    # 1. Normalize and sort parameters
    sorted_pairs = sorted(
        (pct_encode(k), pct_encode(v)) for k, v in params.items()
    )
    param_str = "&".join(f"{k}={v}" for k, v in sorted_pairs)

    # 2. Build signature base string
    base_url = url.split("?")[0]
    base_str = f"{method.upper()}&{pct_encode(base_url)}&{pct_encode(param_str)}"

    # 3. Create signing key
    signing_key = f"{pct_encode(creds['consumer_secret'])}&{pct_encode(creds['access_token_secret'])}"

    # 4. Generate HMAC-SHA1 signature
    hashed = hmac.new(
        signing_key.encode("utf-8"),
        base_str.encode("utf-8"),
        hashlib.sha1,
    )
    signature = base64.b64encode(hashed.digest()).decode("utf-8")
    params["oauth_signature"] = signature

    # 5. Format Authorization header
    auth_header_parts = [
        f'{pct_encode(k)}="{pct_encode(v)}"'
        for k, v in sorted(params.items())
        if k.startswith("oauth_")
    ]
    return "OAuth " + ", ".join(auth_header_parts)


def post_tweet(text: str) -> dict:
    """Post a tweet using Twitter API v2 endpoint."""
    url = "https://api.twitter.com/2/tweets"
    creds = get_credentials()

    payload = json.dumps({"text": text}).encode("utf-8")
    auth_header = build_oauth1_header("POST", url, creds)

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "User-Agent": "TweetyTweets/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tweet_id = data.get("data", {}).get("id")
            tweet_url = f"https://x.com/i/status/{tweet_id}" if tweet_id else None
            return {
                "ok": True,
                "id": tweet_id,
                "tweet_url": tweet_url,
                "text": text,
                "response": data,
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status_code": e.code,
            "error": err_body,
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
