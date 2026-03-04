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

# --- CẤU HÌNH ĐIỀU KIỆN LỌC THEO CHIẾN LƯỢC TRUNG HẠN ---
TIMEFRAME = '4h'               # Sử dụng khung 4h để xác định Trend [cite: 1]
LIMIT = 500                    # Lấy đủ 233 nến để tính SMA233 [cite: 1]
RSI_PERIOD = 14                # Chu kỳ RSI tiêu chuẩn

CHANGE_THRESHOLD = 8           # 1. 24h Change > 8%
VOLUME_THRESHOLD = 55_000_000  # 2. Volume 24h > 55M [cite: 1]
RSI_THRESHOLD = 50             # 3. RSI 4h > 50

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

def calculate_sma(series, period=233):
    return series.rolling(window=period).mean()

def format_volume(vol):
    return f"{vol/1_000_000:.0f}M"

def main():
    print(f"📊 Đang quét: Change > {CHANGE_THRESHOLD}%, Vol > {format_volume(VOLUME_THRESHOLD)}, RSI4h > {RSI_THRESHOLD} & Price > SMA233-4h...")
    
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
            
            # [cite_start]Điều kiện lọc sơ bộ để giảm tải API [cite: 4]
            if change_percent > CHANGE_THRESHOLD and quote_vol > VOLUME_THRESHOLD:
                filtered_tickers.append(t)
        except:
            continue
    
    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin tiềm năng. Đang check kỹ thuật 4H...")

    results = []

    # [cite_start]Bước 2: Kiểm tra chi tiết RSI và SMA cho từng coin [cite: 5]
    for t in filtered_tickers:
        symbol = t['symbol']
        change_val = float(t['priceChangePercent'])
        quote_vol = float(t['quoteVolume'])
        price = float(t['lastPrice'])
        
        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)
        
        if klines and len(klines) >= LIMIT:
            # [cite_start]Lấy giá đóng cửa [cite: 6]
            closes = pd.Series([float(k[4]) for k in klines])
            
            # [cite_start]Tính RSI 4h [cite: 6]
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            current_rsi = rsi_series.iloc[-1]
            
            # Tính SMA 233 khung 4h
            sma_series = calculate_sma(closes, 233)
            current_sma = sma_series.iloc[-1]

            # ĐIỀU KIỆN LỌC QUYẾT ĐỊNH: RSI > 50 VÀ Giá > SMA233-4H
            if current_rsi > RSI_THRESHOLD and price > current_sma:
                print(f"✅ Khớp: {symbol} (RSI: {current_rsi:.1f}, Price > SMA233)")
                results.append({
                    's': symbol, 
                    'r': current_rsi, 
                    'p': price, 
                    'c': change_val,
                    'v': quote_vol
                })
        
        # [cite_start]Nghỉ ngắn để tránh spam API [cite: 8]
        time.sleep(0.5)

    # --- ĐỊNH DẠNG TIN NHẮN BÁO CÁO ---
    now_vn = datetime.utcnow() + timedelta(hours=7)
    date_str = now_vn.strftime("'%d/%m/%Y")
    time_str = now_vn.strftime("'%H:%M")

    if results:
        # [cite_start]Sắp xếp theo RSI giảm dần [cite: 8]
        results.sort(key=lambda x: x['r'], reverse=True)
        
        msg = f"🚀 **BOT >sma233-4h, rsi>50, vol>55M**|\n"
        #msg += "date|time|ticker|last price|24h change|rsi|vol24h\n"
        
        for item in results:
            vol_str = format_volume(item['v'])
            # [cite_start]Định dạng: date|time|ticker|last price|24h change|rsi|vol24h [cite: 9, 10]
            msg += f"{date_str}|{time_str}|**#{item['s']}**|{item['p']}|+{item['c']:.2f}%|{item['r']:.1f}|{vol_str}\n"
            
    else:
        msg = f"ℹ️ Không tìm thấy coin thỏa mãn SMA233-4H & RSI > 50 lúc {date_str} {time_str}"

    # [cite_start]Gửi báo cáo qua Telegram [cite: 11]
    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo lúc {date_str} {time_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
