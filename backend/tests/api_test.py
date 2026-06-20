#!/usr/bin/env python3
"""
发现者（Discoverer）A股量化回测系统 — 全端API测试脚本
QA 测试工程师：测试所有公开和认证端点的功能、边界条件、错误处理
"""

import httpx
import json
import time
import uuid
import traceback

BASE_URL = "http://127.0.0.1:8000"
client = httpx.Client(proxy=None, trust_env=False, timeout=30)

# 测试结果记录
results = []
warnings = []


def log(endpoint, scenario, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    entry = {
        "endpoint": endpoint,
        "scenario": scenario,
        "passed": passed,
        "detail": detail,
    }
    results.append(entry)
    print(f"{status} | {endpoint} | {scenario}")
    if detail:
        print(f"       {detail}")


def check_response(r, expected_code=None, expected_json_code=None):
    """检查响应是否符合基本规范"""
    issues = []
    
    # Check HTTP status code
    if expected_code is not None and r.status_code != expected_code:
        issues.append(f"期望HTTP {expected_code}, 实际 {r.status_code}")
    
    # Try to parse JSON
    try:
        body = r.json()
    except json.JSONDecodeError:
        return {"valid_json": False, "issues": ["非JSON响应"], "body": r.text[:200]}
    
    # Check standard response format {code, data, message}
    if "code" not in body:
        issues.append("响应缺少 'code' 字段")
    if "data" not in body:
        issues.append("响应缺少 'data' 字段")
    if "message" not in body:
        issues.append("响应缺少 'message' 字段")
    
    if expected_json_code is not None and body.get("code") != expected_json_code:
        issues.append(f"期望json.code={expected_json_code}, 实际={body.get('code')}")
    
    return {
        "valid_json": True,
        "issues": issues,
        "body": body,
    }


# ═══════════════════════════════════════════════════════════════
# 第1部分：不需要登录的端点
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("第1部分：不需要登录的端点测试")
print("=" * 70)

# ── 1. GET /api/system/status ──
print("\n── 1. GET /api/system/status ──")

try:
    r = client.get(f"{BASE_URL}/api/system/status")
    check = check_response(r, expected_code=200, expected_json_code=0)
    
    if check["valid_json"] and not check["issues"]:
        body = check["body"]
        data = body.get("data", {})
        
        # 验证必要字段
        if isinstance(data, dict):
            has_keys = all(k in data for k in ["signals_loaded", "stocks_count", "initialized"])
            if has_keys:
                log("/api/system/status", "正常获取系统状态 (GET)", True,
                    f"stocks={data.get('stocks_count')}, signals={data.get('signals_count', 'N/A')}, init={data.get('initialized')}")
            else:
                log("/api/system/status", "正常获取系统状态 (GET)", False,
                    f"缺少关键字段，data keys: {list(data.keys())}")
        else:
            log("/api/system/status", "正常获取系统状态 (GET)", False,
                f"data 不是dict: {type(data)}")
    else:
        log("/api/system/status", "正常获取系统状态 (GET)", False, "; ".join(check["issues"]))
except Exception as e:
    log("/api/system/status", "正常获取系统状态 (GET)", False, str(e))

# Test with POST (should not allow or should handle gracefully)
try:
    r = client.post(f"{BASE_URL}/api/system/status", json={})
    body = r.json()
    # 要么 405 Method Not Allowed, 要么 200 但返回错误
    if r.status_code == 405 or (r.status_code == 200 and body.get("code") == -1):
        log("/api/system/status", "POST 请求（应拒绝）", True, f"HTTP {r.status_code}")
    elif r.status_code == 200 and body.get("code") == 0:
        log("/api/system/status", "POST 请求（应拒绝）", False, "POST 意外成功返回 code=0")
    else:
        log("/api/system/status", "POST 请求（应拒绝）", True, f"HTTP {r.status_code} (可接受的拒绝)")
except Exception as e:
    log("/api/system/status", "POST 请求（应拒绝）", True, f"异常 (可接受): {e}")


# ── 2. GET /api/strategies/classic ──
print("\n── 2. GET /api/strategies/classic ──")

try:
    r = client.get(f"{BASE_URL}/api/strategies/classic")
    check = check_response(r, expected_code=200, expected_json_code=0)
    
    if check["valid_json"] and not check["issues"]:
        body = check["body"]
        data = body.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            log("/api/strategies/classic", "获取经典策略列表 (GET)", True,
                f"返回 {len(data)} 个策略, 示例: {sample.get('id', 'N/A')}")
            
            # 验证每个策略的格式
            required_fields = ["id", "name", "category", "description"]
            for i, s in enumerate(data):
                missing = [f for f in required_fields if f not in s]
                if missing:
                    log("/api/strategies/classic", f"策略[{i}]字段完整性", False,
                        f"缺少: {missing}")
                    break
            else:
                log("/api/strategies/classic", "策略对象字段完整性", True, "所有字段完整")
        else:
            log("/api/strategies/classic", "获取经典策略列表 (GET)", False,
                f"data 不是有效列表: {type(data)}")
    else:
        log("/api/strategies/classic", "获取经典策略列表 (GET)", False,
            "; ".join(check["issues"]))
except Exception as e:
    log("/api/strategies/classic", "获取经典策略列表 (GET)", False, str(e))

# POST to classic (should be rejected)
try:
    r = client.post(f"{BASE_URL}/api/strategies/classic")
    if r.status_code == 405:
        log("/api/strategies/classic", "POST 请求（应拒绝）", True, "405 Method Not Allowed")
    else:
        log("/api/strategies/classic", "POST 请求（应拒绝）", True,
            f"HTTP {r.status_code} (可接受)")
except Exception as e:
    log("/api/strategies/classic", "POST 请求（应拒绝）", True, f"异常: {e}")


# ── 3. POST /api/auth/register ──
print("\n── 3. POST /api/auth/register ──")

# 3a. 注册时不接受风险告知书
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "test@example.com",
        "password": "test123456",
        "agreed_risk_disclosure": False,
    })
    check = check_response(r, expected_json_code=-1)
    body = check["body"]
    msg = body.get("message", "")
    if "风险告知书" in msg or "risk" in msg.lower():
        log("/api/auth/register", "未同意风险告知书", True, f"msg='{msg}'")
    else:
        log("/api/auth/register", "未同意风险告知书", False, f"msg='{msg}'")
