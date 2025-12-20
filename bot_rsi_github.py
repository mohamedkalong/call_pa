import pandas as pd
import requests
import time
from datetime import datetime
import os

# ================= CẤU HÌNH (CONFIG) =================
# Thay đổi URL này thành URL Web App của bạn trên PA
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

TELEGRAM_BOT_TOKEN = "8219004391:AAEyCr89eR33w17-fikVUm3-xYnok1oahRY"
TELEGRAM_CHAT_ID = "5235344133"

TIMEFRAME = '1h'
LIMIT = 500            
RSI_PERIOD = 14
RSI_THRESHOLD = 70     
CHANGE_THRESHOLD = 20  

# ================= HÀM XỬ LÝ =================

def get_data_via_proxy(endpoint, params=None):
    """Lấy dữ liệu Binance thông qua Proxy PythonAnywhere"""
    url = f"{PA_PROXY_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"❌ Lỗi khi gọi Proxy: {e}")
    return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    # Wilder's Smoothing
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def main():
    print(f"📊 [GHA] Đang quét qua Proxy: Change > {CHANGE_THRESHOLD}% & RSI > {RSI_THRESHOLD}...")
    
    # 1. Lấy dữ liệu ticker từ Proxy
    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    # 2. Lọc coin > 20% Change
    filtered_tickers = [
        t for t in tickers 
        if t['symbol'].endswith('USDT') and float(t['priceChangePercent']) > CHANGE_THRESHOLD
    ]
    
    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin tiềm năng.")

    results = []

    # 3. Quét RSI
    for t in filtered_tickers:
        symbol = t['symbol']
        change_val = float(t['priceChangePercent'])
        
        # Gọi klines qua Proxy
        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)
        
        if klines and len(klines) >= LIMIT:
            closes = pd.Series([float(k[4]) for k in klines])
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            
            current_rsi = rsi_series.iloc[-1]
            current_price = closes.iloc[-1]

            if current_rsi > RSI_THRESHOLD:
                print(f"✅ Khớp: {symbol} (+{change_val}% | RSI: {current_rsi:.1f})")
                results.append({
                    's': symbol, 'r': current_rsi, 'p': current_price, 'c': change_val
                })
        
        time.sleep(0.5) # Nghỉ để tránh quá tải Web App PA

    # 4. Gửi Telegram
    now = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
    if results:
        results.sort(key=lambda x: x['c'], reverse=True)
        msg = f"🚀 **CẢNH BÁO: 24h CHANGE > {CHANGE_THRESHOLD}% & RSI > {RSI_THRESHOLD}**\n"
        msg += f"⏰ _Time: {now}_ (GitHub)\n\n"
        for index, item in enumerate(results, start=1):
            msg += f"{index}. #{item['s']} | **{item['p']}** | 24h: `+{item['c']}%` | RSI: `{item['r']:.1f}`\n"
    else:
        msg = f"ℹ️ **THÔNG BÁO QUÉT COIN**\n⏰ _Time: {now}_\n❌ Không có coin nào thỏa mãn."

    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
