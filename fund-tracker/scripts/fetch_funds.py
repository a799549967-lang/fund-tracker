#!/usr/bin/env python3
"""
Fetch fund data from Eastmoney APIs.
Runs server-side in GitHub Actions - no CORS issues.
Reads fund codes from data/holdings.json, writes to data/funds.json
"""

import json
import os
import re
import time
import requests
from datetime import datetime, timezone, timedelta

# CST timezone
CST = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Referer": "https://fund.eastmoney.com/",
}

def fetch_valuation(code):
    """Fetch real-time estimate (估值) from fundmobapi."""
    url = f"https://fundmobapi.eastmoney.com/FundMApi/FundVarietieValuationDetail.ashx?FCODE={code}&deviceid=Wap&plat=Wap&product=EFund&version=2.0.0"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("Data") and data["Data"].get("GZ"):
            d = data["Data"]
            return {
                "name": d.get("SHORTNAME", ""),
                "dwjz": float(d.get("JZ") or 0),
                "gsz":  float(d.get("GZ") or 0),
                "gszzl": float(d.get("GSZZL") or 0),
                "jzrq": (d.get("GZTIME") or "").split(" ")[0],
                "gztime": d.get("GZTIME", ""),
            }
    except Exception as e:
        print(f"  [valuation] {code} failed: {e}")
    return None

def fetch_fundgz(code):
    """Fallback: fetch from fundgz.1234567.com.cn JSONP."""
    url = f"https://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time())}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        m = re.search(r"jsonpgz\((.*)\)", r.text)
        if m:
            return json.loads(m.group(1))
    except Exception as e:
        print(f"  [fundgz] {code} failed: {e}")
    return None

def fetch_history(code, per=30):
    """Fetch NAV history from F10DataApi."""
    url = f"https://fundf10.eastmoney.com/F10DataApi.aspx?type=lsjz&code={code}&page=1&per={per}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        text = r.text

        # Extract content string
        m = re.search(r'content:"([\s\S]*?)",\s*records:', text)
        if not m:
            m = re.search(r'content:"([\s\S]*?)"', text)
        if not m:
            return []

        content = m.group(1)
        content = content.replace('\\"', '"').replace('\\t', '\t').replace('\\n', '\n').replace('\\r', '\r')

        rows = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', content)
        result = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row)
            if len(tds) >= 4:
                def clean(s):
                    return re.sub(r'<[^>]+>', '', s).replace('&nbsp;', '').strip()
                date = clean(tds[0])
                nav_s = clean(tds[1])
                # Find change % in remaining tds
                chg = ""
                for td in tds[2:]:
                    v = clean(td)
                    if "%" in v or re.match(r'^[+-]?\d+\.\d+$', v):
                        chg = v
                        if "%" in v:
                            break
                try:
                    nav = float(nav_s)
                    chg_val = float(chg.replace("%","")) if chg else 0.0
                    if date and nav:
                        result.append({"date": date, "nav": nav, "chg": chg_val})
                except:
                    pass
        return result
    except Exception as e:
        print(f"  [history] {code} failed: {e}")
    return []

def fetch_fund_info(code):
    """Fetch basic fund info from jbgk page."""
    url = f"https://fundf10.eastmoney.com/jbgk_{code}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        html = r.text

        def get_field(key):
            pattern = rf'<th>[^<]*{re.escape(key)}[^<]*</th>\s*<td[^>]*>([\s\S]*?)(?=</td>|<th>|</tr>)'
            m = re.search(pattern, html)
            if m:
                v = re.sub(r'<[^>]+>', '', m.group(1)).replace('&nbsp;', ' ').strip()
                return v if v and v != '---' else None
            return None

        name = get_field('基金简称') or get_field('基金全称')
        return {
            "name": name,
            "fundType": get_field('基金类型'),
            "manager": get_field('基金经理人'),
            "company": get_field('基金管理人'),
            "manageFee": get_field('管理费率'),
            "assetSize": get_field('资产规模') or get_field('净资产规模'),
        }
    except Exception as e:
        print(f"  [info] {code} failed: {e}")
    return {}

