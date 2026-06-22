from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
from ultralytics import YOLO
import time
import os
import random
import glob
from datetime import datetime
from insight_engine import get_ai_prediction, get_citizen_sentiment
import requests
import threading
from werkzeug.security import generate_password_hash, check_password_hash
import json
import uuid

app = Flask(__name__)

# ==========================================
# 1. SETUP AI & GLOBAL STATISTICS
# ==========================================
model_traffic = YOLO("weights/best.pt")
model_human = YOLO("weights/yolo11n.pt") 

EVIDENCE_DIR = os.path.join('static', 'image')

def initialize_evidence_folder():
    if not os.path.exists(EVIDENCE_DIR):
        os.makedirs(EVIDENCE_DIR)
    else:
        files = glob.glob(os.path.join(EVIDENCE_DIR, '*.jpg'))
        for f in files:
            try:
                os.remove(f)
            except Exception as e:
                print(f"Error removing {f}: {e}")

initialize_evidence_folder()

polygons = {'L': [], 'S': [], 'D': []}
current_key = 'L'
timers = {}
frame_width, frame_height = 1280, 720

ai_enabled = False 

violation_stats = {
    'bus_lane': 0,
    'illegal_stop': 0,
    'suspicious_dropoff': 0
}
logged_ids = set() 

ai_logs = []
MAX_LOGS = 100 
stream_quality = "high"

TELEGRAM_TOKEN = '8772260797:AAFF2vYQJb1ss_VbOaAQxTW1IZ-KRkPO6cc'
TELEGRAM_CHAT_ID = '1882349075'
telegram_enabled = False

def add_system_log(message, level="INFO"):
    global ai_logs
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    ai_logs.append(log_entry)
    if len(ai_logs) > MAX_LOGS:
        ai_logs.pop(0)

def save_evidence_screenshot(frame, violation_id, violation_type):
    date_str = datetime.now().strftime("%Y%m%d")
    time_str = datetime.now().strftime("%H%M%S")
    filename = f"VIO_{violation_type}_{violation_id}_{date_str}_{time_str}.jpg"
    filepath = os.path.join(EVIDENCE_DIR, filename)
    cv2.imwrite(filepath, frame)
    add_system_log(f"Bukti disimpan: {filename}", "SCAN")

    if telegram_enabled:
        pesan_pelanggaran = f"🚨 PELANGGARAN DETECTED!\nJenis: {violation_type}\nID: {violation_id}"
        threading.Thread(target=send_telegram_alert, args=(filepath, pesan_pelanggaran)).start()

