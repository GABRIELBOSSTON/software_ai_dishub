# 🚦 USBA (TrafficAI) — Intelligent Traffic Enforcement & Behaviour Analysis

![Project Status](https://img.shields.io/badge/Status-MVP%20%2F%20Prototype-success)
![AI Model](https://img.shields.io/badge/AI_Model-YOLOv8%20%26%20Ollama%20LLM-blue)
![Framework](https://img.shields.io/badge/Backend-Flask-black)
![UI](https://img.shields.io/badge/UI-Dark%20Mode%20%2B%203D%20Glassmorphism-purple)

**USBA (Suara Warga Jakarta / TrafficAI)** adalah platform inovatif berbasis *Computer Vision* dan *Generative AI* (LLM) yang dirancang untuk merombak cara pemerintah kota melakukan pengawasan lalu lintas. Kami mentransformasi kamera CCTV pasif milik kota dan laporan warga menjadi mesin analitik proaktif secara *real-time*.

> 🏆 **Proyek ini dikembangkan untuk memecahkan Case 1: Intelligent Traffic Enforcement and Behaviour Analysis pada kompetisi AI Open 2026.**

---

## ✨ Jelajahi Fitur Utama Kami

### 1. 📢 Portal Pelaporan Warga & Dashboard Interaktif (USBA)
Menjembatani kesenjangan antara keluhan masyarakat dan tindakan pemerintah. Warga dapat melaporkan pelanggaran (Angkot ngetem, parkir liar, menerobos busway) secara *real-time* dengan antarmuka yang modern, cepat, dan transparan.
![USBA Dashboard](foto/44444444Screenshot%202026-06-22%20123010.png)

### 2. 👁️ Live CCTV Vision Tracking (YOLO AI)
Menggunakan algoritma *Deep Learning* untuk mendeteksi, mengklasifikasi, dan melacak kendaraan secara langsung dari *stream* CCTV publik. Dilengkapi dengan fitur penggambaran zona pelanggaran interaktif (*Bus Lane, Ngetem Area*), serta ekstraksi plat nomor (ANPR).
![Live Vision Tracking](foto/22222222222222Screenshot%202026-06-22%20122858.jpg)

### 3. 🧠 Analytics Workspace & Predictive Insights (RAG-LLM)
Ini adalah "otak" dari sistem kami. Panel ini tidak hanya menampilkan log hasil *scan* CCTV secara *live*, tetapi juga mengintegrasikan asisten AI (Ollama) yang mampu memberikan **Predictive Insights** menggunakan bahasa manusia yang natural berdasarkan situasi jalan saat itu juga.
![Analytics Workspace](foto/3333333333Screenshot%202026-06-22%20122935.jpg)

### 4. 🗺️ Real-Time Hotspot Mapping
Sistem secara otomatis mengubah log pelanggaran visual dan keluhan warga menjadi peta panas spasial terintegrasi. Pengambil kebijakan dapat dengan mudah melihat titik-titik rawan macet atau area invasi jalur khusus langsung dari atas peta Jakarta.
![Hotspot Mapping](foto/111Screenshot%202026-06-22%20122639.jpg)

---

## 🛠️ Arsitektur Teknologi

Sistem ini dirancang dengan arsitektur *hardware-agnostic* yang berjalan sangat efisien di jaringan lokal (*on-premise*) demi menjaga keamanan dan privasi data instansi:
- **Frontend UI/UX:** HTML5, Vanilla JavaScript, Custom CSS (Dark Mode & Glassmorphism).
- **Backend Routing:** Python (Flask).
- **Vision Engine:** YOLO (*You Only Look Once*) / OpenCV untuk pemrosesan *frame* spasial.
- **Cognitive Analytics:** LLM Lokal via Ollama (`deepseek-coder-v2`) dengan metode *Retrieval-Augmented Generation* (RAG) untuk merangkum log data menjadi wawasan prediktif.

---

## 🚀 Panduan Instalasi Lokal

Ingin mencoba proyek ini di komputer Anda? Ikuti langkah mudah berikut:

1. **Clone Repositori:**
```bash
   git clone [https://github.com/username-anda/usba-traffic-ai.git](https://github.com/username-anda/usba-traffic-ai.git)
   cd usba-traffic-ai