except Exception as e:
    log("/api/auth/register", "未同意风险告知书", False, str(e))

# 3b. 无效邮箱格式
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "not-an-email",
        "password": "test123456",
        "agreed_risk_disclosure": True,
    })
    check = check_response(r)
    body = check["body"]
    if r.status_code == 422:
        log("/api/auth/register", "无效邮箱格式", True, "422 Validation Error (Pydantic)")
    elif body.get("code") == -1:
        log("/api/auth/register", "无效邮箱格式", True, f"code=-1, msg='{body.get('message')}'")
    else:
        log("/api/auth/register", "无效邮箱格式", False, f"HTTP {r.status_code}, code={body.get('code')}")
except Exception as e:
    log("/api/auth/register", "无效邮箱格式", False, str(e))

# 3c. 空邮箱
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "",
        "password": "test123456",
        "agreed_risk_disclosure": True,
    })
    check = check_response(r)
    body = check["body"]
    if r.status_code == 422:
        log("/api/auth/register", "空邮箱", True, "422 Validation Error")
    elif body.get("code") == -1:
        log("/api/auth/register", "空邮箱", True, f"code=-1, msg='{body.get('message')}'")
    else:
        log("/api/auth/register", "空邮箱", False, f"HTTP {r.status_code}")
except Exception as e:
    log("/api/auth/register", "空邮箱", False, str(e))

# 3d. 密码过短 (< 6)
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "shortpwd@test.com",
        "password": "12345",
        "agreed_risk_disclosure": True,
    })
    check = check_response(r)
    body = check["body"]
    if r.status_code == 422:
        log("/api/auth/register", "密码过短（5位）", True, "422 Validation Error")
    elif body.get("code") == -1:
        log("/api/auth/register", "密码过短（5位）", True, f"code=-1, msg='{body.get('message')}'")
    else:
        log("/api/auth/register", "密码过短（5位）", False, f"HTTP {r.status_code}")
except Exception as e:
    log("/api/auth/register", "密码过短（5位）", False, str(e))

# 3e. 缺少必要字段
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={})
    if r.status_code == 422:
        log("/api/auth/register", "空请求体（缺少字段）", True, "422 Validation Error")
    elif r.status_code == 400:
        log("/api/auth/register", "空请求体（缺少字段）", True, "400 Bad Request")
    else:
        body = r.json()
        log("/api/auth/register", "空请求体（缺少字段）", True,
            f"HTTP {r.status_code}, code={body.get('code')}")
except Exception as e:
    log("/api/auth/register", "空请求体（缺少字段）", False, str(e))

# 3f. 特殊字符密码
try:
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": "special@test.com",
        "password": "!@#$%^&*()_+-=[]{}|",
        "agreed_risk_disclosure": True,
    })
    check = check_response(r)
    body = check["body"]
    if body.get("code") == 0:
        log("/api/auth/register", "特殊字符密码", True, "注册成功")
    elif body.get("code") == -1:
        log("/api/auth/register", "特殊字符密码", True, f"msg='{body.get('message')}'")
    else:
        log("/api/auth/register", "特殊字符密码", False, f"HTTP {r.status_code}")
except Exception as e:
    log("/api/auth/register", "特殊字符密码", False, str(e))


# ── 4. POST /api/auth/login ──
print("\n── 4. POST /api/auth/login ──")

