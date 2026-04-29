import cv2
from flask import Flask, Response
import time

app = Flask(__name__)

def generate_live_stream():
    """Mensimulasikan CCTV yang menyala 24/7 (Looping Video)"""
    while True:
        # Ganti path ini sesuai dengan video target kamu
        cap = cv2.VideoCapture("videos/cctv_gadog.mp4") 
        
        # Ambil FPS asli video agar stream tidak terlalu cepat/lambat
        fps = cap.get(cv2.CAP_PROP_FPS)
        sleep_time = 1 / fps if fps > 0 else 0.033

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break # Video habis? Ulangi lagi dari awal (Loop)
            
            # Encode frame jadi format JPG Stream (MJPEG)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            
            # Kirim frame ke jaringan
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Simulasi delay natural CCTV
            time.sleep(sleep_time)
            
        cap.release()

@app.route('/stream/gadog_01')
def stream_gadog():
    return Response(generate_live_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print("📡 SERVER DISHUB MENYALA!")
    print("🎥 URL Stream CCTV: http://127.0.0.1:5001/stream/gadog_01")
    # Kita jalankan di port 5001 agar tidak bentrok dengan app.py (port 5000)
    app.run(port=5001, debug=False, threaded=True)

    