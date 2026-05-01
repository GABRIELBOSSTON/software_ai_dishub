"""
insight_engine.py
=================
Modul Mesin Insight berbasis Rule-Based untuk Sistem CCTV AI Smart City.
Menghasilkan narasi analitik yang menggunakan bahasa sederhana dan mudah dimengerti.

Fungsi utama : get_ai_prediction(violation_stats, density, logs_data)
Fungsi warga : get_citizen_sentiment(count)
Versi        : 4.0.0
"""

import re
import random
from collections import Counter

# ---------------------------------------------------------------------------
# KONSTANTA THRESHOLD
# ---------------------------------------------------------------------------

BUS_LANE_LOW          = 3
BUS_LANE_MODERATE     = 8
BUS_LANE_HIGH         = 15

ILLEGAL_STOP_LOW      = 2
ILLEGAL_STOP_MODERATE = 6
ILLEGAL_STOP_HIGH     = 12

SUSPICIOUS_LOW        = 1
SUSPICIOUS_MODERATE   = 4
SUSPICIOUS_HIGH       = 8

# ---------------------------------------------------------------------------
# HELPER: PARSING LOG
# ---------------------------------------------------------------------------

def _parse_logs(logs_data: list[str]) -> dict:
    vehicle_classes     = Counter()
    busway_classes      = Counter()
    illegalstop_classes = Counter()
    dropoff_locations   = []
    id_counter          = Counter()

    pattern_class    = re.compile(r'\(([\w\s]+?)\)')
    pattern_id       = re.compile(r'ID:(\d+)')
    pattern_location = re.compile(r'di\s+([A-Za-z\s]+?)(?:\.|,|$)', re.IGNORECASE)

    for line in logs_data:
        classes_found = pattern_class.findall(line)
        for cls in classes_found:
            vehicle_classes[cls.strip()] += 1

        ids_found = pattern_id.findall(line)
        for vid in ids_found:
            id_counter[vid] += 1

        upper = line.upper()
        if 'BUSWAY' in upper or 'JALUR' in upper:
            for cls in classes_found:
                busway_classes[cls.strip()] += 1

        if 'NGETEM' in upper or 'PARKIR LIAR' in upper or 'ILLEGAL STOP' in upper:
            for cls in classes_found:
                illegalstop_classes[cls.strip()] += 1

        if 'DROP' in upper or 'SUSPICIOUS' in upper:
            loc = pattern_location.search(line)
            if loc:
                dropoff_locations.append(loc.group(1).strip())

    repeat_offenders = {vid for vid, count in id_counter.items() if count > 1}

    return {
        'vehicle_classes'    : vehicle_classes,
        'busway_classes'     : busway_classes,
        'illegalstop_classes': illegalstop_classes,
        'dropoff_locations'  : dropoff_locations,
        'repeat_offenders'   : repeat_offenders,
    }


def _dominant_class(counter: Counter, top_n: int = 2) -> str:
    if not counter:
        return "tidak teridentifikasi"
    top = counter.most_common(top_n)
    return " dan ".join([f"{cls}" for cls, cnt in top])


# ---------------------------------------------------------------------------
# FUNGSI UTAMA: AI PREDICTION
# ---------------------------------------------------------------------------