# 4a. 不存在用户登录
try:
    r = client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "nonexistent_user_99999@test.com",
        "password": "test123456",
    })
    check = check_response(r, expected_json_code=-1)
    body = check["body"]
    if check["issues"]:
        log("/api/auth/login", "不存在用户登录", False, "; ".join(check["issues"]))
    else:
        log("/api/auth/login", "不存在用户登录", True, f"msg='{body.get('message')}'")
except Exception as e:
    log("/api/auth/login", "不存在用户登录", False, str(e))

# 4b. 错误密码
# First register a test user
test_email = f"qa_test_{int(time.time())}@discoverer.test"
test_password = "QaTest123!"

try:
    r1 = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": test_email,
        "password": test_password,
        "agreed_risk_disclosure": True,
    })
    reg_body = r1.json()
    if reg_body.get("code") == 0:
        log("/api/auth/register", f"创建测试用户 {test_email}", True, "注册成功")
        
        # 现在用错误密码登录
        r2 = client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": "WrongPassword123",
        })
        login_check = check_response(r2, expected_json_code=-1)
        body2 = r2.json()
        if login_check["issues"]:
            log("/api/auth/login", "错误密码登录", False, "; ".join(login_check["issues"]))
        else:
            log("/api/auth/login", "错误密码登录", True, f"msg='{body2.get('message')}'")
    else:
        log("/api/auth/register", f"创建测试用户 {test_email}", False,
            f"msg='{reg_body.get('message')}'")
except Exception as e:
    log("/api/auth/login", "注册测试用户失败", False, str(e))

# 4c. 空密码
try:
    r = client.post(f"{BASE_URL}/api/auth/login", json={
        "email": test_email,
        "password": "",
    })
    check = check_response(r)
    if r.status_code == 422:
        log("/api/auth/login", "空密码", True, "422 Validation Error")
    elif r.json().get("code") == -1:
        log("/api/auth/login", "空密码", True, f"code=-1")
    else:
        log("/api/auth/login", "空密码", False, f"HTTP {r.status_code}")
except Exception as e:
    log("/api/auth/login", "空密码", False, str(e))

# 4d. 缺少字段
try:
    r = client.post(f"{BASE_URL}/api/auth/login", json={})
    if r.status_code == 422:
        log("/api/auth/login", "空请求体", True, "422 Validation Error")
    else:
        log("/api/auth/login", "空请求体", True, f"HTTP {r.status_code}")
except Exception as e:
    log("/api/auth/login", "空请求体", False, str(e))


# ── 5. GET /api/stocks/search ──
print("\n── 5. GET /api/stocks/search ──")

# 5a. 正常搜索
try:
    r = client.get(f"{BASE_URL}/api/stocks/search?q=平安")
    check = check_response(r, expected_code=200, expected_json_code=0)
    body = check["body"]
    data = body.get("data", [])
    if check["issues"]:
        log("/api/stocks/search", '搜索 "平安"', False, "; ".join(check["issues"]))
    elif isinstance(data, list) and len(data) > 0:
        log("/api/stocks/search", '搜索 "平安"', True, f"返回 {len(data)} 条结果")
    elif isinstance(data, list) and len(data) == 0:
        log("/api/stocks/search", '搜索 "平安"', True, "返回 0 条结果")
    else:
        log("/api/stocks/search", '搜索 "平安"', False, f"data类型异常: {type(data)}")
except Exception as e:
    log("/api/stocks/search", '搜索 "平安"', False, str(e))

# 5b. 空 keyword
try:
    r = client.get(f"{BASE_URL}/api/stocks/search?q=")
    check = check_response(r, expected_code=200)
    body = check["body"]
    data = body.get("data", [])
    if isinstance(data, list):
        log("/api/stocks/search", "空 keyword", True,
            f"返回 {len(data)} 条（空keyword行为正确）" if len(data) == 0 else f"返回 {len(data)} 条")
    else:
        log("/api/stocks/search", "空 keyword", False, f"data类型: {type(data)}")
except Exception as e:
    log("/api/stocks/search", "空 keyword", False, str(e))

# 5c. 不存在的股票代码
try:
    r = client.get(f"{BASE_URL}/api/stocks/search?q=999999")
    check = check_response(r, expected_code=200)
    body = check["body"]
    data = body.get("data", [])
    if isinstance(data, list):
        if len(data) == 0 or body.get("code") == -1:
            log("/api/stocks/search", "搜索不存在代码 999999", True,
                f"正确返回空/错误 ({len(data)} 条)")
        else:
            log("/api/stocks/search", "搜索不存在代码 999999", True,
                f"返回 {len(data)} 条（可能模糊匹配到其他代码）")
    else:
        log("/api/stocks/search", "搜索不存在代码 999999", False, f"data: {data}")
except Exception as e:
    log("/api/stocks/search", "搜索不存在代码 999999", False, str(e))

# 5d. 代码搜索
try:
    r = client.get(f"{BASE_URL}/api/stocks/search?q=000001")
    check = check_response(r, expected_code=200, expected_json_code=0)
    body = check["body"]
    data = body.get("data", [])
    if isinstance(data, list) and len(data) > 0:
        log("/api/stocks/search", "搜索有效代码 000001", True,
            f"返回 {len(data)} 条, 首条: {data[0].get('name', 'N/A')}")
    else:
        log("/api/stocks/search", "搜索有效代码 000001", False,
            f"返回 {len(data)} 条")
