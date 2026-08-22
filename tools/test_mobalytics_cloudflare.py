#!/usr/bin/env python3
"""
Test Mobalytics / Cloudflare independently from Bot Marin.

This script deliberately does NOT import anything from the project. It uses one
persistent curl_cffi AsyncSession, lets curl_cffi provide the browser headers,
warms the session with a normal profile GET, then runs a small GraphQL query.

Examples:
    python tools/test_mobalytics_cloudflare.py "Game Name" "TAG"
    python tools/test_mobalytics_cloudflare.py "Game Name" "TAG" --match-id 1234567890
    python tools/test_mobalytics_cloudflare.py "Game Name" "TAG" --impersonate chrome

Dependency:
    pip install -U curl_cffi
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
from typing import Any
from urllib.parse import quote

import curl_cffi
from curl_cffi.requests import AsyncSession


GRAPHQL_URL = "https://mobalytics.gg/api/lol/graphql/v1/query"


QUEUES_QUERY = """
query LolPlayerQueuesStatsType($region: Region!, $gameName: String!, $tagLine: String!) {
  lol {
    player(region: $region, gameName: $gameName, tagLine: $tagLine) {
      queuesStats {
        items {
          __typename
          wins
          losses
          winrate
          gamesCount
          virtualQueue
        }
      }
    }
  }
}
"""


MATCH_QUERY = """
query LolMatchDetailsQuery($region: Region!, $gameName: String!, $tagLine: String!, $matchId: Int!) {
  lol {
    player(region: $region, gameName: $gameName, tagLine: $tagLine) {
      match(matchId: $matchId) {
        id
        seasonId
        queue
        startedAt
        duration
        patch
        teams {
          avgTier {
            tier
            division
          }
        }
        participants {
          gameName
          tagLine
          region
          championId
          championLevel
          team
          role
        }
      }
    }
  }
}
"""


def make_profile_url(game_name: str, tag_line: str, region: str) -> str:
    profile_slug = f"{game_name.lower()}-{tag_line.lower()}"
    safe_slug = quote(profile_slug, safe="")
    return f"https://mobalytics.gg/lol/profile/{region.lower()}/{safe_slug}/overview"


def cookie_names(session: AsyncSession) -> list[str]:
    """Return cookie names only; values are intentionally not printed."""
    try:
        return sorted(session.cookies.get_dict().keys())
    except Exception:
        return []


def looks_like_cloudflare_challenge(status_code: int, headers: Any, text: str) -> bool:
    body = (text or "").lower()
    cf_mitigated = str(headers.get("cf-mitigated", "")).lower()

    markers = (
        "just a moment",
        "cf-chl-",
        "challenge-platform",
        "verify you are human",
    )

    return (
        cf_mitigated == "challenge"
        or any(marker in body for marker in markers)
        or (status_code in {403, 429, 503} and "cloudflare" in body)
    )


def print_response_diagnostics(label: str, response: Any, session: AsyncSession) -> None:
    text = response.text or ""
    challenge = looks_like_cloudflare_challenge(
        response.status_code,
        response.headers,
        text,
    )

    print(f"\n=== {label} ===")
    print(f"HTTP status      : {response.status_code}")
    print(f"Content-Type     : {response.headers.get('content-type', '-')}")
    print(f"Server           : {response.headers.get('server', '-')}")
    print(f"CF-Ray           : {response.headers.get('cf-ray', '-')}")
    print(f"CF-Mitigated     : {response.headers.get('cf-mitigated', '-')}")
    print(f"Cloudflare check : {'CHALLENGE DETECTED' if challenge else 'no obvious challenge'}")
    print(f"Session cookies  : {cookie_names(session) or 'none'}")

    if challenge:
        compact = " ".join(text[:700].split())
        print(f"Response excerpt : {compact}")


def graphql_headers(operation_name: str, referer: str) -> dict[str, str]:
    # Do NOT set User-Agent / sec-ch-ua manually. curl_cffi's impersonation
    # should keep those headers coherent with its TLS/HTTP2 fingerprint.
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://mobalytics.gg",
        "referer": referer,
        "x-moba-client": "mobalytics-web",
        "x-moba-proxy-gql-ops-name": operation_name,
    }


async def graphql_post(
    session: AsyncSession,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
    referer: str,
    timeout: float,
) -> Any:
    payload = {
        "operationName": operation_name,
        "query": query,
        "variables": variables,
    }

    return await session.post(
        GRAPHQL_URL,
        headers=graphql_headers(operation_name, referer),
        json=payload,
        timeout=timeout,
    )


def print_graphql_result(response: Any) -> bool:
    """Print a compact GraphQL result. Return True when the query succeeded."""
    if looks_like_cloudflare_challenge(response.status_code, response.headers, response.text):
        return False

    content_type = (response.headers.get("content-type") or "").lower()
    if response.status_code >= 400:
        print(f"HTTP error body  : {' '.join((response.text or '')[:1000].split())}")
        return False

    if "json" not in content_type:
        print("Unexpected body  : response is not JSON")
        print(f"Body excerpt     : {' '.join((response.text or '')[:1000].split())}")
        return False

    try:
        data = response.json()
    except Exception as exc:
        print(f"JSON decode error: {exc}")
        return False

    if data.get("errors"):
        print("GraphQL errors:")
        print(json.dumps(data["errors"], ensure_ascii=False, indent=2)[:3000])
        return False

    print("GraphQL result   : OK")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
    return True


async def run(args: argparse.Namespace) -> int:
    region = args.region.upper()
    profile_url = make_profile_url(args.game_name, args.tag_line, region)

    print("Mobalytics standalone diagnostic")
    print("--------------------------------")
    print(f"Python           : {platform.python_version()}")
    print(f"curl_cffi        : {getattr(curl_cffi, '__version__', 'unknown')}")
    print(f"Impersonation    : {args.impersonate}")
    print(f"Region           : {region}")
    print(f"Riot ID          : {args.game_name}#{args.tag_line}")
    print(f"Profile URL      : {profile_url}")
    print(f"GraphQL endpoint : {GRAPHQL_URL}")

    try:
        async with AsyncSession(
            impersonate=args.impersonate,
            timeout=args.timeout,
        ) as session:
            if not args.skip_warmup:
                print("\n[1/2] Warming the persistent session with the public profile page...")
                warmup = await session.get(profile_url, timeout=args.timeout)
                print_response_diagnostics("PROFILE GET", warmup, session)
            else:
                print("\n[1/2] Profile warm-up skipped.")

            print("\n[2/2] Testing LolPlayerQueuesStatsType...")
            queues_response = await graphql_post(
                session=session,
                operation_name="LolPlayerQueuesStatsType",
                query=QUEUES_QUERY,
                variables={
                    "region": region,
                    "gameName": args.game_name,
                    "tagLine": args.tag_line,
                },
                referer=profile_url,
                timeout=args.timeout,
            )
            print_response_diagnostics("QUEUES GRAPHQL POST", queues_response, session)
            queues_ok = print_graphql_result(queues_response)

            match_ok = True
            if args.match_id is not None:
                print("\n[extra] Testing LolMatchDetailsQuery with the same session...")
                match_response = await graphql_post(
                    session=session,
                    operation_name="LolMatchDetailsQuery",
                    query=MATCH_QUERY,
                    variables={
                        "region": region,
                        "gameName": args.game_name,
                        "tagLine": args.tag_line,
                        "matchId": args.match_id,
                    },
                    referer=profile_url,
                    timeout=args.timeout,
                )
                print_response_diagnostics("MATCH GRAPHQL POST", match_response, session)
                match_ok = print_graphql_result(match_response)

            print("\n=== VERDICT ===")
            if queues_ok and match_ok:
                print("SUCCESS: Mobalytics GraphQL answered without an obvious Cloudflare challenge.")
                print("This validates the persistent-session + coherent curl_cffi impersonation approach.")
                return 0

            print("FAILED: at least one test did not return a usable GraphQL response.")
            print("Use the diagnostics above (HTTP status, CF-Ray, CF-Mitigated and body excerpt).")
            return 2

    except Exception as exc:
        print("\n=== CLIENT ERROR ===")
        print(f"{type(exc).__name__}: {exc}")
        return 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone Mobalytics / Cloudflare diagnostic using curl_cffi.",
    )
    parser.add_argument("game_name", help="Riot game name, quote it if it contains spaces")
    parser.add_argument("tag_line", help="Riot tag without #")
    parser.add_argument("--region", default="EUW", help="Mobalytics region (default: EUW)")
    parser.add_argument("--match-id", type=int, default=None, help="Optional match ID to test match details")
    parser.add_argument(
        "--impersonate",
        default="chrome",
        help='curl_cffi browser fingerprint (default: "chrome")',
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    parser.add_argument(
        "--skip-warmup",
        action="store_true",
        help="Skip the initial GET of the Mobalytics profile page",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        exit_code = 130

    sys.exit(exit_code)
