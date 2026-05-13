import cv2
import numpy as np
from ultralytics import YOLO
import time

# 1. Inisialisasi Model
model_traffic = YOLO("weights/best.pt")
model_human = YOLO("yolo11n.pt") 

# Variabel Global
polygons = {'L': [], 'S': [], 'D': []}
current_key = 'L'
timers = {}

def mouse_event(event, x, y, flags, param):
    global polygons, current_key
    if event == cv2.EVENT_LBUTTONDOWN:
        polygons[current_key].append((x, y))

# 2. Setup Video & UI
video_path = "videos/cctv_gadog.mp4"
cap = cv2.VideoCapture(video_path)
cv2.namedWindow("Gadog Smart System")
cv2.setMouseCallback("Gadog Smart System", mouse_event)

# Trackbar untuk setting ketebalan dan transparansi garis
cv2.createTrackbar("Thickness", "Gadog Smart System", 2, 10, lambda x: None)
cv2.createTrackbar("Opacity", "Gadog Smart System", 4, 10, lambda x: None)

print("KONTROL: Tekan 'L' (Lane), 'S' (Drop-off), 'D' (Redlight).")
print("Tekan 'C' untuk clear area. 'Q' untuk keluar.")

while cap.isOpened():
    success, frame = cap.read()
    if not success: break
    
    # Ambil nilai dari Trackbar (minimal 1 agar garis tidak hilang)
    line_thickness = max(1, cv2.getTrackbarPos("Thickness", "Gadog Smart System"))
    alpha = cv2.getTrackbarPos("Opacity", "Gadog Smart System") / 10.0

    # 3. Jalankan AI
    res_traffic = model_traffic.track(frame, persist=True, conf=0.25, iou=0.5, imgsz=640)
    res_human = model_human.track(frame, persist=True, classes=[0], conf=0.3)

    # Simpan koordinat manusia
    human_coords = []
    if res_human[0].boxes.xyxy is not None:
        human_coords = res_human[0].boxes.xyxy.cpu().numpy()

    # ==========================================
    # SOLUSI: KEMBALIKAN KOTAK BAWAAN YOLO
    # ==========================================
    # Gambar kotak kendaraan
    annotated_frame = res_traffic[0].plot()
    # Tumpuk gambar kotak manusia di atasnya
    annotated_frame = res_human[0].plot(img=annotated_frame)
    # ==========================================

    overlay = annotated_frame.copy()

    # 4. Gambar Area (Polygon)
    colors = {'L': (255, 0, 0), 'S': (0, 255, 0), 'D': (0, 0, 255)}
    for key, points in polygons.items():
        if len(points) > 1:
            pts = np.array(points, np.int32)
            cv2.fillPoly(overlay, [pts], colors[key])
            cv2.polylines(annotated_frame, [pts], True, colors[key], line_thickness)
    
    # Efek Transparan
    cv2.addWeighted(overlay, alpha, annotated_frame, 1 - alpha, 0, annotated_frame)

    # 5. Analisa Pelanggaran
    if res_traffic[0].boxes.id is not None:
        boxes = res_traffic[0].boxes.xyxy.cpu().numpy()
        clss = res_traffic[0].boxes.cls.cpu().numpy()
        ids = res_traffic[0].boxes.id.cpu().numpy()

        for box, cls, id in zip(boxes, clss, ids):
            label = model_traffic.names[int(cls)]
            x_c, y_b = int((box[0] + box[2]) / 2), int(box[3])
            
            # --- Pelanggaran Jalur Khusus (L) ---
            if len(polygons['L']) > 2:
                if cv2.pointPolygonTest(np.array(polygons['L']), (x_c, y_b), False) >= 0:
                    if label not in ['Bus', 'Two Wheeler']:
                        cv2.putText(annotated_frame, f"DANGER: {label} Jalur Salah!", (x_c, y_b-10), 0, 0.6, (0,0,255), 2)

            # --- Pelanggaran Drop-off (S) & Redlight (D) ---
            for zone in ['S', 'D']:
                if len(polygons[zone]) > 2:
                    if cv2.pointPolygonTest(np.array(polygons[zone]), (x_c, y_b), False) >= 0:
                        if id not in timers:
                            timers[id] = {'start': time.time(), 'activity': False}
                        
                        # Cek interaksi dengan manusia
                        for h_box in human_coords:
                            dist = np.linalg.norm(np.array([x_c, y_b]) - np.array([(h_box[0]+h_box[2])/2, h_box[3]]))
                            if dist < 100:
                                timers[id]['activity'] = True
                        
                        elapsed = time.time() - timers[id]['start']
                        
                        # Tampilkan timer detik di atas kendaraan
                        cv2.putText(annotated_frame, f"{int(elapsed)}s", (int(box[0]), int(box[1])-20), 0, 0.7, (0,255,255), 2)

                        # Batas Waktu 60 Detik
                        if elapsed > 60:
                            msg = "DANGER: Overtime!" if zone == 'D' else "DANGER: Berhenti Terlalu Lama!"
                            cv2.putText(annotated_frame, msg, (int(box[0]), int(box[3])+20), 0, 0.6, (0,0,255), 2)
                            cv2.rectangle(annotated_frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0,0,255), 4)
                    else:
                        if id in timers: del timers[id]

    # Info UI di pojok kiri atas
    cv2.putText(annotated_frame, f"MODE: {current_key}", (10, 30), 0, 0.8, (255,255,255), 2)
    cv2.imshow("Gadog Smart System", annotated_frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'): break
    elif key in [ord('l'), ord('s'), ord('d')]: current_key = chr(key).upper()
    elif key == ord('c'): polygons[current_key] = []

cap.release()
cv2.destroyAllWindows()