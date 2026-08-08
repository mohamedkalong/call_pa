import pandas as pd
import requests
import time
import json
import os
from datetime import datetime, timedelta

# ================= CẤU HÌNH (CONFIG) =================
PA_PROXY_URL = "https://longdo.eu.pythonanywhere.com/proxy"

TELEGRAM_BOT_TOKEN = os.environ.get("TELE_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELE_CHATID")

TIMEFRAME     = '4h'
LIMIT         = 200   # RSI(14) chỉ cần 100 nến là đủ tính toán chính xác
RSI_PERIOD    = 14
RSI_THRESHOLD = 71    # Điều kiện RSI > 71

WHITELIST_FILE = "whitelist.json"

# ================= HÀM XỬ LÝ =================

def load_whitelist() -> set:
    """Đọc whitelist từ file JSON."""
    if not os.path.exists(WHITELIST_FILE):
        print(f"⚠️  Không tìm thấy {WHITELIST_FILE}. Vui lòng kiểm tra lại file.")
        return set()
    try:
        with open(WHITELIST_FILE, "r") as f:
            data = json.load(f)
        symbols = set(data.get("symbols", []))
        updated = data.get("updated_at", "N/A")
        print(f"📋 Whitelist: {len(symbols)} coin | Cập nhật: {updated}")
        return symbols
    except Exception as e:
        print(f"❌ Lỗi đọc file Whitelist: {e}")
        return set()


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
    delta   = series.diff()
    up      = delta.clip(lower=0)
    down    = -1 * delta.clip(upper=0)
    ma_up   = up.ewm(com=period - 1, adjust=False).mean()
    ma_down = down.ewm(com=period - 1, adjust=False).mean()
    rs      = ma_up / ma_down
    return 100 - (100 / (1 + rs))


def format_volume(vol):
    return f"{vol / 1_000_000:.1f}M"


def main():
    # --- Load whitelist ---
    mcap_whitelist = load_whitelist()
    if not mcap_whitelist:
        print("❌ Whitelist rỗng hoặc không tồn tại. Dừng quét.")
        return

    print(f"📊 Đang quét khung {TIMEFRAME}: Chỉ lọc coin trong Whitelist có RSI > {RSI_THRESHOLD}")

    # --- Lấy toàn bộ ticker từ Binance ---
    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    # --- Lọc vòng 1: Chỉ giữ lại các coin NẰM TRONG WHITELIST ---
    filtered_tickers = []
    for t in tickers:
        symbol = t.get('symbol', '')
        if symbol in mcap_whitelist:
            filtered_tickers.append(t)

    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin thuộc Whitelist. Đang kiểm tra RSI {TIMEFRAME}...")

    # --- Lọc vòng 2: Chỉ check điều kiện RSI > 71 ---
    results = []
    for t in filtered_tickers:
        symbol        = t['symbol']
        change_val    = float(t.get('priceChangePercent', 0))
        quote_vol_24h = float(t.get('quoteVolume', 0))
        price         = float(t.get('lastPrice', 0))

        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)

        if klines and len(klines) >= RSI_PERIOD + 1:
            closes      = pd.Series([float(k[4]) for k in klines])
            rsi_series  = calculate_rsi(closes, RSI_PERIOD)
            current_rsi = rsi_series.iloc[-2]

            # --- Điều kiện: RSI > 71 ---
            if current_rsi > RSI_THRESHOLD:
                print(f"✅ Khớp: {symbol} | RSI: {current_rsi:.1f} | Giá: {price}")
                results.append({
                    's': symbol,
                    'r': current_rsi,
                    'p': price,
                    'c': change_val,
                    'v': quote_vol_24h
                })

        time.sleep(0.2)  # Giảm delay một chút cho tốc độ quét nhanh hơn

    # --- Định dạng tin nhắn gửi Telegram ---
    now_vn   = datetime.utcnow() + timedelta(hours=7)
    date_str = now_vn.strftime("%d/%m/%Y")
    time_str = now_vn.strftime("%H:%M")

    if results:
        # Sắp xếp theo RSI giảm dần (RSI cao nhất lên đầu)
        results.sort(key=lambda x: x['r'], reverse=True)
        msg  = f"🚀 *CẢNH BÁO COIN RSI > {RSI_THRESHOLD} (WHITELIST)*\n"
        msg += f"{date_str} | {time_str} (Khung {TIMEFRAME})\n"
        for item in results:
            vol_str = format_volume(item['v'])
            msg += f"#{item['s']}|{item['p']}|{item['c']:+.1f}%|RSI:{item['r']:.1f}|Vol:{vol_str}\n"
    else:
        msg = f"ℹ️ Không có coin nào trong Whitelist thỏa mãn RSI > {RSI_THRESHOLD} lúc {date_str} {time_str}"

    # --- Gửi Telegram ---
    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi Telegram lúc {date_str} {time_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")


if __name__ == "__main__":
    main()