def get_ai_prediction(
    violation_stats: dict,
    density: int,
    logs_data: list[str] = None
) -> tuple[str, int]:
    """
    Menghasilkan teks insight yang mudah dipahami orang awam tanpa istilah teknis.
    Fokus pada jenis pelanggaran dan kejadian di lapangan, bukan sekadar kemacetan.
    """

    if logs_data is None:
        logs_data = []

    # -- Ekstrak variabel statistik --
    bus_lane     = violation_stats.get('bus_lane', 0)
    illegal_stop = violation_stats.get('illegal_stop', 0)
    suspicious   = violation_stats.get('suspicious_dropoff', 0)

    # -- Parsing log --
    parsed       = _parse_logs(logs_data)
    illstop_dom  = _dominant_class(parsed['illegalstop_classes'])
    repeat_count = len(parsed['repeat_offenders'])
    dropoff_locs = parsed['dropoff_locations']
    blur_count   = parsed['vehicle_classes'].get('Blur Number Plate', 0)

    truck_count  = parsed['vehicle_classes'].get('Truck', 0)
    bus_count    = parsed['vehicle_classes'].get('Bus', 0)
    car_count    = parsed['vehicle_classes'].get('Car', 0)
    tw_count     = parsed['busway_classes'].get('Two Wheeler', 0)
    heavy_count  = truck_count + bus_count

    # =======================================================================
    # SKENARIO LALU LINTAS (BAHASA SEDERHANA & MUDAH DIMENGERTI)
    # =======================================================================

    # 1. PELAT NOMOR DITUTUPI / BURAM
    if blur_count >= 1:
        insight = (
            f"⚠️ Peringatan: Sistem AI mendeteksi ada {blur_count} kendaraan yang pelat nomornya buram, tertutup, atau "
            f"tidak terbaca dengan jelas. Ini bisa jadi upaya sengaja dari pengemudi untuk menghindari kamera tilang "
            f"elektronik (ETLE). Sangat disarankan agar petugas mengecek rekaman CCTV ini lebih detail untuk melacak "
            f"identitas kendaraan tersebut agar aturan tetap bisa ditegakkan."
        )
        return insight, 95

    # 2. AKTIVITAS NAIK-TURUN PENUMPANG BERBAHAYA (Di luar area ngetem/buslane)
    elif suspicious >= SUSPICIOUS_LOW:
        lokasi_str = ", ".join(set(dropoff_locs[:3])) if dropoff_locs else "area sekitar jalan"
        insight = (
            f"🚨 Pantauan Keamanan:  Sistem AI menemukan ada {suspicious} aktivitas naik-turun penumpang atau bongkar "
            f"muat barang di lokasi yang tidak aman ({lokasi_str}). Tindakan berhenti sembarangan di luar zona hijau ini "
            f"sangat berbahaya bagi pejalan kaki dan pengendara lain di sekitarnya. Mohon agar petugas di ruang kontrol "
            f"segera memberikan teguran melalui pengeras suara CCTV untuk mengusir kendaraan tersebut."
        )
        return insight, 88

    # 3. KENDARAAN BOLAK-BALIK MELANGGAR
    elif bus_lane >= 1 and repeat_count >= 2:
        insight = (
            f"👀 Perhatian Khusus: Sistem mencatat ada {repeat_count} kendaraan yang sama tertangkap kamera bolak-balik "
            f"melakukan pelanggaran (terutama menerobos jalur busway). Pengemudi ini sepertinya sengaja mengabaikan aturan "
            f"karena merasa tidak ada petugas yang berjaga secara fisik. Data kendaraan ini harus segera ditandai untuk "
            f"diberikan sanksi tilang yang lebih tegas agar memberikan efek jera."
        )
        return insight, 90

    # 4. BANYAK MOTOR MASUK JALUR BUSWAY
    elif bus_lane >= BUS_LANE_MODERATE and tw_count > sum(v for k, v in parsed['busway_classes'].items() if k != 'Two Wheeler'):
        insight = (
            f"🚌 Jalur Busway Diserobot: Saat ini jalur khusus busway sedang diserbu oleh gerombolan sepeda motor "
            f"(tercatat {tw_count} motor masuk ke jalur khusus). Biasanya, jika satu motor nekat masuk dan dibiarkan, motor "
            f"lain di belakangnya akan ikut-ikutan. Hal ini tentu sangat mengganggu kelancaran operasional Bus TransJakarta. "
            f"Disarankan untuk mengarahkan petugas lapangan menjaga pintu masuk jalur ini."
        )
        return insight, 92

    # 5. KENDARAAN NGETEM TERLALU LAMA
    elif illegal_stop >= ILLEGAL_STOP_LOW:
        insight = (
            f"🅿️ Parkir Liar / Ngetem: Sistem mendeteksi ada {illegal_stop} kendaraan yang berhenti terlalu lama atau "
            f"ngetem di area terlarang (Lampu Merah/Pinggir Jalan). Kendaraan yang didominasi oleh kelas {illstop_dom} ini "
            f"membuat lajur jalan menjadi lebih sempit dan merugikan pengguna jalan lainnya. Diperlukan tindakan cepat dari "
            f"petugas untuk meminta kendaraan tersebut segera jalan terus."
        )
        return insight, 89

    # 6. DOMINASI KENDARAAN BESAR (Truk/Bus)
    elif heavy_count > car_count and heavy_count >= 4:
        insight = (
            f"🚚 Banyak Kendaraan Besar: Lalu lintas di titik ini sedang banyak dilewati oleh kendaraan berukuran besar "
            f"yaitu Truk ({truck_count} unit) dan Bus ({bus_count} unit). Meskipun tidak ada pelanggaran aturan yang mencolok, "
            f"kehadiran banyak kendaraan besar ini secara alami akan membuat pergerakan lalu lintas menjadi lebih lambat. "
            f"Pastikan kendaraan angkutan barang ini melintas sesuai dengan jam operasional yang diizinkan."
        )
        return insight, 85

    # 7. PELANGGARAN JALUR BUSWAY (Umum)
    elif bus_lane >= 1:
        insight = (
            f"⚠️ Pelanggaran Marka Jalan: Tercatat ada {bus_lane} pelanggaran di mana kendaraan pribadi nekat masuk ke "
            f"dalam jalur khusus Busway. Jalur ini seharusnya steril agar angkutan massal bisa melaju tanpa hambatan. "
            f"Petugas disarankan untuk memproses bukti rekaman kamera ini ke dalam sistem tilang elektronik (ETLE)."
        )
        return insight, 86

    # 8. JALANAN AMAN DAN TERTIB
    elif bus_lane == 0 and illegal_stop == 0 and suspicious == 0:
        insight = (
            f"✅ Kondisi Aman Terkendali: Pantauan CCTV saat ini menunjukkan lalu lintas yang sangat tertib. Sistem AI "
            f"sama sekali tidak menemukan adanya kendaraan yang menerobos jalur busway, tidak ada yang ngetem sembarangan, "
            f"ataupun aktivitas naik-turun penumpang yang berbahaya di tengah jalan. Kepatuhan pengemudi di titik ini "
            f"sedang sangat baik."
        )
        return insight, 98

    # 9. KONDISI AWAL (Belum banyak data)
    else:
        insight = (
            f"🔄 Pantauan Aktif: Sistem AI sedang aktif menganalisis pergerakan lalu lintas. Sejauh ini baru tercatat "
            f"pelanggaran skala kecil yang belum mengganggu ketertiban umum (Jalur Busway: {bus_lane}, Ngetem: {illegal_stop}, "
            f"Drop-off Berbahaya: {suspicious}). Petugas disarankan untuk terus membiarkan AI bekerja dan memantau apakah "
            f"akan ada lonjakan pelanggaran beberapa menit ke depan."
        )
        return insight, 75


