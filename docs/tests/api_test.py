"""API Test Suite for Face Check-in System — face.twosmallcats.asia"""
import requests
import json
import sys
from datetime import datetime

BASE = "http://120.27.120.99:8080"
RESULTS = []
FAILED = 0
PASSED = 0

def test(name, method, path, **kwargs):
    global PASSED, FAILED
    expected_status = kwargs.pop("expected", 200)
    is_binary = kwargs.pop("binary", False)
    url = BASE + path
    try:
        r = requests.request(method, url, timeout=10, **kwargs)
        if is_binary:
            if r.status_code == expected_status and len(r.content) > 0:
                RESULTS.append({"name": name, "status": "PASS", "code": r.status_code,
                                "detail": f"Binary: {len(r.content)} bytes, content-type: {r.headers.get('content-type','?')}"})
                PASSED += 1
            else:
                RESULTS.append({"name": name, "status": "FAIL", "code": r.status_code,
                                "detail": f"Expected {expected_status} with binary body, got {r.status_code}"})
                FAILED += 1
            return r, {}
        body = r.json() if r.text else {}
        if r.status_code == expected_status:
            RESULTS.append({"name": name, "status": "PASS", "code": r.status_code, "detail": ""})
            PASSED += 1
        else:
            RESULTS.append({"name": name, "status": "FAIL", "code": r.status_code,
                            "detail": f"Expected {expected_status}, got {r.status_code}: {body.get('detail', str(body)[:100])}"})
            FAILED += 1
        return r, body
    except Exception as e:
        RESULTS.append({"name": name, "status": "ERROR", "code": 0, "detail": str(e)})
        FAILED += 1
        return None, {"error": str(e)}

# ── 1. Health Check ──
print("=" * 60)
print("FACE CHECK-IN SYSTEM — API TEST SUITE")
print(f"Target: {BASE}")
print(f"Time: {datetime.now().isoformat()}")
print("=" * 60)

print("\n-- 1. Basic Checks --")
test("Health endpoint", "GET", "/api/health")

# ── 2. Auth ──
print("\n── 2. Authentication ──")
_, login_data = test("Admin login (valid)", "POST", "/api/auth/login",
                     json={"username": "admin", "password": "Test512"})
ADMIN_TOKEN = login_data.get("access_token", "")
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

test("Admin login (wrong password)", "POST", "/api/auth/login",
     json={"username": "admin", "password": "wrong"}, expected=401)

test("Admin login (missing fields)", "POST", "/api/auth/login",
     json={"username": "admin"}, expected=422)

_, student_data = test("Student login (valid)", "POST", "/api/auth/login",
                       json={"username": "zht", "password": "myhomework"})
STUDENT_TOKEN = student_data.get("access_token", "")
STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}

# ── 3. User Management ──
print("\n── 3. User Management (Admin) ──")
_, users = test("List all users", "GET", "/api/admin/users",
                headers=ADMIN_HEADERS)
test("List students only", "GET", "/api/admin/users?role=student",
     headers=ADMIN_HEADERS)

# ── 4. Location Management ──
print("\n── 4. Location Management (Admin) ──")
_, locs = test("List locations", "GET", "/api/admin/locations",
               headers=ADMIN_HEADERS)

# ── 5. Statistics & Dashboard ──
print("\n── 5. Statistics ──")
test("Get today statistics", "GET", "/api/admin/statistics",
     headers=ADMIN_HEADERS)

# ── 6. QR Code ──
print("\n── 6. QR Code Operations ──")
_, qr_data = test("Generate checkin QR", "POST", "/api/qr/generate",
                  headers=ADMIN_HEADERS,
                  json={"type": "checkin", "location_id": 1})
if qr_data.get("token"):
    test("Validate QR token", "GET", f"/api/qr/validate/{qr_data['token']}")

_, qr_co = test("Generate checkout QR", "POST", "/api/qr/generate",
                headers=ADMIN_HEADERS,
                json={"type": "checkout", "location_id": 1})

# ── 7. Session Management ──
print("\n── 7. Session Management (Admin) ──")
test("List active sessions", "GET", "/api/admin/sessions/active",
     headers=ADMIN_HEADERS)

