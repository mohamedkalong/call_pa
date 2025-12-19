import requests
import os
import sys
from datetime import datetime

# Lấy thông tin từ biến môi trường (Secrets)
# Nếu bạn chưa dùng Secrets, hãy thay os.environ.get bằng mã Token trực tiếp để test
USERNAME = 'longdo'
API_TOKEN = os.environ.get('PA_TOKEN') 
FILE_PATH = f'/home/{USERNAME}/bot_rsi_futures.py'

def trigger_pa():
    if not API_TOKEN:
        print("❌ Lỗi: Không tìm thấy PA_TOKEN trong Secrets!")
        return

    url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/consoles/"
    headers = {'Authorization': f'Token {API_TOKEN}'}
    
    data = {
        'executable': 'python3',
        'arguments': FILE_PATH,
        'working_directory': f'/home/{USERNAME}/'
    }
    
    print(f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🚀 Đang gửi yêu cầu chạy: {FILE_PATH}...")

    try:
        response = requests.post(url, headers=headers, data=data)
        
        if response.status_code == 201:
            res_data = response.json()
            print(f"✅ Kích hoạt thành công!")
            print(f"🔹 Console ID: {res_data['id']}")
            print(f"🔹 Console URL: {res_data['console_url']}")
            print("💡 Kiểm tra Telegram sau 1-2 phút nhé!")
        else:
            print(f"❌ Thất bại! Mã lỗi: {response.status_code}")
            print(f"📝 Chi tiết lỗi: {response.text}")
            
    except Exception as e:
        print(f"💥 Lỗi kết nối: {e}")

if __name__ == "__main__":
    trigger_pa()
