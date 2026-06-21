# -*- coding: utf-8 -*-
"""Security Test Suite for Face Check-in System"""
import requests
import urllib.parse

BASE = "http://120.27.120.99:8080"
RESULTS = []
PASSED = 0
FAILED = 0

def sec_test(name, method, path, **kwargs):
    global PASSED, FAILED
    expected = kwargs.pop("expected", None)
    check = kwargs.pop("check", None)
    url = BASE + path
    try:
        r = requests.request(method, url, timeout=10, **kwargs)
        status = "PASS"
        detail = f"HTTP {r.status_code}"
        body = r.text[:500]

        if check == "not_500":
            if r.status_code >= 500:
                status = "FAIL"
                detail += " | SERVER ERROR (500+)"
        elif check == "no_stacktrace":
            if any(kw in body.lower() for kw in ["traceback", "sqlalchemy", "sqlite3.", 'file "', "line "]):
                status = "FAIL"
                detail += " | STACK TRACE LEAKED"
        elif check == "not_200":
            if r.status_code == 200:
                status = "FAIL"
                detail += " | Should NOT return 200"
        elif expected is not None:
            if r.status_code != expected:
                status = "FAIL"
                detail += " | Expected " + str(expected)

        if status == "PASS":
            PASSED += 1
        else:
            FAILED += 1
        RESULTS.append({"name": name, "status": status, "code": r.status_code, "detail": detail})
        print("  [OK] " + name + " (" + detail + ")" if status == "PASS" else "  [FAIL] " + name + " (" + detail + ")")
    except Exception as e:
        FAILED += 1
        RESULTS.append({"name": name, "status": "ERROR", "code": 0, "detail": str(e)})
        print("  [ERROR] " + name + ": " + str(e))

print("=" * 65)
print("FACE CHECK-IN -- SECURITY TEST")
print("Target: " + BASE)
print("=" * 65)

# 1. SQL Injection
print("\n-- 1. SQL Injection --")
sql_tests = [
    ("' OR '1'='1", "Basic OR injection"),
    ("'; DROP TABLE users; --", "Drop table injection"),
    ("1' UNION SELECT * FROM users --", "UNION injection"),
    ("admin'--", "Comment injection"),
    ("1 OR 1=1", "Numeric OR injection"),
]

for payload, desc in sql_tests:
    sec_test("SQLi Login: " + desc, "POST", "/api/auth/login",
             json={"username": payload, "password": "test"}, check="not_500")
    encoded = urllib.parse.quote(payload)
    sec_test("SQLi Param: " + desc, "GET",
             "/api/admin/users?role=" + encoded, check="not_500")
    sec_test("SQLi Status: " + desc, "GET",
             "/api/check/status?user_id=" + urllib.parse.quote(payload), check="not_500")

# 2. XSS Attack Vectors
print("\n-- 2. XSS Attack Vectors --")
xss_tests = [
    ("<script>alert(1)</script>", "Basic script tag"),
    ("<img src=x onerror=alert(1)>", "IMG onerror"),
    ("<svg onload=alert(1)>", "SVG onload"),
    ("<body onload=alert(1)>", "Body onload"),
    ("<iframe src=javascript:alert(1)>", "iframe javascript"),
]

for payload, desc in xss_tests:
    sec_test("XSS Login: " + desc, "POST", "/api/auth/login",
             json={"username": payload, "password": "test"}, check="not_500")
    sec_test("XSS Param: " + desc, "GET",
             "/api/admin/users?name=" + urllib.parse.quote(payload), check="not_500")

# 3. Authentication Bypass
print("\n-- 3. Authentication Bypass --")
sec_test("No Auth Header", "GET", "/api/admin/users", check="not_200")
sec_test("Empty Token", "GET", "/api/admin/users",
         headers={"Authorization": "Bearer "}, check="not_200")
sec_test("Fake Token", "GET", "/api/admin/users",
         headers={"Authorization": "Bearer fake.jwt.token.here"}, check="not_200")
sec_test("Malformed Header", "GET", "/api/admin/users",
         headers={"Authorization": "NotBearer xyz"}, check="not_200")
sec_test("JWT Tamper: student to admin", "GET", "/api/admin/users",
         headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwicm9sZSI6ImFkbWluIiwiZXhwIjo5OTk5OTk5OTk5fQ.abc"},
         check="not_200")

# 4. Path Traversal
print("\n-- 4. Path Traversal --")
paths = ["../../etc/passwd", "/etc/passwd", "....//....//....//etc/passwd"]
for p in paths:
    sec_test("Path Traversal: " + p, "GET", "/static/" + p, check="not_500")
    sec_test("Path Traversal QR: " + p, "GET", "/api/qr/image/" + p, check="not_500")

# 5. Rate Limiting
print("\n-- 5. Rate Limiting / Brute Force --")
print("  Sending 20 rapid failed login attempts...")
limited = False
for i in range(20):
    try:
        r = requests.post(BASE + "/api/auth/login",
                         json={"username": "admin", "password": "wrong" + str(i)}, timeout=5)
        if r.status_code == 429:
            print("  [INFO] Rate limiting active after " + str(i+1) + " attempts (HTTP 429)")
            limited = True
            break
    except:
        pass
if not limited:
    print("  [INFO] No rate limiting (all 20 attempts accepted)")

# 6. Sensitive Data Exposure
print("\n-- 6. Sensitive Data Exposure --")
sec_test("No stacktrace on 404", "GET", "/api/nonexistent", check="no_stacktrace")
sec_test("No stacktrace on bad id", "GET", "/api/admin/users/99999", check="no_stacktrace")
r = requests.get(BASE + "/api/health", timeout=5)
body = r.text.lower()
leaked = "password" in body or "secret" in body or "key" in body
print("  [" + ("FAIL" if leaked else "OK") + "] Health endpoint: " + ("LEAKED" if leaked else "clean"))

# 7. Input Validation
print("\n-- 7. Input Validation (Boundary) --")
sec_test("Long username 10000 chars", "POST", "/api/auth/login",
         json={"username": "A" * 10000, "password": "test"}, check="not_500")
sec_test("Negative user_id", "GET", "/api/check/status?user_id=-1", check="not_500")

# Summary
print("\n" + "=" * 65)
print("SECURITY TEST SUMMARY")
print("=" * 65)
total = PASSED + FAILED
print("Total: " + str(total) + "  |  Passed: " + str(PASSED) + "  |  Failed: " + str(FAILED))
if total > 0:
    print("Pass rate: " + str(round(PASSED/total*100, 1)) + "%")

fails = [r for r in RESULTS if r['status'] != 'PASS']
if fails:
    print("\nFailed/Error tests (" + str(len(fails)) + "):")
    for r in fails:
        print("  - " + r['name'] + ": " + r['detail'])
else:
    print("\nAll security tests passed. No vulnerabilities found.")

import json
with open(r"D:\test\security_results.json", "w", encoding="utf-8") as f:
    json.dump({"total": total, "passed": PASSED, "failed": FAILED, "results": RESULTS},
              f, ensure_ascii=False, indent=2)
print("\nResults saved to D:\\test\\security_results.json")
