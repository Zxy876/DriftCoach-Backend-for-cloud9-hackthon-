#!/usr/bin/env python3
"""
Diagnostic script to debug 400 errors from /api/coach/query

This script tests the API and provides detailed error messages.
"""

import sys
import json
import requests
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8000/api"
TEST_SERIES_ID = "2819676"  # Default series ID for testing


def print_section(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def test_health():
    """Test if the server is running."""
    print_section("1. Testing Server Health")

    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print("✅ Server is running")
            print(f"   Data source: {data.get('data_source')}")
            print(f"   Demo mode: {data.get('demo_mode')}")
            print(f"   Active sessions: {data.get('active_sessions', [])}")
            return True
        else:
            print(f"❌ Server returned status {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        print("   Start it with: python3 -m driftcoach.api")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_init(series_id: str):
    """Test session initialization."""
    print_section("2. Testing Session Initialization")

    try:
        payload = {"grid_series_id": series_id}
        print(f"   POST {API_BASE}/coach/init")
        print(f"   Payload: {json.dumps(payload, indent=2)}")

        resp = requests.post(
            f"{API_BASE}/coach/init",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            session_id = data.get("session_id")
            print(f"✅ Session initialized successfully")
            print(f"   Session ID: {session_id}")
            print(f"   Context loaded: {data.get('context_loaded')}")
            return session_id
        else:
            print(f"❌ Init failed with status {resp.status_code}")
            try:
                error = resp.json()
                print(f"   Error: {json.dumps(error, indent=2)}")
            except:
                print(f"   Response: {resp.text[:200]}")
            return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_query(session_id: str, query: str):
    """Test query endpoint."""
    print_section("3. Testing Query Endpoint")

    try:
        payload = {
            "coach_query": query,
            "session_id": session_id,
        }
        print(f"   POST {API_BASE}/coach/query")
        print(f"   Payload: {json.dumps(payload, indent=2)}")

        resp = requests.post(
            f"{API_BASE}/coach/query",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"   Status: {resp.status_code}")

        if resp.status_code == 200:
            print("✅ Query successful")
            data = resp.json()

            # Show key fields
            if "answer_synthesis" in data:
                ans = data["answer_synthesis"]
                print(f"   Claim: {ans.get('claim', 'N/A')}")
                print(f"   Verdict: {ans.get('verdict', 'N/A')}")
                print(f"   Confidence: {ans.get('confidence', 'N/A')}")
            return True
        else:
            print(f"❌ Query failed with status {resp.status_code}")
            try:
                error = resp.json()
                print(f"   Error details:")
                print(json.dumps(error, indent=2))
            except:
                print(f"   Response: {resp.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_without_session(query: str):
    """Test what happens when we query without a valid session."""
    print_section("4. Testing Query WITHOUT Valid Session (Expected to Fail)")

    try:
        payload = {
            "coach_query": query,
            "session_id": "invalid-session-id-12345",
        }
        print(f"   POST {API_BASE}/coach/query")
        print(f"   Payload: {json.dumps(payload, indent=2)}")

        resp = requests.post(
            f"{API_BASE}/coach/query",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"   Status: {resp.status_code}")

        if resp.status_code == 400:
            print("✅ Correctly returned 400 for invalid session")
            try:
                error = resp.json()
                print(f"   Error message: {error.get('detail', 'N/A')}")
            except:
                print(f"   Response: {resp.text[:200]}")
            return True
        else:
            print(f"❌ Expected 400, got {resp.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_empty_query():
    """Test what happens when we send an empty query."""
    print_section("5. Testing Empty Query (Expected to Fail)")

    try:
        payload = {
            "coach_query": "",  # Empty query
            "session_id": "any-session",
        }
        print(f"   POST {API_BASE}/coach/query")
        print(f"   Payload: {json.dumps(payload, indent=2)}")

        resp = requests.post(
            f"{API_BASE}/coach/query",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        print(f"   Status: {resp.status_code}")

        if resp.status_code == 400:
            print("✅ Correctly returned 400 for empty query")
            try:
                error = resp.json()
                print(f"   Error message: {error.get('detail', 'N/A')}")
            except:
                print(f"   Response: {resp.text[:200]}")
            return True
        else:
            print(f"⚠️  Expected 400, got {resp.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all diagnostic tests."""
    print("\n" + "="*60)
    print(" DriftCoach API Diagnostic Tool")
    print("="*60)
    print(f"\nTarget API: {API_BASE}")
    print(f"Test Series ID: {TEST_SERIES_ID}")

    results = []

    # Test 1: Server health
    if not test_health():
        print("\n❌ Server is not running. Please start it first:")
        print("   cd '/Users/zxydediannao/ DriftCoach Backend'")
        print("   python3 -m driftcoach.api")
        return 1

    results.append(("Server Health", True))

    # Test 2: Initialize session
    session_id = test_init(TEST_SERIES_ID)
    results.append(("Session Init", session_id is not None))

    if not session_id:
        print("\n❌ Cannot proceed without valid session")
        return 1

    # Test 3: Valid query
    test_query_result = test_query(session_id, "这场比赛风险高吗？")
    results.append(("Valid Query", test_query_result))

    # Test 4: Query without session (should fail)
    test_no_session_result = test_query_without_session("测试查询")
    results.append(("Query Without Session", test_no_session_result))

    # Test 5: Empty query (should fail)
    test_empty_result = test_empty_query()
    results.append(("Empty Query", test_empty_result))

    # Summary
    print_section("Summary")
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All diagnostic tests passed!")
        print("\nThe API is working correctly. If you're still seeing 400 errors,")
        print("check that:")
        print("1. Your frontend is sending the correct session_id")
        print("2. The session_id matches what was returned from /api/coach/init")
        print("3. The coach_query field is not empty")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