def send_telegram_alert(filepath, message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(filepath, 'rb') as photo:
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': message}
            files = {'photo': photo}
            requests.post(url, data=payload, files=files, timeout=10)
    except Exception as e:
        print(f"Gagal mengirim Telegram: {e}")

# --- SETUP DB JSON ---
DB_DIR = 'db'
DB_FILE = os.path.join(DB_DIR, 'laporan_warga.json')
ADMIN_PASSWORD_HASH = generate_password_hash('admin123')

def initialize_json_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        add_system_log("Folder database dibuat: db/", "SYSTEM")
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({"reports": []}, f, indent=2, ensure_ascii=False)
        add_system_log("Database JSON baru dibuat: db/laporan_warga.json", "SYSTEM")

def read_reports():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get('reports', [])
    except (FileNotFoundError, json.JSONDecodeError) as e:
        add_system_log(f"Gagal membaca DB: {e}", "ERROR")
        return []

def write_reports(reports: list) -> bool:
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({"reports": reports}, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        add_system_log(f"Gagal menulis ke DB: {e}", "ERROR")
        return False

initialize_json_db()

# ==========================================
# 2. RUTE API (KOMUNIKASI WEB KE BACKEND)
@app.route('/set_quality', methods=['POST'])
def set_quality():
    global stream_quality
    data = request.json
    stream_quality = data['quality']
    add_system_log(f"Kualitas stream diubah menjadi {stream_quality.upper()}", "SYSTEM")
    return jsonify({"status": "success", "stream_quality": stream_quality})

@app.route('/pelaporan')
def pelaporan_page():
    return render_template('pelaporan.html')

@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot_test.html')

@app.route('/toggle_telegram', methods=['POST'])
def toggle_telegram():
    global telegram_enabled
    data = request.json
    telegram_enabled = data['status']
    if telegram_enabled:
        add_system_log("Telegram Auto-Report DIAKTIFKAN.", "SYSTEM")
    else:
        add_system_log("Telegram Auto-Report DIMATIKAN.", "SYSTEM")
    return jsonify({"status": "success", "telegram_enabled": telegram_enabled})

@app.route('/toggle_ai', methods=['POST'])
def toggle_ai():
    global ai_enabled, timers
    data = request.json
    ai_enabled = data['status']
    
    if not ai_enabled:
        timers.clear() 
        add_system_log("Mesin AI DIMATIKAN. Mode hemat daya aktif.", "SYSTEM")
    else:
        add_system_log("Mesin AI DINYALAKAN. Memulai inferensi spasial...", "SYSTEM")
        
    return jsonify({"status": "success", "ai_enabled": ai_enabled})

@app.route('/set_mode', methods=['POST'])
def set_mode():
    global current_key
    current_key = request.json['mode']
    add_system_log(f"Admin mengganti mode area ke: {current_key}", "SYSTEM")
    return jsonify({"status": "success", "mode": current_key})

@app.route('/add_point', methods=['POST'])
def add_point():
    global polygons, current_key, frame_width, frame_height
    data = request.json
    x = int(data['x'] * frame_width)
    y = int(data['y'] * frame_height)
    polygons[current_key].append((x, y))
    return jsonify({"status": "success"})

@app.route('/clear_mode', methods=['POST'])
def clear_mode():
    global polygons, current_key
    polygons[current_key] = []
    add_system_log(f"Admin menghapus area poligon: {current_key}", "SYSTEM")
    return jsonify({"status": "success"})

@app.route('/api/insights')
def api_insights():
    global violation_stats, timers, ai_logs
    
    # Hitung kepadatan rata-rata
    active_vehicles = len(timers)
    density = min(100, (active_vehicles / 15) * 100)
    
    # Mengirim dictionary violation_stats dan list ai_logs ke insight_engine
    insight_text, accuracy = get_ai_prediction(violation_stats, density, ai_logs)
    
    return jsonify({
        "ai_insight": insight_text,
        "ai_accuracy": accuracy,
        "stats": violation_stats, 
        "sentiments": get_citizen_sentiment(count=2)
    })

@app.route('/api/logs')
def api_logs():
    global ai_logs
    return jsonify({"logs": ai_logs})

@app.route('/api/evidence')
def api_evidence():
    if not os.path.exists(EVIDENCE_DIR):
        return jsonify([])
    
    files = glob.glob(os.path.join(EVIDENCE_DIR, '*.jpg'))
    evidence_list = []
    for f in files:
        filename = os.path.basename(f)
        parts = filename.replace('.jpg', '').split('_')
        
        v_type = parts[1] if len(parts) > 1 else "UNKNOWN"
        time_str = parts[4] if len(parts) > 4 else ""
        
        formatted_time = ""
        if len(time_str) == 6:
            formatted_time = f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
        else:
            formatted_time = time_str
            
        evidence_list.append({
            "url": f"/static/image/{filename}",
            "filename": filename,
            "type": v_type,
            "time": formatted_time,
            "raw_time": os.path.getmtime(f)
        })
    
    evidence_list.sort(key=lambda x: x['raw_time'], reverse=True)
    return jsonify(evidence_list)



@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if username == 'admin' and check_password_hash(ADMIN_PASSWORD_HASH, password):
        add_system_log(f"Login admin berhasil dari IP: {request.remote_addr}", "SYSTEM")
        return jsonify({"status": "success", "role": "admin", "name": "Petugas Diskominfo"})

    add_system_log(f"Percobaan login gagal — username: '{username}'", "ALERT")
    return jsonify({"status": "error", "message": "Username atau password salah."}), 401

@app.route('/api/reports', methods=['GET'])
def api_reports_get():
    reports = read_reports()
    reports_sorted = sorted(reports, key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({"reports": reports_sorted, "total": len(reports_sorted)})

@app.route('/api/reports', methods=['POST'])
def api_reports_post():
    data = request.json or {}
    location = data.get('location', '').strip()
    description = data.get('description', '').strip()

    if not location or not description:
        return jsonify({"status": "error", "message": "Lokasi dan deskripsi wajib diisi."}), 400

    raw_name = data.get('reporter_name', '').strip()
    if raw_name:
        reporter_name = raw_name
        is_anonymous = False
        initials = ''.join(w[0] for w in raw_name.split() if w).upper()[:2] or 'WG'
        reporter_color = '#64a0ff'
    else:
        reporter_name = 'Anonim (Unverified)'
        is_anonymous = True
        initials = '?'
        reporter_color = '#606060'

    report_id = f"RPT-{uuid.uuid4().hex[:4].upper()}"

    new_report = {
        "id": report_id,
        "name": reporter_name,
        "initials": initials,
        "color": reporter_color,
        "is_anonymous": is_anonymous,
        "type": data.get('type', 'Lainnya'),
        "location": location,
        "description": description,
        "urgency": data.get('urgency', 'med'),
        "status": "new",
        "upvotes": 0,
        "has_photo": bool(data.get('has_photo', False)),
        "timestamp": datetime.now().isoformat(),
    }

    existing = read_reports()
    existing.append(new_report)

    if write_reports(existing):
        add_system_log(f"Laporan tersimpan: {report_id} | Pelapor: {reporter_name}", "INFO")
        return jsonify({"status": "success", "report_id": report_id}), 201

    return jsonify({"status": "error", "message": "Gagal menyimpan laporan."}), 500

# ==========================================
# 3. CORE LOGIC (AI + POLYGON RULES)
# ==========================================
def generate_frames():
    global polygons, current_key, timers, violation_stats, logged_ids, frame_width, frame_height, ai_enabled
    
    video_path = "http://127.0.0.1:5001/stream/gadog_01" 
    cap = cv2.VideoCapture(video_path)
    
    add_system_log("Terhubung ke CCTV Stream Dishub.", "SYSTEM")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            time.sleep(1)
            cap = cv2.VideoCapture(video_path)
            continue

        if not ai_enabled:
            # --- PENGATUR KUALITAS STREAMING (ANTI-LAG) ---
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85] # Default HD
            frame_to_stream = frame
            
            if stream_quality == "med":
                frame_to_stream = cv2.resize(frame, (0,0), fx=0.6, fy=0.6)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
            elif stream_quality == "low":
                frame_to_stream = cv2.resize(frame, (0,0), fx=0.35, fy=0.35)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 35]
                
            ret, buffer = cv2.imencode('.jpg', frame_to_stream, encode_param)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            continue

        frame_height, frame_width = frame.shape[:2]

        res_traffic = model_traffic.track(frame, persist=True, conf=0.25, iou=0.5, imgsz=640, verbose=False)
        res_human = model_human.track(frame, persist=True, classes=[0], conf=0.3, verbose=False)

        annotated_frame = res_traffic[0].plot()
        annotated_frame = res_human[0].plot(img=annotated_frame)

        human_coords = []
        if res_human[0].boxes.xyxy is not None:
            human_coords = res_human[0].boxes.xyxy.cpu().numpy()

        # --- BUAT MASKING PIXEL UNTUK DETEKSI AKURAT ---
        mask_L = np.zeros((frame_height, frame_width), dtype=np.uint8)
        mask_S = np.zeros((frame_height, frame_width), dtype=np.uint8)
        mask_D = np.zeros((frame_height, frame_width), dtype=np.uint8)

        if len(polygons['L']) > 2:
            cv2.fillPoly(mask_L, [np.array(polygons['L'], np.int32)], 255)
        if len(polygons['S']) > 2:
            cv2.fillPoly(mask_S, [np.array(polygons['S'], np.int32)], 255)
        if len(polygons['D']) > 2:
            cv2.fillPoly(mask_D, [np.array(polygons['D'], np.int32)], 255)

        if res_traffic[0].boxes.id is not None:
            boxes = res_traffic[0].boxes.xyxy.cpu().numpy()
            clss = res_traffic[0].boxes.cls.cpu().numpy()
            ids = res_traffic[0].boxes.id.cpu().numpy()

            for box, cls, id in zip(boxes, clss, ids):
                label = model_traffic.names[int(cls)]
                
                # Cegah koordinat keluar dari batas layar
                x1, y1 = max(0, int(box[0])), max(0, int(box[1]))
                x2, y2 = min(frame_width, int(box[2])), min(frame_height, int(box[3]))
                
                bbox_area = (x2 - x1) * (y2 - y1)
                
                in_l, in_s, in_d = False, False, False
                
                # Cek apakah 5% luas kendaraan memotong poligon
                if bbox_area > 0:
                    if len(polygons['L']) > 2:
                        in_l = (cv2.countNonZero(mask_L[y1:y2, x1:x2]) / bbox_area) >= 0.05
                    if len(polygons['S']) > 2:
                        in_s = (cv2.countNonZero(mask_S[y1:y2, x1:x2]) / bbox_area) >= 0.05
                    if len(polygons['D']) > 2:
                        in_d = (cv2.countNonZero(mask_D[y1:y2, x1:x2]) / bbox_area) >= 0.05

                # Titik untuk meletakkan teks peringatan
                x_c = int((x1 + x2) / 2)
                y_b = y2

                if id not in timers:
                    timers[id] = {'start': time.time()}
                    add_system_log(f"Objek ID:{int(id)} teridentifikasi sebagai '{label}'.", "SCAN")
                
                elapsed = time.time() - timers[id]['start']

                # --- RULE L (Bus Lane) ---
                # Semua kendaraan selain Bus akan KENA TILANG jika masuk jalur L
                if in_l:
                    if label != 'Bus': 
                        cv2.putText(annotated_frame, "LANE VIOLATION!", (x_c-30, y_b-10), 0, 0.6, (0,0,255), 2)
                        if f"{id}_L" not in logged_ids:
                            violation_stats['bus_lane'] += 1
                            logged_ids.add(f"{id}_L")
                            add_system_log(f"PELANGGARAN JALUR! ID:{int(id)} ({label}) masuk area Busway.", "ALERT")
                            save_evidence_screenshot(annotated_frame, int(id), 'BUSLANE')

                # --- RULE D (Traffic Light / Long Stop) ---
                # Diberikan waktu aman selama 180 detik (3 menit) untuk antrean lampu merah
                if in_d and elapsed > 180: 
                    cv2.putText(annotated_frame, "ILLEGAL PARK/STOP!", (int(box[0]), int(box[3])+20), 0, 0.6, (0,0,255), 2)
                    if f"{id}_D" not in logged_ids:
                        violation_stats['illegal_stop'] += 1
                        logged_ids.add(f"{id}_D")
                        add_system_log(f"PARKIR LIAR! ID:{int(id)} ({label}) menetap > 3 menit di area D.", "ALERT")
                        save_evidence_screenshot(annotated_frame, int(id), 'ILLEGALSTOP')

                # --- RULE S (Safe Drop-off Zone) ---
                # Hanya curigai Mobil/Truk/Auto. Motor ("Two Wheeler") AMAN!
                if not in_s and label != 'Two Wheeler':
                    for h_box in human_coords:
                        h_x_c = (h_box[0] + h_box[2]) / 2
                        h_y_b = h_box[3]
                        
                        dist = np.linalg.norm(np.array([x_c, y_b]) - np.array([h_x_c, h_y_b]))
                        
                        if dist < 85: 
                            cv2.putText(annotated_frame, "SUSPICIOUS DROP-OFF!", (int(box[0]), int(box[1])-10), 0, 0.6, (0,255,255), 2)
                            if f"{id}_drop" not in logged_ids:
                                violation_stats['suspicious_dropoff'] += 1
                                logged_ids.add(f"{id}_drop")
                                add_system_log(f"DROP-OFF ILEGAL! Manusia terdeteksi mendekat ke ID:{int(id)} ({label}) di luar zona S.", "ALERT")
                                save_evidence_screenshot(annotated_frame, int(id), 'DROPOFF')

        # Gambar Layer Poligon
        overlay = annotated_frame.copy()
        colors = {'L': (255, 0, 0), 'S': (0, 255, 0), 'D': (0, 0, 255)}
        for key, points in polygons.items():
            if len(points) > 1:
                pts = np.array(points, np.int32)
                cv2.fillPoly(overlay, [pts], colors[key])
                cv2.polylines(annotated_frame, [pts], True, colors[key], 2)
        cv2.addWeighted(overlay, 0.3, annotated_frame, 0.7, 0, annotated_frame)

        # --- PENGATUR KUALITAS STREAMING (ANTI-LAG) ---
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85] # Default HD
        frame_to_stream = annotated_frame
        
        if stream_quality == "med":
            frame_to_stream = cv2.resize(annotated_frame, (0,0), fx=0.6, fy=0.6)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        elif stream_quality == "low":
            frame_to_stream = cv2.resize(annotated_frame, (0,0), fx=0.35, fy=0.35)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 35]
            
        ret, buffer = cv2.imencode('.jpg', frame_to_stream, encode_param)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(debug=True, threaded=True)

  