import os
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import logging


app = Flask(__name__)

# 🌟 關鍵修正：關閉 Werkzeug 的預設刷屏 Log，只顯示 Error 與我們自己寫的 print()
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 狀態與指令暫存區
device_statuses = {}
pending_commands = {}  # 格式: { "deviceId": {"command": "...", "value": "..."} }

# 1. 圖片上傳 API


@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "沒有找到檔案"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "檔案名稱為空"}), 400

    # 計算民國年月日 (例如：115-03-17)
    now = datetime.now()
    minguo_year = now.year - 1911
    date_folder_name = f"{minguo_year}-{now.strftime('%m-%d')}"

    # 組合出今天的專屬路徑
    save_dir = os.path.join(UPLOAD_FOLDER, date_folder_name)
    os.makedirs(save_dir, exist_ok=True)  # 如果資料夾不存在，自動建立

    # 存檔
    filename = secure_filename(file.filename)
    filepath = os.path.join(save_dir, filename)
    file.save(filepath)

    print(f"📸 圖片已分類儲存至: {filepath}")
    return jsonify({"message": "上傳成功"}), 200

# 2. 接收 Android 狀態心跳 API


@app.route('/status', methods=['POST'])
def update_status():
    data = request.json
    if not data or 'deviceId' not in data:
        return jsonify({"error": "無效"}), 400

    device_id = data['deviceId']
    data['lastUpdate'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    device_statuses[device_id] = data

    # 取得手機目前真實的狀態
    current_interval = str(data.get('photoInterval', ''))
    is_stopping = data.get('isStopping', False)
    is_restarting = data.get('isRestarting', False) # 🌟 攔截重啟狀態


    if is_stopping:
        print(f"💀 [接收遺言] 設備 {device_id} 已確認停止服務！")
    elif is_restarting:
        print(f"🔄 [重啟通知] 設備 {device_id} 正在執行徹底重啟！")
    else:
        print(f"💓 [收到心跳] 設備: {device_id} | 頻率: {current_interval}s | 上傳: {data.get('uploadCount')}張")

    if device_id in pending_commands:
        cmd = pending_commands[device_id]

        # 如果要求改頻率，且手機回報的頻率真的變了 -> 刪除指令
        if cmd['command'] == 'SET_INTERVAL' and current_interval == str(cmd['value']):
            print(f"✅ [指令確認] 設備 {device_id} 已成功套用頻率 {current_interval}s")
            del pending_commands[device_id]

        # 如果要求自毀，且手機回傳遺言了 -> 刪除指令
        elif cmd['command'] == 'STOP_SERVICE' and is_stopping:
            print(f"✅[指令確認] 設備 {device_id} 已徹底自毀")
            del pending_commands[device_id]
        # 如果要求重啟，且手機回傳重啟了 -> 刪除指令
        elif cmd['command'] == 'RESTART_APP' and is_restarting:
            print(f"✅[指令確認] 設備 {device_id} 已接受重啟指令")
            del pending_commands[device_id]

    # 💥 關鍵修正 2：如果指令還沒被刪除，代表手機還沒改，繼續下發！(死纏爛打機制)
    response_data = {"message": "狀態已更新"}
    if device_id in pending_commands:
        cmd = pending_commands[device_id]
        response_data['command'] = cmd['command']
        response_data['value'] = cmd['value']
        print(f"📤 [指令下發] 持續發送 [{cmd['command']}] 給設備 {device_id}...")

    return jsonify(response_data), 200

# 3. 提供給前端網頁讀取的 API


@app.route('/api/command', methods=['POST'])
def send_command():
    data = request.json
    device_id = data.get('deviceId')
    command = data.get('command')
    value = data.get('value', '')

    if not device_id or not command:
        return jsonify({"error": "參數錯誤"}), 400

    pending_commands[device_id] = {"command": command, "value": value}

    # 🌟 修正 1：網頁下達指令時，立刻顯示在 CMD
    print(f"💻[Web下達指令] 準備要求設備 {device_id} 執行: {command} (參數: {value})")

    return jsonify({"message": "指令已排隊"}), 200


@app.route('/api/status', methods=['GET'])
def get_statuses():
    return jsonify(device_statuses), 200


@app.route('/', methods=['GET'])
def index():
    # 從當前目錄發送 index.html 檔案
    return send_from_directory(os.getcwd(), 'index.html')


if __name__ == '__main__':
    print("🚀 伺服器已啟動: http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080)
