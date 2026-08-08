import requests
import json
import time
import os
from datetime import datetime

# ================= CẤU HÌNH =================
MIN_MCAP = 100_000_000       # Market cap tối thiểu: 50M
PAGES = 4                    # Lấy top 1250 coin (250 coin/page x 5 page)
OUTPUT_FILE = "whitelist.json"

# ================= HÀM XỬ LÝ =================

def fetch_coingecko_page(page: int) -> list:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": page,
        "sparkline": False
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(f"⚠️  Rate limit page {page}, chờ 60s...")
            time.sleep(60)
            return fetch_coingecko_page(page)  # Retry
        else:
            print(f"❌ Lỗi HTTP {r.status_code} tại page {page}")
            return []
    except Exception as e:
        print(f"❌ Exception tại page {page}: {e}")
        return []


def build_whitelist():
    print(f"🔄 Đang build whitelist (mcap > ${MIN_MCAP/1_000_000:.0f}M)...")
    
    whitelist = []
    total_checked = 0
    total_qualified = 0

    for page in range(1, PAGES + 1):
        print(f"  📄 Đang lấy page {page}/{PAGES}...")
        coins = fetch_coingecko_page(page)
        
        if not coins:
            print(f"  ⚠️  Page {page} trả về rỗng, dừng.")
            break

        for coin in coins:
            total_checked += 1
            mcap = coin.get("market_cap") or 0
            
            if mcap < MIN_MCAP:
                # Danh sách đã sort theo mcap desc, coin tiếp theo còn nhỏ hơn
                # Nhưng không break vì đôi khi CoinGecko có sắp xếp lệch
                continue
            
            symbol_binance = coin["symbol"].upper() + "USDT"
            whitelist.append(symbol_binance)
            total_qualified += 1

        # Delay tránh rate limit CoinGecko free tier
        time.sleep(2.5)

    # Ghi file
    output = {
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "min_mcap_usd": MIN_MCAP,
        "count": len(whitelist),
        "symbols": whitelist
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Hoàn tất!")
    print(f"   - Đã kiểm tra: {total_checked} coin")
    print(f"   - Đủ điều kiện mcap > ${MIN_MCAP/1_000_000:.0f}M: {total_qualified} coin")
    print(f"   - Đã lưu vào: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_whitelist()