# Create a session
_, sess_data = test("Create checkin session", "POST", "/api/admin/sessions",
                    headers=ADMIN_HEADERS,
                    json={
                        "location_id": 1,
                        "name": "TEST_AUTO_测试任务",
                        "start_date": "2026-06-01",
                        "end_date": "2026-12-31",
                        "checkin_start_time": "00:00",
                        "checkin_end_time": "23:59",
                        "recurring_days": "0,1,2,3,4,5,6",
                        "target_user_ids": "2"
                    })
SESSION_ID = sess_data.get("id")

if SESSION_ID:
    # Test duplicate name rejection
    test("Create session (duplicate name)", "POST", "/api/admin/sessions",
         headers=ADMIN_HEADERS,
         json={
             "location_id": 1,
             "name": "TEST_AUTO_测试任务",
             "checkin_start_time": "08:00",
             "checkin_end_time": "20:00",
         }, expected=400)

    # Test GET single session
    test("Get session detail", "GET", f"/api/admin/sessions/{SESSION_ID}",
         headers=ADMIN_HEADERS)

    # Test update session
    test("Update session", "PUT", f"/api/admin/sessions/{SESSION_ID}",
         headers=ADMIN_HEADERS,
         json={"name": "TEST_AUTO_测试任务_修改"})

    # Generate QR with session
    test("Generate QR with session", "POST", "/api/qr/generate",
         headers=ADMIN_HEADERS,
         json={"type": "checkin", "location_id": 1, "session_id": SESSION_ID})

    # Export session
    _, export = test("Export session Excel", "GET",
                     f"/api/admin/sessions/{SESSION_ID}/export",
                     headers=ADMIN_HEADERS, binary=True)

    # End session
    test("End session", "POST", f"/api/admin/sessions/{SESSION_ID}/end",
         headers=ADMIN_HEADERS)

# ── 8. Check-in Flow (Student) ──
print("\n── 8. Student Check-in Flow ──")
# Get check status
test("Check status", "GET", "/api/check/status?user_id=2")

# Get active sessions for student
test("Student active sessions", "GET", "/api/check/session/active",
     headers=STUDENT_HEADERS)

# ── 9. Records ──
print("\n── 9. Check-in Records ──")
test("List checkins (admin)", "GET", "/api/admin/checkins",
     headers=ADMIN_HEADERS)
test("List checkins (student own)", "GET", "/api/admin/checkins",
     headers=STUDENT_HEADERS)

# ── 10. Export ──
print("\n── 10. Export ──")
test("Export Excel (date)", "GET", "/api/admin/export?date=2026-06-20",
     headers=ADMIN_HEADERS, binary=True)
test("Export Excel (date range)", "GET",
     "/api/admin/export?date_from=2026-06-01&date_to=2026-06-20",
     headers=ADMIN_HEADERS, binary=True)

# ── 11. Location Validation ──
print("\n── 11. Location Validation ──")
test("Validate location", "POST", "/api/admin/validate-location",
     json={"lat": 36.547308, "lng": 116.83223, "location_id": 1})

# ── 12. Auth & Permission ──
print("\n── 12. Auth & Permission ──")
test("Access admin API without token", "GET", "/api/admin/users", expected=401)
test("Access admin API with student token", "GET", "/api/admin/users",
     headers=STUDENT_HEADERS, expected=403)

# ── Summary ──
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
total = PASSED + FAILED
print(f"Total: {total}  |  Passed: {PASSED}  |  Failed: {FAILED}")
print(f"Pass rate: {PASSED/total*100:.1f}%" if total > 0 else "No tests")
print()

for r in RESULTS:
    icon = "[OK]" if r['status'] == 'PASS' else "[FAIL]"
    print(f"  {icon} {r['name']} (HTTP {r['code']})")
    if r['detail']:
        print(f"       -> {r['detail']}")

print("\nReport data saved to D:\\test\\api_test_results.json")
with open(r"D:\test\api_test_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "test_time": datetime.now().isoformat(),
        "base_url": BASE,
        "total": total,
        "passed": PASSED,
        "failed": FAILED,
        "pass_rate": f"{PASSED/total*100:.1f}%" if total > 0 else "N/A",
        "results": RESULTS,
    }, f, ensure_ascii=False, indent=2)

print("Done.")
