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

# ==========================================
# 2. RUTE API (KOMUNIKASI WEB KE BACKEND)
# ==========================================
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
            ret, buffer = cv2.imencode('.jpg', frame)
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

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
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

  