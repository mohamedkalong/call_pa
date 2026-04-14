import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os

# ================= CẤU HÌNH (CONFIG) =================
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

# Lấy Token từ biến môi trường (Environment Variables)
TELEGRAM_BOT_TOKEN = os.environ.get("TELE_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELE_CHATID")

# --- CẤU HÌNH ĐIỀU KIỆN LỌC THEO YÊU CẦU ---
TIMEFRAME = '4h'               
LIMIT = 500                    # Lấy đủ nến để tính SMA200 và Volume MA
RSI_PERIOD = 14   

CHANGE_THRESHOLD = 8           # 1. 24h Change > 8%
VOLUME_THRESHOLD = 55_000_000  # 2. Volume 24h > 55M
VOL_SPIKE_RATIO = 2.1          # 3. Vol spike > 2.1 lần trung bình 13 nến trước
VOL_MA_PERIOD = 13             
RSI_THRESHOLD = 60             # 4. RSI > 60

# ================= HÀM XỬ LÝ (FUNCTIONS) =================

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

def calculate_sma(series, period=200):
    return series.rolling(window=period).mean()

def format_volume(vol):
    return f"{vol/1_000_000:.1f}M"

def main():
    print(f"📊 Đang quét (SMA200): Change> {CHANGE_THRESHOLD}%, Vol24h> {format_volume(VOLUME_THRESHOLD)}, RSI> {RSI_THRESHOLD}, VolSpike> {VOL_SPIKE_RATIO}x")

    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    filtered_tickers = []
    for t in tickers:
        if not t['symbol'].endswith('USDT'):
            continue
        try:
            change_percent = float(t['priceChangePercent'])
            quote_vol = float(t['quoteVolume'])
            if change_percent > CHANGE_THRESHOLD and quote_vol > VOLUME_THRESHOLD:
                filtered_tickers.append(t)
        except:
            continue

    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin tiềm năng. Đang check kỹ thuật 4H...")

    results = []
    for t in filtered_tickers:
        symbol = t['symbol']
        change_val = float(t['priceChangePercent'])
        quote_vol_24h = float(t['quoteVolume'])
        price = float(t['lastPrice'])

        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)

        if klines and len(klines) >= 200:
            closes = pd.Series([float(k[4]) for k in klines])
            volumes = pd.Series([float(k[7]) for k in klines]) 

            # 1. Tính RSI
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            current_rsi = rsi_series.iloc[-1]

            # 2. Tính SMA 200
            sma_series = calculate_sma(closes, 200)
            current_sma = sma_series.iloc[-1]

            # 3. Tính Volume Spike (Nến đóng gần nhất so với trung bình 13 nến trước)
            current_vol = volumes.iloc[-1]
            prev_vols_avg = volumes.iloc[-(VOL_MA_PERIOD+1):-1].mean()
            vol_spike = current_vol / prev_vols_avg if prev_vols_avg > 0 else 0

            # KIỂM TRA ĐIỀU KIỆN
            if (current_rsi > RSI_THRESHOLD and 
                price > current_sma and 
                vol_spike > VOL_SPIKE_RATIO):
                
                print(f"✅ Khớp: {symbol} (RSI: {current_rsi:.1f}, VolSpike: {vol_spike:.2f}x)")
                results.append({
                    's': symbol,
                    'r': current_rsi,
                    'p': price,
                    'c': change_val,
                    'v': quote_vol_24h,
                    'vs': vol_spike
                })

        time.sleep(0.2)

    # --- ĐỊNH DẠNG TIN NHẮN BÁO CÁO ---
    now_vn = datetime.utcnow() + timedelta(hours=7)
    date_str = now_vn.strftime("'%d/%m/%Y")
    time_str = now_vn.strftime("'%H:%M")

    if results:
        results.sort(key=lambda x: x['r'], reverse=True)
        msg = f"🚀 Github 24h>8%, Vol>55M, RSI>60, VolSpike>2.1x \n"          
        for item in results:
            vol_str = format_volume(item['v'])
            msg += f"{date_str}|{time_str}|#{item['s']}|{item['p']} |24h:+{item['c']:.1f}% |RSI:{item['r']:.1f}|Vol24h:{vol_str}\n"
                
    else:
        msg = f"ℹ️ Không tìm thấy coin thỏa SMA200 & RSI > {RSI_THRESHOLD} lúc {date_str} {time_str}"

    # Gửi báo cáo qua Telegram
    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo lúc {date_str} {time_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
