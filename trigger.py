import requests
import os
import time
from datetime import datetime

# --- CONFIG ---
USERNAME = 'longdo' 
API_TOKEN = os.environ.get('PA_TOKEN').strip()
BASE_URL = f"https://eu.pythonanywhere.com/api/v0/user/{USERNAME}/consoles/"
FILE_PATH = f'/home/{USERNAME}/bot_rsi_futures.py'
headers = {'Authorization': f'Token {API_TOKEN}'}

def kill_all_consoles():
    print("🧹 Đang kiểm tra và dọn dẹp các console cũ...")
    try:
        # Lấy danh sách các console đang chạy
        response = requests.get(BASE_URL, headers=headers)
        if response.status_code == 200:
            consoles = response.json()
            if not consoles:
                print("   Ngon! Không có console nào đang mở.")
                return
            
            for c in consoles:
                console_id = c['id']
                requests.delete(f"{BASE_URL}{console_id}/", headers=headers)
                print(f"   🗑️ Đã xóa console ID: {console_id}")
        else:
            print(f"   ⚠️ Không thể lấy danh sách console: {response.text}")
    except Exception as e:
        print(f"   ❌ Lỗi khi dọn dẹp: {e}")

def trigger_new_scan():
    print(f"🚀 Đang khởi tạo console mới để chạy: {FILE_PATH}")
    data = {
        'executable': 'python3',
        'arguments': FILE_PATH,
        'working_directory': f'/home/{USERNAME}/'
    }
    
    try:
        response = requests.post(BASE_URL, headers=headers, data=data)
        if response.status_code == 201:
            res_data = response.json()
            console_id = res_data['id']
            print(f"✅ Đã kích hoạt! ID: {console_id}")
            
            # Đợi 2 phút để script thực hiện xong việc quét và gửi Telegram
            print("⏳ Đang đợi script hoàn tất công việc...")
            time.sleep(120) 
            
            # Xóa chính nó sau khi xong để tiết kiệm tài nguyên
            requests.delete(f"{BASE_URL}{console_id}/", headers=headers)
            print(f"🧹 Đã đóng console {console_id}. Hệ thống sẵn sàng cho lần tới.")
        else:
            print(f"❌ Lỗi khi tạo console: {response.text}")
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")

if __name__ == "__main__":
    print(f"--- BẮT ĐẦU CHU KỲ QUÉT: {datetime.now().strftime('%H:%M:%S')} ---")
    kill_all_consoles()
    trigger_new_scan()
    print("--- HOÀN TẤT CHU KỲ ---")
