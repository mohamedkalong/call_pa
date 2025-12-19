import requests
import os
from datetime import datetime

USERNAME = 'longdo' 
API_TOKEN = os.environ.get('PA_TOKEN') 
FILE_PATH = f'/home/{USERNAME}/bot_rsi_futures.py'

def trigger_pa():
    # Kiểm tra xem Token có tồn tại không
    if not API_TOKEN:
        print("❌ Lỗi: Không tìm thấy biến PA_TOKEN trong GitHub Secrets!")
        return

    # In 4 ký tự đầu và cuối của Token để bạn đối chiếu xem có đúng mã trên PA không
    print(f"🔑 Token nhận được: {API_TOKEN[:4]}****{API_TOKEN[-4:]}")

    url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/consoles/"
    headers = {
        'Authorization': f'Token {API_TOKEN.strip()}' # Dùng .strip() để xóa khoảng trắng thừa
    }
    
    data = {
        'executable': 'python3',
        'arguments': FILE_PATH,
        'working_directory': f'/home/{USERNAME}/'
    }
    
    print(f"🚀 Đang gọi API PythonAnywhere...")
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 201:
        print(f"✅ Thành công! Console ID: {response.json()['id']}")
    else:
        print(f"❌ Thất bại! Mã lỗi: {response.status_code}")
        print(f"📝 Chi tiết: {response.text}")

if __name__ == "__main__":
    trigger_pa()
