import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os

# ================= CẤU HÌNH (CONFIG) =================
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

TELEGRAM_BOT_TOKEN = os.environ.get("TELE_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELE_CHATID")

# --- CẤU HÌNH ĐIỀU KIỆN LỌC ---
TIMEFRAME = '1h'
LIMIT = 500            
RSI_PERIOD = 14

# 3 ĐIỀU KIỆN CHÍNH:
CHANGE_THRESHOLD = 20         # 1. Change > 20%
VOLUME_THRESHOLD = 40_000_000 # 2. Volume 
RSI_THRESHOLD = 70            # 3. RSI > 70

# ================= HÀM XỬ LÝ =================

def get_data_via_proxy(endpoint, params=None):
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
    ma_up = up.ewm(com=period-1, adjust=False).mean()
    ma_down = down.ewm(com=period-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def format_volume(vol):
    if vol >= 1_000_000_000:
        return f"{vol/1_000_000_000:.2f}B"
    elif vol >= 1_000_000:
        return f"{vol/1_000_000:.0f}M"
    return f"{vol/1_000:.0f}K"

def main():
    print(f"📊 [GHA] Đang quét: Change > {CHANGE_THRESHOLD}%, Vol > {format_volume(VOLUME_THRESHOLD)}, RSI > {RSI_THRESHOLD}...")
    
    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    filtered_tickers = []
    for t in tickers:
        if not t['symbol'].endswith('USDT'):
            continue
        
        change_percent = float(t['priceChangePercent'])
        quote_vol = float(t['quoteVolume'])
        
        if change_percent > CHANGE_THRESHOLD and quote_vol > VOLUME_THRESHOLD:
            filtered_tickers.append(t)
    
    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin thỏa mãn Vol & Change.")

    results = []

    for t in filtered_tickers:
        symbol = t['symbol']
        change_val = float(t['priceChangePercent'])
        quote_vol = float(t['quoteVolume'])
        price = float(t['lastPrice'])
        
        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)
        
        if klines and len(klines) >= LIMIT:
            closes = pd.Series([float(k[4]) for k in klines])
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            current_rsi = rsi_series.iloc[-1]

            if current_rsi > RSI_THRESHOLD:
                print(f"✅ Khớp: {symbol} (RSI: {current_rsi:.1f})")
                results.append({
                    's': symbol, 
                    'r': current_rsi, 
                    'p': price, 
                    'c': change_val,
                    'v': quote_vol
                })
        
        time.sleep(0.5)

    now_vn = datetime.utcnow() + timedelta(hours=7)
    now_str = now_vn.strftime("%d-%m-%Y, %H:%M")
    
    if results:
        results.sort(key=lambda x: x['r'], reverse=True)

        msg = f"🚀 **LỌC COIN 24H +{CHANGE_THRESHOLD}% & VOL> {format_volume(VOLUME_THRESHOLD)} & RSI> {RSI_THRESHOLD}**\n"
        msg += f"  ⏰ Time: {now_str}. (github)\n\n"
        
        for index, item in enumerate(results, start=1):
            vol_str = format_volume(item['v'])
            
            # --- THÊM TAG CHO RSI >= 80 ---
            rsi_tag = " 💎 rsi8x "  if item['r'] >= 80 else ""
            
            # Format: 1. #COIN | price | 24h x% | RSI x | Vol 50M #RSI80Plus
            msg += f"{index}. **#{item['s']}**|{item['p']}|+{item['c']}%|RSI:{item['r']:.1f}|Vol:{vol_str}{rsi_tag}\n"
    else:
        msg = f"ℹ️ **BOT REPORT**\n⏰ {now_str}\n✅ System OK.\n❌ Không tìm thấy coin thỏa 3 điều kiện."

    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo lúc {now_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
