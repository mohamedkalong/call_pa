import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os

# ================= CẤU HÌNH (CONFIG) =================
# Thay đổi URL này thành URL Web App của bạn trên PA
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

# Lấy Token từ GitHub Secrets
#TELEGRAM_BOT_TOKEN = "8219004391:AAEyCr89eR33w17-fikVUm3-xYnok1oahRY"
#TELEGRAM_CHAT_ID = "-1003618825373"
#TELEGRAM_BOT_TOKEN = os.environ.get("TELE_TOKEN")
#TELEGRAM_CHAT_ID = os.environ.get("TELE_CHATID")


# --- CẤU HÌNH ĐIỀU KIỆN LỌC ---
TIMEFRAME = '1h'
LIMIT = 500            
RSI_PERIOD = 14

# 3 ĐIỀU KIỆN CHÍNH:
CHANGE_THRESHOLD = 20         # 1. Change > 20%
VOLUME_THRESHOLD = 50_000_000 # 2. Volume > 50 Triệu USDT
RSI_THRESHOLD = 70            # 3. RSI > 70

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

def format_volume(vol):
    """Làm gọn số Volume: 50000000 -> 50M"""
    if vol >= 1_000_000_000:
        return f"{vol/1_000_000_000:.2f}B" # Tỷ (Billion)
    elif vol >= 1_000_000:
        return f"{vol/1_000_000:.0f}M"    # Triệu (Million) - Lấy số chẵn
    return f"{vol/1_000:.0f}K"

def main():
    print(f"📊 [GHA] Đang quét: Change > {CHANGE_THRESHOLD}%, Vol > {format_volume(VOLUME_THRESHOLD)}, RSI > {RSI_THRESHOLD}...")
    
    # 1. Lấy dữ liệu ticker từ Proxy
    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    # 2. Lọc sơ bộ: Coin có Change > 20% VÀ Volume > 50M
    # Lọc ngay bước này để đỡ tốn thời gian tính RSI cho coin rác
    filtered_tickers = []
    for t in tickers:
        if not t['symbol'].endswith('USDT'):
            continue
        
        change_percent = float(t['priceChangePercent'])
        quote_vol = float(t['quoteVolume']) # Volume theo USDT
        
        if change_percent > CHANGE_THRESHOLD and quote_vol > VOLUME_THRESHOLD:
            filtered_tickers.append(t)
    
    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin thỏa mãn Vol & Change.")

    results = []

    # 3. Quét RSI cho danh sách đã lọc
    for t in filtered_tickers:
        symbol = t['symbol']
        change_val = float(t['priceChangePercent'])
        quote_vol = float(t['quoteVolume'])
        price = float(t['lastPrice'])
        
        # Gọi klines qua Proxy để tính RSI
        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)
        
        if klines and len(klines) >= LIMIT:
            closes = pd.Series([float(k[4]) for k in klines])
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            
            current_rsi = rsi_series.iloc[-1]

            # Kiểm tra điều kiện RSI > 70
            if current_rsi > RSI_THRESHOLD:
                print(f"✅ Khớp: {symbol} (RSI: {current_rsi:.1f})")
                results.append({
                    's': symbol, 
                    'r': current_rsi, 
                    'p': price, 
                    'c': change_val,
                    'v': quote_vol
                })
        
        time.sleep(0.5) # Nghỉ để tránh quá tải Web App PA

    # 4. Gửi Telegram
    # GitHub Server chạy UTC, cộng thêm 7 giờ để ra giờ Việt Nam
    now_vn = datetime.utcnow() + timedelta(hours=7)
    now_str = now_vn.strftime("%d-%m-%Y, %H:%M")
    
    if results:
        # Sắp xếp ưu tiên RSI cao nhất lên đầu (hoặc đổi thành x['c'] nếu muốn xếp theo Change)
        results.sort(key=lambda x: x['r'], reverse=True)

        msg = f"🚀 **LỌC COIN 24H +{CHANGE_THRESHOLD}% & VOL> {format_volume(VOLUME_THRESHOLD)} & RSI> {RSI_THRESHOLD}**\n"
        msg += f"  ⏰ Time: {now_str}. (github)\n\n"
        
        for index, item in enumerate(results, start=1):
            vol_str = format_volume(item['v'])
            # Format: 1. #COIN | price |24h x% | RSI x | Vol 50M
            msg += f"{index}. **#{item['s']}** |{item['p']} |24h: +{item['c']}% |RSI: {item['r']:.1f} |Vol: {vol_str}\n"
    else:
        # Có thể tắt dòng này nếu không muốn báo khi không có kết quả
        msg = f"ℹ️ **BOT REPORT**\n⏰ {now_str}\n✅ System OK.\n❌ Không tìm thấy coin thỏa 3 điều kiện."

    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo lúc {now_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
