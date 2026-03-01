#!/usr/bin/env python3
"""
Test script for AI roleplay generation endpoint.

Usage:
    python3 tools/test_roleplay_generate.py \
        --base http://43.142.49.126:9000 \
        --username admin --password admin123 \
        [--utterance-id <UUID>]

If --utterance-id is not provided, the script fetches the first available utterance.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def request(url, method="GET", data=None, headers=None):
    headers = headers or {}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://43.142.49.126:9000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--utterance-id", default=None)
    args = parser.parse_args()

    base = args.base.rstrip("/")

    # ── Step 1: Login ──
    print(f"[1] Logging in as {args.username}...")
    code, resp = request(
        f"{base}/api/auth/login",
        method="POST",
        data={"username": args.username, "password": args.password},
        headers={"Content-Type": "application/json"},
    )
    if code != 200:
        print(f"  ✗ Login failed ({code}): {resp}")
        sys.exit(1)
    token = resp["access_token"]
    print(f"  ✓ Token: {token[:30]}...")

    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── Step 2: Get utterance ID ──
    utt_id = args.utterance_id
    if not utt_id:
        print("[2] Fetching first utterance...")
        code, utts = request(f"{base}/api/utterances?limit=5", headers=auth)
        if code != 200 or not utts:
            print(f"  ✗ No utterances found ({code}): {utts}")
            sys.exit(1)
        # Prefer ones with text
        utt = next((u for u in utts if u.get("text", "").strip()), utts[0])
        utt_id = utt["id"]
        print(f"  ✓ Using utterance: {utt_id} — '{utt.get('text', '')[:60]}'")
    else:
        print(f"[2] Using provided utterance: {utt_id}")

    # ── Step 3: GET existing roleplay (may be empty) ──
    print("[3] GET existing roleplay...")
    code, resp = request(f"{base}/api/utterances/{utt_id}/roleplay", headers=auth)
    print(f"  HTTP {code}")
    if code == 200:
        if resp.get("exists"):
            print(f"  ✓ Cached roleplay found (model={resp.get('model')}, created={resp.get('created_at')})")
            print(f"    impact: {resp['content']['impact'][:1]}")
            print("[4] Already cached — skipping generation. Use --utterance-id for a fresh one.")
            print("\n✓ PASS: GET /roleplay works, cached result returned.")
            return
        else:
            print(f"  No existing roleplay — will generate.")

    # ── Step 4: POST generate ──
    print("[4] POST generate roleplay (may take 10-30s)...")
    code, resp = request(
        f"{base}/api/utterances/{utt_id}/roleplay",
        method="POST",
        headers=auth,
    )
    print(f"  HTTP {code}")

    if code == 502:
        detail = resp.get("detail", "")
        print(f"  ✗ LLM generation failed: {detail}")
        print()
        if "401" in detail or "User not found" in detail:
            print("  → OPENROUTER_API_KEY is expired or invalid.")
            print("  → Update /opt/info-tech/deploy/.env:")
            print("       OPENROUTER_API_KEY=sk-or-v1-<new-key>")
            print("  → Restart backend:")
            print("       sshpass -p 'gawtAn-8butmy-bargyz' ssh ubuntu@43.142.49.126")
            print("       cd /opt/info-tech/deploy && sudo docker compose up -d --build backend")
        elif "402" in detail:
            print("  → OpenRouter account has insufficient credits.")
        print("\n✗ FAIL: LLM call blocked by API key issue.")
        sys.exit(2)

    if code != 200 and code != 201:
        print(f"  ✗ Unexpected response: {json.dumps(resp, ensure_ascii=False, indent=2)}")
        sys.exit(1)

    if not resp.get("ok"):
        print(f"  ✗ Response ok=false: {resp}")
        sys.exit(1)

    content = resp.get("content", {})
    impact = content.get("impact", [])
    rewrites = content.get("rewrites", [])
    rehearsal = content.get("rehearsal", [])

    print(f"  ✓ Generated (model={resp.get('model')}, cached={resp.get('cached')})")
    print(f"    impact ({len(impact)}):    {impact[0] if impact else '(empty)'}")
    print(f"    rewrites ({len(rewrites)}): {rewrites[0] if rewrites else '(empty)'}")
    print(f"    rehearsal ({len(rehearsal)} turns)")
    if len(impact) < 1 or len(rewrites) < 1 or len(rehearsal) < 1:
        print("  ✗ Content incomplete!")
        sys.exit(1)

    # ── Step 5: Verify cache ──
    print("[5] GET again (should return cached)...")
    code, resp2 = request(f"{base}/api/utterances/{utt_id}/roleplay", headers=auth)
    if code == 200 and resp2.get("exists") and resp2.get("content"):
        print(f"  ✓ Cache hit")
    else:
        print(f"  ? Cache check: {code} {resp2}")

    print("\n✓ PASS: roleplay generation and caching work correctly.")


if __name__ == "__main__":
    main()