def main():
    # Read holdings to get codes
    holdings_path = "data/holdings.json"
    if not os.path.exists(holdings_path):
        print("No holdings.json found, creating empty one.")
        os.makedirs("data", exist_ok=True)
        with open(holdings_path, "w") as f:
            json.dump([], f)
        return

    with open(holdings_path) as f:
        holdings = json.load(f)

    codes = list(dict.fromkeys(h["code"] for h in holdings if h.get("code")))
    if not codes:
        print("No fund codes found in holdings.json")
        return

    print(f"Fetching data for {len(codes)} funds: {codes}")

    # Load existing funds data to preserve info cache
    funds_path = "data/funds.json"
    existing = {}
    if os.path.exists(funds_path):
        try:
            with open(funds_path) as f:
                existing = json.load(f)
        except:
            pass

    now_cst = datetime.now(CST)
    is_trading = (
        now_cst.weekday() < 5 and
        (
            (9 * 60 + 30 <= now_cst.hour * 60 + now_cst.minute <= 11 * 60 + 30) or
            (13 * 60 <= now_cst.hour * 60 + now_cst.minute <= 15 * 60)
        )
    )
    print(f"CST time: {now_cst.strftime('%Y-%m-%d %H:%M')}, trading: {is_trading}")

    funds = {}
    for code in codes:
        print(f"\nProcessing {code}...")
        prev = existing.get(code, {})
        entry = {
            "code": code,
            "name": prev.get("name", code),
            "nav": prev.get("nav", 0),
            "navDate": prev.get("navDate", ""),
            "change": prev.get("change", 0),
            "estNav": prev.get("estNav", 0),
            "estChg": prev.get("estChg", 0),
            "hasEst": False,
            "info": prev.get("info", {}),
            "history": prev.get("history", []),
            "updatedAt": now_cst.isoformat(),
        }

        # 1. Try valuation API (has estimate + name)
        val = fetch_valuation(code)
        if val:
            print(f"  valuation OK: {val.get('name')} nav={val.get('dwjz')} gsz={val.get('gsz')}")
            if val.get("name"):
                entry["name"] = val["name"]
            if val.get("dwjz", 0) > 0:
                entry["nav"] = val["dwjz"]
                entry["navDate"] = val.get("jzrq", "")
            if val.get("gsz", 0) > 0:
                entry["estNav"] = val["gsz"]
                entry["estChg"] = val.get("gszzl", 0)
                entry["hasEst"] = True
        else:
            # 2. Fallback to fundgz
            gz = fetch_fundgz(code)
            if gz:
                print(f"  fundgz OK: {gz}")
                if gz.get("name"):
                    entry["name"] = gz["name"]
                if float(gz.get("dwjz") or 0) > 0:
                    entry["nav"] = float(gz["dwjz"])
                    entry["navDate"] = gz.get("jzrq", "")
                if float(gz.get("gsz") or 0) > 0:
                    entry["estNav"] = float(gz["gsz"])
                    entry["estChg"] = float(gz.get("gszzl") or 0)
                    entry["hasEst"] = True

        # Fall back estNav to nav if no estimate
        if not entry["estNav"]:
            entry["estNav"] = entry["nav"]
            entry["estChg"] = entry["change"]

        # 3. Fetch history (always, to get change %)
        hist = fetch_history(code, 30)
        if hist:
            print(f"  history OK: {len(hist)} records")
            entry["history"] = hist
            if not entry["nav"] and hist:
                entry["nav"] = hist[0]["nav"]
                entry["navDate"] = hist[0]["date"]
            if len(hist) >= 1:
                entry["change"] = hist[0]["chg"]
            if not entry["hasEst"]:
                entry["estNav"] = entry["nav"]
                entry["estChg"] = entry["change"]

        # 4. Fetch info (only if missing or once a week)
        info_age = 0
        if prev.get("infoFetchedAt"):
            try:
                fetched = datetime.fromisoformat(prev["infoFetchedAt"])
                info_age = (now_cst - fetched).total_seconds() / 3600
            except:
                pass
        if not entry["info"].get("fundType") or info_age > 168:
            info = fetch_fund_info(code)
            if info:
                print(f"  info OK: {info.get('name')} type={info.get('fundType')}")
                entry["info"] = info
                entry["infoFetchedAt"] = now_cst.isoformat()
                if info.get("name") and entry["name"] == code:
                    entry["name"] = info["name"]

        funds[code] = entry
        time.sleep(0.3)  # be polite

    # Write output
    output = {
        "updatedAt": now_cst.isoformat(),
        "updatedAtTs": int(now_cst.timestamp()),
        "funds": funds,
    }
    os.makedirs("data", exist_ok=True)
    with open(funds_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {funds_path} with {len(funds)} funds.")

if __name__ == "__main__":
    main()