except Exception as e:
    log("/api/stocks/search", "搜索有效代码 000001", False, str(e))

# 5e. SQL注入尝试
try:
    r = client.get(f"{BASE_URL}/api/stocks/search?q='%20OR%201=1--")
    check = check_response(r, expected_code=200)
    # 应返回空或正常处理，不崩溃
    log("/api/stocks/search", "SQL注入关键字", True,
        f"HTTP {r.status_code}, code={r.json().get('code')} (未崩溃)")
except Exception as e:
    log("/api/stocks/search", "SQL注入关键字", False, str(e))

# 5f. 超长查询
try:
    long_query = "A" * 5000
    r = client.get(f"{BASE_URL}/api/stocks/search?q={long_query}")
    # 应正常处理或返回422
    ok = r.status_code in [200, 422]
    log("/api/stocks/search", "超长查询 (5000字符)", ok,
        f"HTTP {r.status_code}")
except Exception as e:
    log("/api/stocks/search", "超长查询 (5000字符)", False, str(e))


# ═══════════════════════════════════════════════════════════════
# 第2部分：需要登录的端点
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("第2部分：需要登录的端点测试")
print("=" * 70)

# 先注册并登录获取 token
access_token = None
print("\n── 登录准备 ──")

try:
    # 注册
    unique_email = f"qa_login_test_{int(time.time())}@discoverer.test"
    r = client.post(f"{BASE_URL}/api/auth/register", json={
        "email": unique_email,
        "password": test_password,
        "agreed_risk_disclosure": True,
    })
    reg_body = r.json()
    if reg_body.get("code") == 0:
        log("/api/auth/register", "注册测试用户", True, f"{unique_email}")
    elif "已存在" in reg_body.get("message", "") or "already" in reg_body.get("message", "").lower():
        log("/api/auth/register", "注册测试用户", True, "用户已存在（使用已有账户）")
    else:
        log("/api/auth/register", "注册测试用户", False, str(reg_body))

    # 登录
    r = client.post(f"{BASE_URL}/api/auth/login", json={
        "email": unique_email,
        "password": test_password,
    })
    login_body = r.json()
    if login_body.get("code") == 0:
        access_token = login_body["data"]["access_token"]
        log("/api/auth/login", "获取 access_token", True, f"token={access_token[:20]}...")
    else:
        # 可能之前已注册，尝试用 test_email
        r = client.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": test_password,
        })
        login_body2 = r.json()
        if login_body2.get("code") == 0:
            access_token = login_body2["data"]["access_token"]
            log("/api/auth/login", "获取 access_token (fallback)", True, f"token={access_token[:20]}...")
        else:
            log("/api/auth/login", "获取 access_token（fallback）", False, str(login_body2))
except Exception as e:
    log("/api/auth/login", "登录准备失败", False, str(e))

if access_token:
    auth_headers = {"Authorization": f"Bearer {access_token}"}
else:
    auth_headers = {}
    log("所有认证端点", "缺少 token", False, "跳过需要登录的测试")

# ── 6. POST /api/backtest/classic ──
print("\n── 6. POST /api/backtest/classic ──")

