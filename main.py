import cv2
from ultralytics import YOLO

# 1. Load Model
model = YOLO("weights/best.pt")

video_path = "videos/cctv_gadog.mp4"
cap = cv2.VideoCapture(video_path)

while cap.isOpened():
    success, frame = cap.read()
    
    if success:
        # 2. GUNAKAN TRACK BUKAN PREDICT
        # conf=0.25 -> Biar yang jauh ketangkep
        # iou=0.5 -> Biar motor & mobil dempet nggak bingung
        # persist=True -> Wajib biar dia inget ID objeknya
        results = model.track(frame, persist=True, conf=0.25, iou=0.5, imgsz=640)

        # 3. Visualisasi
        annotated_frame = results[0].plot()

        # 4. Tampilkan
        cv2.imshow("Gadog Smart Traffic - Pro Tracking", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    else:
        break

cap.release()
cv2.destroyAllWindows()