# ---------------------------------------------------------------------------
# FUNGSI SENTIMEN WARGA
# ---------------------------------------------------------------------------

def get_citizen_sentiment(count=2):
    """
    Menghasilkan data sentimen simulasi (mock) dari warga sekitar.
    """
    templates = [
        {"pesan": "Hati-hati genangan air di titik ini setelah hujan tadi.", "warna": "red"},
        {"pesan": "Sudah lancar, petugas sudah di lokasi melakukan penanganan.", "warna": "green"},
        {"pesan": "Ada mobil mogok di lajur kanan, bikin macet panjang ke belakang.", "warna": "orange"},
        {"pesan": "Jalur busway mulai diserobot motor, mohon petugas ditindak.", "warna": "orange"},
        {"pesan": "Lampu merahnya mati, lalu lintas jadi semrawut.", "warna": "red"},
        {"pesan": "Terima kasih Dishub, rekayasa lalu lintasnya bikin arus lebih lancar.", "warna": "green"}
    ]
    
    selected = random.sample(templates, count)
    
    names = ["Andi Saputra", "Rina M.", "Budi Santoso", "Siti Aisyah", "Kelvin W.", "Agus T."]
    
    results = []
    for item in selected:
        nama = random.choice(names)
        inisial = "".join([n[0] for n in nama.split()[:2]]).upper()
        waktu = f"{random.randint(1, 59)}m ago"
        
        results.append({
            "inisial": inisial,
            "nama": nama,
            "pesan": item["pesan"],
            "warna": item["warna"],
            "waktu": waktu
        })
        
    return results