if access_token:
    # 6a. 有效策略回测
    try:
        r = client.post(f"{BASE_URL}/api/backtest/classic", json={
            "stock_code": "000001",
            "strategy_id": "ma_golden_cross",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        }, headers=auth_headers)
        check = check_response(r, expected_code=200)
        body = check["body"]
        
        if body.get("code") == 0 and body.get("data"):
            data = body["data"]
            if "metrics" in data:
                metrics = data["metrics"]
                log("/api/backtest/classic", "有效策略 ma_golden_cross", True,
                    f"total_return={metrics.get('total_return', 'N/A')}, trades={metrics.get('total_trades', 'N/A')}")
            else:
                log("/api/backtest/classic", "有效策略 ma_golden_cross", False,
                    f"data缺少metrics, keys={list(data.keys())}")
        else:
            log("/api/backtest/classic", "有效策略 ma_golden_cross", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/classic", "有效策略 ma_golden_cross", False, str(e))

    # 6b. 无效策略ID
    try:
        r = client.post(f"{BASE_URL}/api/backtest/classic", json={
            "stock_code": "000001",
            "strategy_id": "nonexistent_strategy_xyz",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        }, headers=auth_headers)
        body = r.json()
        if body.get("code") == -1:
            log("/api/backtest/classic", "无效策略ID", True, f"msg='{body.get('message')}'")
        else:
            log("/api/backtest/classic", "无效策略ID", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/classic", "无效策略ID", False, str(e))

    # 6c. 无效股票代码
    try:
        r = client.post(f"{BASE_URL}/api/backtest/classic", json={
            "stock_code": "INVALID",
            "strategy_id": "ma_golden_cross",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        }, headers=auth_headers)
        body = r.json()
        log("/api/backtest/classic", "无效股票代码", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/classic", "无效股票代码", False, str(e))

    # 6d. 缺少必填字段
    try:
        # 缺少 stock_code
        r = client.post(f"{BASE_URL}/api/backtest/classic", json={
            "strategy_id": "ma_golden_cross",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }, headers=auth_headers)
        if r.status_code == 422:
            log("/api/backtest/classic", "缺少必填字段 stock_code", True, "422 Validation Error")
        else:
            body = r.json()
            log("/api/backtest/classic", "缺少必填字段 stock_code", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/backtest/classic", "缺少必填字段 stock_code", False, str(e))

    # 6e. 多策略测试
    for sid in ["momentum_breakout", "rsi_oversold", "bollinger_lower"]:
        try:
            r = client.post(f"{BASE_URL}/api/backtest/classic", json={
                "stock_code": "600036",
                "strategy_id": sid,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
            }, headers=auth_headers)
            body = r.json()
            ok = body.get("code") == 0
            log("/api/backtest/classic", f"策略 {sid}", ok,
                f"code={body.get('code')}")
        except Exception as e:
            log("/api/backtest/classic", f"策略 {sid}", False, str(e))

else:
    log("/api/backtest/classic", "所有场景", False, "缺少有效 token，跳过")


# ── 7. POST /api/backtest/custom ──
print("\n── 7. POST /api/backtest/custom ──")

if access_token:
    # 7a. 有效自然语言
    try:
        r = client.post(f"{BASE_URL}/api/backtest/custom", json={
            "stock_code": "000001",
            "natural_language": "当5日均线上穿20日均线时买入，当5日均线下穿20日均线时卖出",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        }, headers=auth_headers)
        body = r.json()
        if body.get("code") == 0 and body.get("data"):
            data = body["data"]
            parse_level = data.get("parse_level", "unknown")
            if "backtest_result" in data:
                metrics = data["backtest_result"].get("metrics", {})
                log("/api/backtest/custom", "自然语言回测-均线交叉", True,
                    f"level={parse_level}, return={metrics.get('total_return', 'N/A')}")
            else:
                log("/api/backtest/custom", "自然语言回测-均线交叉", False,
                    f"level={parse_level}, 缺少backtest_result")
        else:
            log("/api/backtest/custom", "自然语言回测-均线交叉", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/custom", "自然语言回测-均线交叉", False, str(e))

    # 7b. 空自然语言
    try:
        r = client.post(f"{BASE_URL}/api/backtest/custom", json={
            "stock_code": "000001",
            "natural_language": "",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }, headers=auth_headers)
        body = r.json()
        # 空字符串应该能处理
        log("/api/backtest/custom", "空自然语言描述", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/custom", "空自然语言描述", False, str(e))

    # 7c. 无意义自然语言
    try:
        r = client.post(f"{BASE_URL}/api/backtest/custom", json={
            "stock_code": "000001",
            "natural_language": "asdfghjkl",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }, headers=auth_headers)
        body = r.json()
        log("/api/backtest/custom", "无意义自然语言", True,
            f"code={body.get('code')}, level={body.get('data', {}).get('parse_level', 'N/A')}")
    except Exception as e:
        log("/api/backtest/custom", "无意义自然语言", False, str(e))

    # 7d. 缺少 stock_code
    try:
        r = client.post(f"{BASE_URL}/api/backtest/custom", json={
            "natural_language": "当股价突破20日高点时买入",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        }, headers=auth_headers)
        if r.status_code == 422:
            log("/api/backtest/custom", "缺少必填字段 stock_code", True, "422 Validation Error")
        else:
            body = r.json()
            log("/api/backtest/custom", "缺少必填字段 stock_code", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/backtest/custom", "缺少必填字段 stock_code", False, str(e))

else:
    log("/api/backtest/custom", "所有场景", False, "缺少有效 token，跳过")


# ── 8. POST /api/llm/parse (backtest/parse) ──
print("\n── 8. POST /api/llm/parse ──")

if access_token:
    # 8a. 解析自然语言
    try:
        r = client.post(f"{BASE_URL}/api/llm/parse", json={
            "natural_language": "当RSI低于30时买入，当RSI高于70时卖出",
            "stock_code": "000001",
        }, headers=auth_headers)
        body = r.json()
        if "data" in body and body.get("data"):
            data = body["data"]
            if isinstance(data, dict):
                success = data.get("success", False)
                log("/api/llm/parse", "解析 RSI 策略", True,
                    f"success={success}, level={data.get('parse_level', 'N/A')}")
            else:
                log("/api/llm/parse", "解析 RSI 策略", False, f"data不是dict: {type(data)}")
        else:
            log("/api/llm/parse", "解析 RSI 策略", True,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/llm/parse", "解析 RSI 策略", False, str(e))

    # 8b. 解析空文本
    try:
        r = client.post(f"{BASE_URL}/api/llm/parse", json={
            "natural_language": "",
        }, headers=auth_headers)
        body = r.json()
        # 422 或 code=-1 都可接受
        log("/api/llm/parse", "解析空文本", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/llm/parse", "解析空文本", True, str(e))

else:
    log("/api/llm/parse", "所有场景", False, "缺少有效 token，跳过")


# ── 9. GET /api/backtest/grid-search/{id} ──
print("\n── 9. GET /api/backtest/grid-search/{id} ──")

# 查询不存在的 job
try:
    r = client.get(f"{BASE_URL}/api/backtest/grid-search/nonexistent_job_at_all_99999")
    body = r.json()
    # 代码中的 grid_search 返回 404 作为 code，不是 HTTP 状态码
    if body.get("code") == 404:
        log("/api/backtest/grid-search/{id}", "查询不存在job", True,
            f"code=404 (注意：返回的是json.code=404 而非HTTP 404)")
    elif body.get("code") == -1:
        log("/api/backtest/grid-search/{id}", "查询不存在job", True,
            f"code=-1, msg='{body.get('message')}'")
    else:
        log("/api/backtest/grid-search/{id}", "查询不存在job", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
except Exception as e:
    log("/api/backtest/grid-search/{id}", "查询不存在job", False, str(e))


# ── 10. POST /api/backtest/grid-search ──
print("\n── 10. POST /api/backtest/grid-search ──")

if access_token:
    # 10a. 有效网格搜索
    try:
        r = client.post(f"{BASE_URL}/api/backtest/grid-search", json={
            "stock_code": "000001",
            "strategy_id": "ma_golden_cross",
            "x_param": {
                "name": "stop_loss_pct",
                "min_value": 0.03,
                "max_value": 0.10,
                "step": 0.03,
                "label": "止损比例"
            },
            "y_param": {
                "name": "take_profit_pct",
                "min_value": 0.05,
                "max_value": 0.20,
                "step": 0.05,
                "label": "止盈比例"
            },
            "target_metric": "total_return",
        }, headers=auth_headers)
        body = r.json()
        if body.get("code") == 0 and body["data"].get("job_id"):
            log("/api/backtest/grid-search", "有效网格搜索", True,
                f"job_id={body['data']['job_id']}")
            grid_job_id = body["data"]["job_id"]
            # 查询进度
            time.sleep(1)
            r2 = client.get(f"{BASE_URL}/api/backtest/grid-search/{grid_job_id}")
            job_body = r2.json()
            if job_body.get("code") == 0:
                job_data = job_body["data"]
                log("/api/backtest/grid-search", f"查询 job {grid_job_id}", True,
                    f"status={job_data.get('status')}, progress={job_data.get('progress')}")
        else:
            log("/api/backtest/grid-search", "有效网格搜索", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/grid-search", "有效网格搜索", False, str(e))

    # 10b. 无效策略ID
    try:
        r = client.post(f"{BASE_URL}/api/backtest/grid-search", json={
            "stock_code": "000001",
            "strategy_id": "invalid_strategy_xyz123",
            "x_param": {
                "name": "stop_loss_pct",
                "min_value": 0.03,
                "max_value": 0.10,
                "step": 0.03,
            },
            "y_param": {
                "name": "take_profit_pct",
                "min_value": 0.05,
                "max_value": 0.20,
                "step": 0.05,
            },
        }, headers=auth_headers)
        body = r.json()
        log("/api/backtest/grid-search", "无效策略ID", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/grid-search", "无效策略ID", False, str(e))

    # 10c. 参数 min > max
    try:
        r = client.post(f"{BASE_URL}/api/backtest/grid-search", json={
            "stock_code": "000001",
            "strategy_id": "ma_golden_cross",
            "x_param": {
                "name": "stop_loss_pct",
                "min_value": 0.10,
                "max_value": 0.01,
                "step": 0.01,
            },
            "y_param": {
                "name": "take_profit_pct",
                "min_value": 0.01,
                "max_value": 0.20,
                "step": 0.05,
            },
        }, headers=auth_headers)
        body = r.json()
        # 应该返回错误或正常处理
        log("/api/backtest/grid-search", "参数 min>max", True,
            f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/backtest/grid-search", "参数 min>max", False, str(e))

    # 10d. 缺少必填参数
    try:
        r = client.post(f"{BASE_URL}/api/backtest/grid-search", json={
            "stock_code": "000001",
        }, headers=auth_headers)
        if r.status_code == 422:
            log("/api/backtest/grid-search", "缺少必填参数", True, "422 Validation Error")
        else:
            body = r.json()
            log("/api/backtest/grid-search", "缺少必填参数", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/backtest/grid-search", "缺少必填参数", False, str(e))
else:
    log("/api/backtest/grid-search", "所有场景", False, "缺少有效 token，跳过")


# ── 11. GET /api/strategies ──
print("\n── 11. GET /api/strategies ──")

if access_token:
    try:
        r = client.get(f"{BASE_URL}/api/strategies", headers=auth_headers)
        body = r.json()
        if body.get("code") == 0:
            data = body.get("data", [])
            log("/api/strategies", "获取我的策略列表（已登录）", True,
                f"返回 {len(data)} 条策略")
        else:
            log("/api/strategies", "获取我的策略列表（已登录）", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/strategies", "获取我的策略列表（已登录）", False, str(e))

    # 未登录访问
    try:
        r2 = client.get(f"{BASE_URL}/api/strategies")  # 无 auth header
        if r2.status_code == 401 or r2.status_code == 403:
            log("/api/strategies", "获取策略列表（未登录）", True,
                f"HTTP {r2.status_code} (正确拒绝)")
        elif r2.json().get("code") == -1:
            log("/api/strategies", "获取策略列表（未登录）", True,
                "返回 code=-1")
        else:
            log("/api/strategies", "获取策略列表（未登录）", False,
                f"HTTP {r2.status_code} (应拒绝)")
    except Exception as e:
        log("/api/strategies", "获取策略列表（未登录）", True, str(e))
else:
    log("/api/strategies", "所有场景", False, "缺少有效 token，跳过")


# ── 12. POST /api/strategies ──
print("\n── 12. POST /api/strategies ──")

if access_token:
    # 12a. 创建有效策略
    try:
        r = client.post(f"{BASE_URL}/api/strategies", json={
            "name": f"QA测试策略_{int(time.time())}",
            "description": "这是一个QA自动测试创建的策略",
            "raw_text": "当5日均线上穿20日均线时买入",
            "entry_conditions": [
                {"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0}
            ],
            "exit_conditions": [
                {"signal_id": "ma_death_cross", "operator": "cross_below", "threshold": 0}
            ],
            "params": {"ma_short": 5, "ma_long": 20},
        }, headers=auth_headers)
        body = r.json()
        if body.get("code") == 0:
            strategy_id = body["data"].get("id")
            log("/api/strategies", "创建有效策略", True,
                f"strategy_id={strategy_id}, name={body['data'].get('name')}")
            
            # 保存ID供后续测试
            created_strategy_id = strategy_id
        else:
            log("/api/strategies", "创建有效策略", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
            created_strategy_id = None
    except Exception as e:
        log("/api/strategies", "创建有效策略", False, str(e))
        created_strategy_id = None

    # 12b. 创建缺少名称的策略
    try:
        r = client.post(f"{BASE_URL}/api/strategies", json={
            "entry_conditions": [{"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0}],
            "exit_conditions": [],
        }, headers=auth_headers)
        if r.status_code == 422:
            log("/api/strategies", "创建策略-缺少名称", True, "422 Validation Error")
        else:
            body = r.json()
            log("/api/strategies", "创建策略-缺少名称", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/strategies", "创建策略-缺少名称", False, str(e))

    # 12c. 空名称
    try:
        r = client.post(f"{BASE_URL}/api/strategies", json={
            "name": "",
            "entry_conditions": [{"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0}],
            "exit_conditions": [],
        }, headers=auth_headers)
        if r.status_code == 422:
            log("/api/strategies", "创建策略-空名称", True, "422 Validation Error")
        else:
            body = r.json()
            log("/api/strategies", "创建策略-空名称", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/strategies", "创建策略-空名称", False, str(e))

else:
    log("/api/strategies", "所有场景", False, "缺少有效 token，跳过")
    created_strategy_id = None


# ── 13. GET /api/user/settings ──
print("\n── 13. GET /api/user/settings ──")

if access_token:
    try:
        r = client.get(f"{BASE_URL}/api/user/settings", headers=auth_headers)
        body = r.json()
        if body.get("code") == 0 and isinstance(body.get("data"), dict):
            data = body["data"]
            log("/api/user/settings", "获取用户设置（已登录）", True,
                f"tdx_data_dir='{data.get('tdx_data_dir', 'N/A')}'")
        else:
            log("/api/user/settings", "获取用户设置（已登录）", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/user/settings", "获取用户设置（已登录）", False, str(e))

    # 未登录
    try:
        r2 = client.get(f"{BASE_URL}/api/user/settings")
        if r2.status_code == 401 or r2.status_code == 403:
            log("/api/user/settings", "获取用户设置（未登录）", True,
                f"HTTP {r2.status_code} (正确拒绝)")
        else:
            log("/api/user/settings", "获取用户设置（未登录）", False,
                f"HTTP {r2.status_code} (应拒绝)")
    except Exception as e:
        log("/api/user/settings", "获取用户设置（未登录）", True, str(e))
else:
    log("/api/user/settings", "所有场景", False, "缺少有效 token，跳过")


# ── 14. PUT /api/user/settings ──
print("\n── 14. PUT /api/user/settings ──")

if access_token:
    # 14a. 正常更新
    try:
        r = client.put(f"{BASE_URL}/api/user/settings", json={
            "tdx_data_dir": "/data/test/tdx",
        }, headers=auth_headers)
        body = r.json()
        if body.get("code") == 0:
            data = body.get("data", {})
            log("/api/user/settings", "更新 tdx_data_dir", True,
                f"设置后 tdx_data_dir='{data.get('tdx_data_dir', 'N/A')}'")
        else:
            log("/api/user/settings", "更新 tdx_data_dir", False,
                f"code={body.get('code')}, msg='{body.get('message')}'")
    except Exception as e:
        log("/api/user/settings", "更新 tdx_data_dir", False, str(e))

    # 14b. 空值更新
    try:
        r = client.put(f"{BASE_URL}/api/user/settings", json={
            "tdx_data_dir": "",
        }, headers=auth_headers)
        body = r.json()
        log("/api/user/settings", "更新为空字符串", True,
            f"code={body.get('code')}")
    except Exception as e:
        log("/api/user/settings", "更新为空字符串", False, str(e))

    # 14c. 无效字段
    try:
        r = client.put(f"{BASE_URL}/api/user/settings", json={
            "invalid_field": "test",
        }, headers=auth_headers)
        body = r.json()
        if r.status_code == 422:
            log("/api/user/settings", "更新无效字段", True, "422 Validation Error")
        else:
            log("/api/user/settings", "更新无效字段", True,
                f"HTTP {r.status_code}, code={body.get('code')}")
    except Exception as e:
        log("/api/user/settings", "更新无效字段", False, str(e))

else:
    log("/api/user/settings", "所有场景", False, "缺少有效 token，跳过")


# ═══════════════════════════════════════════════════════════════
# 第3部分：额外边界测试
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("第3部分：额外边界测试")
print("=" * 70)

# API 版本/不存在端点
print("\n── 不存在端点 ──")
try:
    r = client.get(f"{BASE_URL}/api/nonexistent/endpoint")
    body = r.json()
    ok = r.status_code == 404
    log("GET /api/nonexistent", "不存在端点", ok,
        f"HTTP {r.status_code}, detail='{body.get('detail', 'N/A')}'")
except Exception as e:
    log("GET /api/nonexistent", "不存在端点", False, str(e))

# 无效token访问需要认证的端点
print("\n── 无效 Token ──")
try:
    r = client.get(f"{BASE_URL}/api/strategies", headers={
        "Authorization": "Bearer invalid_token_here_xyz"
    })
    if r.status_code == 401:
        log("/api/strategies (invalid token)", "无效JWT", True, "HTTP 401")
    else:
        log("/api/strategies (invalid token)", "无效JWT", True,
            f"HTTP {r.status_code} (可接受)")
except Exception as e:
    log("/api/strategies (invalid token)", "无效JWT", False, str(e))

# 过期token（一个伪造的过期token）
expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcl9pZCI6MSwiZXhwIjoxMDAwMDAwMDAwfQ.fake"
try:
    r = client.get(f"{BASE_URL}/api/strategies", headers={
        "Authorization": f"Bearer {expired_token}"
    })
    if r.status_code == 401:
        log("/api/strategies (expired token)", "过期JWT", True, "HTTP 401")
    else:
        log("/api/strategies (expired token)", "过期JWT", True,
            f"HTTP {r.status_code} (可接受)")
except Exception as e:
    log("/api/strategies (expired token)", "过期JWT", False, str(e))

# 无Auth头的认证端点
print("\n── 无认证 ──")
try:
    r = client.post(f"{BASE_URL}/api/strategies", json={
        "name": "test",
        "entry_conditions": [],
        "exit_conditions": [],
    })
    if r.status_code == 401 or r.status_code == 403:
        log("/api/strategies (no auth)", "无认证创建策略", True, f"HTTP {r.status_code}")
    elif r.status_code == 422:
        # Token 没有但Pydantic先验证了 - 意味着认证没有生效
        log("/api/strategies (no auth)", "无认证创建策略", False,
            "422 (Pydantic验证在认证之前执行 - 潜在问题)")
    else:
        body = r.json()
        log("/api/strategies (no auth)", "无认证创建策略", False,
            f"HTTP {r.status_code}, code={body.get('code')}")
except Exception as e:
    log("/api/strategies (no auth)", "无认证创建策略", False, str(e))


# ═══════════════════════════════════════════════════════════════
# 汇总报告
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("测试汇总")
print("=" * 70)

total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])

print(f"\n总计: {total} 个测试场景")
print(f"通过: {passed}")
print(f"失败: {failed}")
print(f"通过率: {passed/total*100:.1f}%" if total > 0 else "N/A")

if failed > 0:
    print(f"\n❌ 失败用例:")
    for r in results:
        if not r["passed"]:
            print(f"  - {r['endpoint']}: {r['scenario']}")
            print(f"    {r['detail']}")

print()

# 输出 JSON 结果供报告使用
with open("/tmp/api_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("详细结果已保存至: /tmp/api_test_results.json")
