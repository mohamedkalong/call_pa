import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os

# ================= CẤU HÌNH (CONFIG) =================
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

TELEGRAM_BOT_TOKEN = os.environ.get("TELE_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELE_CHATID")
TIMEFRAME = '4h'                
LIMIT = 500                     
RSI_PERIOD = 14   

CHANGE_THRESHOLD = 8           # 1. 24h Change > 8%
VOLUME_THRESHOLD = 55_000_000 # 2. Volume 24h > 88M
RSI_THRESHOLD = 40             # 3. RSI > 50
EMA_FAST = 34                  # 4. EMA 34
EMA_SLOW = 200                  # 5. EMA 89


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

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def format_volume(vol):
    return f"{vol/1_000_000:.1f}M"

def main():
    print(f"📊 Đang quét 4H: Change> {CHANGE_THRESHOLD}%, Vol24h> {format_volume(VOLUME_THRESHOLD)}, RSI> {RSI_THRESHOLD}, Giá > EMA{EMA_FAST} > EMA{EMA_SLOW}")

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

        # Cần ít nhất đủ nến để tính EMA chậm (89)
        if klines and len(klines) >= EMA_SLOW:
            closes = pd.Series([float(k[4]) for k in klines])
            volumes = pd.Series([float(k[7]) for k in klines]) 

            # 1. Tính RSI
            rsi_series = calculate_rsi(closes, RSI_PERIOD)
            current_rsi = rsi_series.iloc[-1]

            # 2. Tính EMA 34 và EMA 89
            ema34_series = calculate_ema(closes, EMA_FAST)
            ema89_series = calculate_ema(closes, EMA_SLOW)
            
            current_ema34 = ema34_series.iloc[-1]
            current_ema89 = ema89_series.iloc[-1]

            # 3. Tính Volume Spike (để tham khảo thêm)
            current_vol = volumes.iloc[-1]
            prev_vols_avg = volumes.iloc[-14:-1].mean() # Trung bình 13 nến trước
            vol_spike = current_vol / prev_vols_avg if prev_vols_avg > 0 else 0

            # --- KIỂM TRA ĐIỀU KIỆN MỚI ---
            # - RSI > 50
            # - Giá > EMA34
            # - EMA34 > EMA89
            if (current_rsi > RSI_THRESHOLD and 
                price > current_ema34 and 
                current_ema34 > current_ema89):
                
                print(f"✅ Khớp: {symbol} (RSI: {current_rsi:.1f}, EMA34 > EMA89)")
                results.append({
                    's': symbol,
                    'r': current_rsi,
                    'p': price,
                    'c': change_val,
                    'v': quote_vol_24h,
                    'vs': vol_spike
                })

        time.sleep(0.3) # Giảm nhẹ delay để quét nhanh hơn nếu cần

    # --- ĐỊNH DẠNG TIN NHẮN BÁO CÁO ---
    now_vn = datetime.utcnow() + timedelta(hours=7)
    date_str = now_vn.strftime("'%d/%m/%Y")
    time_str = now_vn.strftime("'%H:%M")
    vol_fil = format_volume(VOLUME_THRESHOLD)

    if results:
        results.sort(key=lambda x: x['c'], reverse=True) # Sắp xếp theo % tăng trưởng
        msg = f"🚀 8%-{vol_fil}-rsi {RSI_THRESHOLD}-EMA > {EMA_SLOW}\n"
        msg += f"{date_str}|{time_str}\n"
        for item in results:
            vol_str = format_volume(item['v'])
            msg += f"#{item['s']}|{item['p']}|+{item['c']:.1f}%|RSI:{item['r']:.1f}|Vol24h:{vol_str} \n"
                
    else:
        msg = f"ℹ️ Không tìm thấy coin thỏa điều kiện EMA34 > EMA89 & RSI > {RSI_THRESHOLD} lúc {date_str} {time_str}"

    # Gửi báo cáo qua Telegram
    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi báo cáo Telegram lúc {date_str} {time_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

if __name__ == "__main__":
    main()
