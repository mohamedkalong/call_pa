import requests
import time

# --- CONFIG ---
USERNAME = "longdo"
API_TOKEN = "fb0d88a9f4ec84aa21b3e9ee3ff2127046cd1f4f"
FILE_PATH = f'/home/{USERNAME}/bot_rsi_futures.py' # Đường dẫn file trên PA

# URL API của PythonAnywhere để tạo một Console mới và chạy lệnh
url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/consoles/"
headers = {'Authorization': f'Token {API_TOKEN}'}

def trigger_pa():
    # 1. Ra lệnh cho PA mở một console và chạy file python
    data = {
        'executable': 'python3',
        'arguments': FILE_PATH,
        'working_directory': f'/home/{USERNAME}/'
    }
    
    print(f"🚀 Đang ra lệnh cho PythonAnywhere chạy {FILE_PATH}...")
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 201:
        console_id = response.json()['id']
        print(f"✅ Đã kích hoạt thành công! Console ID: {console_id}")
        
        # Đợi một chút để script chạy xong (tùy vào thời gian quét của bạn)
        time.sleep(60) 
        
        # (Tùy chọn) Đóng console sau khi chạy để tránh lãng phí tài nguyên tài khoản Free
        requests.delete(f"{url}{console_id}/", headers=headers)
        print("🧹 Đã dọn dẹp Console.")
    else:
        print(f"❌ Lỗi kích hoạt: {response.text}")

if __name__ == "__main__":
    trigger_pa()
