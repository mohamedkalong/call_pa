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

TIMEFRAME  = '4h'
LIMIT      = 1000
RSI_PERIOD = 14

CHANGE_THRESHOLD = 5            # 24h Change > 5%
VOLUME_THRESHOLD = 30_000_000  # Volume 24h > 100M
RSI_THRESHOLD    = 66           # RSI > 40
EMA_FAST         = 13
EMA_SLOW         = 123

WHITELIST_FILE = "whitelist.json"

# ================= HÀM XỬ LÝ =================

def load_whitelist() -> set:
    """Đọc whitelist từ file JSON. Trả về set rỗng nếu file không tồn tại."""
    if not os.path.exists(WHITELIST_FILE):
        print(f"⚠️  Không tìm thấy {WHITELIST_FILE}. Bỏ qua lọc mcap.")
        return set()
    with open(WHITELIST_FILE, "r") as f:
        data = json.load(f)
    symbols = set(data.get("symbols", []))
    updated = data.get("updated_at", "N/A")
    print(f"📋 Whitelist: {len(symbols)} coin | Cập nhật: {updated}")
    return symbols


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
    delta  = series.diff()
    up     = delta.clip(lower=0)
    down   = -1 * delta.clip(upper=0)
    ma_up   = up.ewm(com=period - 1, adjust=False).mean()
    ma_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def format_volume(vol):
    return f"{vol / 1_000_000:.1f}M"


def main():
    # --- Load whitelist ---
    mcap_whitelist = load_whitelist()
    use_whitelist  = len(mcap_whitelist) > 0

    print(f"📊 Đang quét {TIMEFRAME}: Change>{CHANGE_THRESHOLD}% | Vol24h>{format_volume(VOLUME_THRESHOLD)} | RSI>{RSI_THRESHOLD} | Giá>EMA{EMA_FAST}>EMA{EMA_SLOW} | Mcap>50M")

    # --- Lấy toàn bộ ticker từ Binance ---
    tickers = get_data_via_proxy("ticker")
    if not tickers:
        print("❌ Không lấy được dữ liệu Ticker.")
        return

    # --- Lọc vòng 1: Change%, Volume, Whitelist ---
    filtered_tickers = []
    for t in tickers:
        if not t['symbol'].endswith('USDT'):
            continue
        try:
            symbol         = t['symbol']
            change_percent = float(t['priceChangePercent'])
            quote_vol      = float(t['quoteVolume'])

            if change_percent <= CHANGE_THRESHOLD:
                continue
            if quote_vol <= VOLUME_THRESHOLD:
                continue
            if use_whitelist and symbol not in mcap_whitelist:
                continue

            filtered_tickers.append(t)
        except:
            continue

    print(f"🔍 Tìm thấy {len(filtered_tickers)} coin tiềm năng. Đang check kỹ thuật {TIMEFRAME}...")

    # --- Lọc vòng 2: RSI + EMA ---
    results = []
    for t in filtered_tickers:
        symbol       = t['symbol']
        change_val   = float(t['priceChangePercent'])
        quote_vol_24h = float(t['quoteVolume'])
        price        = float(t['lastPrice'])

        params = {'symbol': symbol, 'interval': TIMEFRAME, 'limit': LIMIT}
        klines = get_data_via_proxy("klines", params)

        if klines and len(klines) >= EMA_SLOW:
            closes  = pd.Series([float(k[4]) for k in klines])
            volumes = pd.Series([float(k[7]) for k in klines])

            rsi_series  = calculate_rsi(closes, RSI_PERIOD)
            ema34_series = calculate_ema(closes, EMA_FAST)
            ema200_series = calculate_ema(closes, EMA_SLOW)

            current_rsi   = rsi_series.iloc[-1]
            current_ema34 = ema34_series.iloc[-1]
            current_ema200 = ema200_series.iloc[-1]

            current_vol    = volumes.iloc[-1]
            prev_vols_avg  = volumes.iloc[-14:-1].mean()
            vol_spike      = current_vol / prev_vols_avg if prev_vols_avg > 0 else 0

            if (current_rsi > RSI_THRESHOLD and
                    price > current_ema34 and
                    current_ema34 > current_ema200):

                print(f"✅ Khớp: {symbol} | RSI:{current_rsi:.1f} | EMA34:{current_ema34:.4f} | EMA200:{current_ema200:.4f}")
                results.append({
                    's':  symbol,
                    'r':  current_rsi,
                    'p':  price,
                    'c':  change_val,
                    'v':  quote_vol_24h,
                    'vs': vol_spike
                })

        time.sleep(0.3)

    # --- Định dạng tin nhắn ---
    now_vn   = datetime.utcnow() + timedelta(hours=7)
    date_str = now_vn.strftime("'%d/%m/%Y")
    time_str = now_vn.strftime("'%H:%M")
    vol_fil  = format_volume(VOLUME_THRESHOLD)

    if results:
        results.sort(key=lambda x: x['c'], reverse=True)
        msg  = f"🚀 {CHANGE_THRESHOLD}%-{vol_fil}-RSI{RSI_THRESHOLD}-EMA>{EMA_SLOW}-Mcap>50M\n"
        msg += f"{date_str}|{time_str}\n"
        for item in results:
            vol_str = format_volume(item['v'])
            msg += f"#{item['s']}|{item['p']}|+{item['c']:.1f}%|RSI:{item['r']:.1f}|Vol:{vol_str}\n"
    else:
        msg = f"ℹ️ Không tìm thấy coin thỏa điều kiện lúc {date_str} {time_str}"

    # --- Gửi Telegram ---
    try:
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tele_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        print(f"✅ Đã gửi Telegram lúc {date_str} {time_str}.")
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")


if __name__ == "__main__":
    main()
