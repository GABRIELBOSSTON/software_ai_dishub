"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          URBAN SPATIAL BEHAVIOR ANALYTICS — INSIGHT ENGINE                 ║
║          Smart City Command Center · Sistem Analitik Perilaku Spasial       ║
║          Version: 2.4.1 · Python 3.9+                                       ║
║          Author  : Senior Data Science Division                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Modul standalone ini TIDAK bergantung pada Flask/app.py.
Tugasnya tunggal: menganalisis data mentah dan menghasilkan kalimat insight
profesional serta data sentimen warga yang dinamis dan tidak berulang.

Ekspor Publik:
  - get_ai_prediction(violation_count, current_density, zone_type) → (str, float)
  - get_citizen_sentiment()                                          → list[dict]
"""

from __future__ import annotations

import random
import hashlib
import datetime
from dataclasses import dataclass, field
from typing import Literal, Optional

# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTA SISTEM
# ─────────────────────────────────────────────────────────────────────────────

_ZONE_ALIASES: dict[str, str] = {
    "highway":       "koridor arteri primer",
    "arterial":      "jalur arteri sekunder",
    "residential":   "zona permukiman padat",
    "commercial":    "kawasan komersial aktif",
    "industrial":    "zona industri terpadu",
    "school_zone":   "kawasan perlindungan sekolah",
    "hospital_zone": "kawasan buffer rumah sakit",
    "bus_corridor":  "koridor angkutan massal BRT",
    "market":        "kawasan pasar tradisional",
    "toll_gate":     "titik akses tol berbayar",
    "bridge":        "infrastruktur jembatan kritis",
    "tunnel":        "terowongan akses bawah tanah",
    "unknown":       "segmen jalan tidak terklasifikasi",
}

_SEVERITY_THRESHOLDS = {
    "critical":  {"violation": 25, "density": 85},
    "high":      {"violation": 15, "density": 70},
    "moderate":  {"violation": 7,  "density": 50},
    "low":       {"violation": 3,  "density": 30},
    "normal":    {"violation": 0,  "density": 0},
}

_ACCURACY_MAP = {
    "critical":  (88.0, 96.5),
    "high":      (81.0, 89.5),
    "moderate":  (73.0, 82.5),
    "low":       (65.0, 75.5),
    "normal":    (58.0, 68.5),
}


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASS INTERNAL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _SpatialContext:
    """Representasi konteks spasial yang diekstrak dari parameter input."""
    violation_count:  int
    current_density:  float
    zone_type:        str
    zone_label:       str
    severity:         str
    accuracy_range:   tuple[float, float]
    hour:             int               = field(default_factory=lambda: datetime.datetime.now().hour)
    day_of_week:      int               = field(default_factory=lambda: datetime.datetime.now().weekday())
    seed:             int               = field(default=0)

    @property
    def is_peak_hour(self) -> bool:
        return (6 <= self.hour <= 9) or (16 <= self.hour <= 20)

    @property
    def is_weekend(self) -> bool:
        return self.day_of_week >= 5

    @property
    def density_label(self) -> str:
        d = self.current_density
        if d >= 85:  return "sangat kritis"
        if d >= 70:  return "padat kritis"
        if d >= 50:  return "cukup padat"
        if d >= 30:  return "moderat"
        return "lancar"

    @property
    def violation_label(self) -> str:
        v = self.violation_count
        if v >= 25:  return "masif"
        if v >= 15:  return "tinggi"
        if v >= 7:   return "sedang"
        if v >= 3:   return "rendah"
        return "minimal"

    def derive_accuracy(self) -> float:
        lo, hi = self.accuracy_range
        r = random.Random(self.seed + self.violation_count + int(self.current_density))
        return round(r.uniform(lo, hi), 1)


# ─────────────────────────────────────────────────────────────────────────────
# BANK KALIMAT — INSIGHT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class _InsightBank:
    """
    Repositori kalimat insight terstruktur berdasarkan tingkat keparahan,
    jenis zona, dan konteks temporal. Setiap template menggunakan placeholder
    yang diisi secara dinamis sehingga output tidak pernah identik.
    """

    # ── CRITICAL ─────────────────────────────────────────────────────────────
    CRITICAL_TEMPLATES: list[str] = [
        (
            "SIAGA KRITIS · Deteksi multi-node mengonfirmasi saturasi arus di {zone_label} "
            "dengan indeks kepadatan {density:.1f}% — melampaui ambang batas operasional {threshold}%. "
            "Akumulasi {violation} insiden pelanggaran dalam periode observasi memicu proyeksi "
            "kemacetan total dalam rentang {eta} menit. Protokol Darurat Lalu Lintas Level-2 direkomendasikan."
        ),
        (
            "Anomali spasial kategori MERAH teridentifikasi pada {zone_label}. "
            "Kepadatan aktual {density:.1f}% berkorelasi positif dengan lonjakan pelanggaran "
            "sebesar {violation} kejadian, membentuk pola congestive cascade yang berpotensi "
            "melumpuhkan {downstream_zone} dalam {eta} menit ke depan. "
            "Intervensi manajer lalu lintas bersertifikat diprioritaskan segera."
        ),
        (
            "Sistem analitik geospasial mendeteksi {violation} titik pelanggaran aktif "
            "dengan rasio okupansi {density:.1f}% di {zone_label}. "
            "Model prediktif LSTM mengindikasikan probabilitas gridlock radial mencapai {accuracy}% "
            "apabila tidak ada intervensi dalam {eta} menit. "
            "Koordinasi dengan pusat kendali Polda Metro Jaya disarankan."
        ),
        (
            "PERINGATAN EKSTREM · Konsentrasi pelanggaran ({violation} insiden) pada {zone_label} "
            "menciptakan zona dead-lock parsial. Indeks mobilitas turun {drop_pct}% dari baseline harian. "
            "Pola arus menunjukkan bottleneck multivariat — analisis shockwave propagation "
            "memprediksi dampak rambatan ke {downstream_zone} dalam {eta} menit."
        ),
        (
            "Sensor CCTV AI melaporkan saturasi penuh pada {zone_label}. "
            "Kepadatan kumulatif {density:.1f}% bersama {violation} pelanggaran aktif "
            "mengaktifkan skenario Level-3 dalam matriks risiko infrastruktur. "
            "Deployment petugas lapangan di {sector} node diutamakan. "
            "ETA normalisasi arus: {eta}–{eta2} menit pasca-intervensi."
        ),
    ]

    # ── HIGH ──────────────────────────────────────────────────────────────────
    HIGH_TEMPLATES: list[str] = [
        (
            "Indikator mobilitas pada {zone_label} menunjukkan tekanan signifikan — "
            "densitas {density:.1f}% dengan {violation} pelanggaran terdokumentasi "
            "menghasilkan skor risiko agregat TINGGI. "
            "Jika tren eskalasi berlanjut selama {eta} menit, model regresi spasial "
            "memprediksi penurunan throughput kendaraan hingga {drop_pct}%."
        ),
        (
            "Analisis pola arus real-time mengidentifikasi tekanan kapasitas di {zone_label}. "
            "Dengan {violation} pelanggaran aktif dan kepadatan {density:.1f}%, "
            "headway kendaraan telah melebar melampaui toleransi {threshold} detik. "
            "Aktivasi manajemen sinyal adaptif di persimpangan terdekat direkomendasikan."
        ),
        (
            "Kluster pelanggaran {violation} unit pada {zone_label} berimplikasi pada "
            "degradasi level-of-service dari kategori C ke D berdasarkan standar HCM 2016. "
            "Kepadatan {density:.1f}% mendekati titik kritis operasional. "
            "Intervensi preventif dalam {eta} menit dapat mencegah transisi ke kondisi forced flow."
        ),
        (
            "Model anomali berbasis isolation forest mendeteksi deviasi {drop_pct}% "
            "dari pola historis di {zone_label}. "
            "Akumulasi {violation} pelanggaran aktif mendorong densitas ke {density:.1f}%, "
            "mengindikasikan potensi spillback ke segmen hulu dalam {eta} menit. "
            "Pemantauan intensif oleh operator shift II diperlukan."
        ),
        (
            "Frekuensi pelanggaran di {zone_label} meningkat {drop_pct}% dari rata-rata "
            "historis segmen ini. Kepadatan real-time {density:.1f}% mendekati batas "
            "kapasitas desain infrastruktur. Diperlukan koordinasi intra-instansi untuk "
            "mengaktifkan manajemen demand side guna mengurangi volume masuk ke koridor ini."
        ),
    ]

    # ── MODERATE ──────────────────────────────────────────────────────────────
    MODERATE_TEMPLATES: list[str] = [
        (
            "Kondisi lalu lintas di {zone_label} berada pada level operasional SEDANG. "
            "Tercatat {violation} pelanggaran dengan densitas {density:.1f}% — "
            "masih dalam koridor toleransi sistem, namun tren pertumbuhan {eta}-menit "
            "memerlukan kewaspadaan operator. Pemantauan pasif dipertahankan."
        ),
        (
            "Arus kendaraan di {zone_label} beroperasi di batas atas level-of-service B. "
            "Insiden pelanggaran sebanyak {violation} kejadian berpotensi memicu "
            "gangguan lokal apabila bertepatan dengan puncak waktu keberangkatan. "
            "Densitas saat ini: {density:.1f}%. Monitoring interval 5 menit dianjurkan."
        ),
        (
            "Analisis geospasial mencatat {violation} pelanggaran tersebar di {zone_label} "
            "dengan kepadatan moderat {density:.1f}%. Pola distribusi insiden belum membentuk "
            "kluster kritikal, namun granulasi temporal menunjukkan kecenderungan "
            "konsentrasi pada interval {eta} menit mendatang."
        ),
        (
            "Sistem scoring risiko menghasilkan nilai {accuracy:.0f} untuk segmen {zone_label}. "
            "Kepadatan {density:.1f}% bersama {violation} pelanggaran tercatat "
            "mengindikasikan kondisi stabil-dinamis. Rekomendasi: pertahankan cycle time "
            "sinyal eksisting dan tingkatkan resolusi sampling kamera ke interval 30 detik."
        ),
        (
            "Deteksi pelanggaran {violation} unit di {zone_label} berada dalam ambang "
            "pengelolaan rutin. Indeks kepadatan {density:.1f}% mencerminkan aktivitas "
            "normal untuk tipologi kawasan ini. Potensi eskalasi tetap ada "
            "apabila variabel eksogen (cuaca, event) mengintervensi dalam {eta} menit ke depan."
        ),
    ]

    # ── LOW ───────────────────────────────────────────────────────────────────
    LOW_TEMPLATES: list[str] = [
        (
            "Kondisi {zone_label} terpantau LANCAR dengan densitas rendah {density:.1f}%. "
            "Hanya {violation} insiden pelanggaran minor yang tercatat — "
            "tidak memerlukan intervensi aktif. Level-of-service berada pada kategori A. "
            "Sistem beroperasi dalam mode surveillance pasif."
        ),
        (
            "Segmen {zone_label} menunjukkan performa optimal: kepadatan {density:.1f}%, "
            "{violation} pelanggaran ringan. Throughput kendaraan sesuai proyeksi kapasitas desain. "
            "Tidak ada indikasi anomali spasial dalam window observasi 15 menit terakhir."
        ),
        (
            "Analitik arus menyimpulkan kondisi sub-kritis di {zone_label}. "
            "Volume lalu lintas dan {violation} catatan pelanggaran berada di bawah "
            "persentil ke-25 data historis harian. Densitas {density:.1f}% mengonfirmasi "
            "mobilitas tinggi. Rekomendasi: manfaatkan interval ini untuk pemeliharaan CCTV terjadwal."
        ),
    ]

    # ── NORMAL ────────────────────────────────────────────────────────────────
    NORMAL_TEMPLATES: list[str] = [
        (
            "Tidak ada anomali terdeteksi pada {zone_label}. "
            "Densitas {density:.1f}% dan nol pelanggaran signifikan mencerminkan "
            "kondisi lalulintas ideal. Sistem analitik beroperasi normal. "
            "Interval auto-refresh berikutnya: {eta} menit."
        ),
        (
            "Segmen {zone_label} berada dalam kondisi PRIMA — densitas {density:.1f}%, "
            "pelanggaran nihil. Data telemetri konsisten dengan baseline histori Senin–Jumat. "
            "Tidak diperlukan eskalasi. Operator disarankan memverifikasi kalibrasi sensor."
        ),
        (
            "Indeks mobilitas {zone_label} mencapai {accuracy:.0f}/100 — tertinggi dalam "
            "6 jam terakhir. Dengan densitas {density:.1f}% dan tanpa pelanggaran signifikan, "
            "koridor ini menjadi acuan performa bagi segmen paralel yang tengah dianalisis."
        ),
    ]

    # ── TEMPORAL OVERLAY (ditambahkan pada akhir insight) ────────────────────
    PEAK_HOUR_SUFFIX: list[str] = [
        " Kondisi diperburuk oleh periode jam sibuk yang tengah berlangsung.",
        " Puncak arus pagi/sore memperparah tekanan kapasitas eksisting.",
        " Intervensi harus memperhitungkan volume masukan dari koridor feeder yang aktif.",
        " Fluktuasi demand puncak mempersempit margin toleransi sistem.",
    ]

    WEEKEND_SUFFIX: list[str] = [
        " Pola akhir pekan memperlihatkan distribusi asal-tujuan yang berbeda dari hari kerja.",
        " Volume leisure-trip berkontribusi pada distribusi kepadatan yang tidak seragam.",
        " Trip rekreasi dan kegiatan komunal meningkatkan variabilitas prediksi model.",
    ]

    ZONE_SPECIFIC_PREFIX: dict[str, list[str]] = {
        "bus_corridor": [
            "Integritas headway BRT terganggu — ",
            "Pelanggaran jalur eksklusif bus terdeteksi — ",
            "Gangguan pada right-of-way angkutan massal — ",
        ],
        "school_zone": [
            "Pelanggaran kecepatan di zona proteksi pelajar — ",
            "Aktivitas antar-jemput tidak tertib di kawasan sekolah — ",
            "Risiko keselamatan pejalan kaki anak meningkat — ",
        ],
        "hospital_zone": [
            "Gangguan akses kendaraan darurat terdeteksi — ",
            "Kemacetan di koridor ambulans berpotensi kritis — ",
            "Clearance jalur emergensi memerlukan perhatian segera — ",
        ],
        "market": [
            "Aktivitas bongkar-muat tidak tertib di kawasan pasar — ",
            "Parkir liar pedagang kaki lima memperparah kondisi — ",
            "Gesekan pejalan kaki-kendaraan di area pasar meningkat — ",
        ],
        "bridge": [
            "Beban axle kumulatif pada infrastruktur jembatan perlu dipantau — ",
            "Kepadatan di struktur jembatan mendekati batas desain — ",
        ],
        "toll_gate": [
            "Antrian kendaraan melampaui kapasitas gardu tol — ",
            "Throughput gardu pembayaran tidak sebanding dengan volume masuk — ",
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# BANK DATA — SENTIMEN WARGA
# ─────────────────────────────────────────────────────────────────────────────

class _SentimentBank:
    """
    Repositori pesan simulasi sentimen warga — dirancang menyerupai
    laporan nyata melalui kanal CRM / Twitter / JAKI / WA Pengaduan.
    Setiap entri memiliki inisial, nama, pesan, dan warna kategori.
    """

    MESSAGES: list[dict] = [
        # ── KEMACETAN ──────────────────────────────────────────────────────
        {
            "inisial": "RS",
            "nama": "Rizki Santoso",
            "pesan": "Macet parah di Jl. Gatot Subroto arah Semanggi dari tadi jam 7 pagi, "
                     "belum bergerak sama sekali. Ada kecelakaan kah? Tolong info dong.",
            "warna": "red",
            "kategori": "kemacetan",
        },
        {
            "inisial": "DW",
            "nama": "Dewi Wijayanti",
            "pesan": "Antrian panjang di flyover Cawang, udah 45 menit nggak maju-maju. "
                     "Anak saya telat sekolah nih. Mohon ada solusi dari Dishub.",
            "warna": "red",
            "kategori": "kemacetan",
        },
        {
            "inisial": "BH",
            "nama": "Bagas Hermawan",
            "pesan": "Bundaran HI total macet dari arah Sudirman. Kayaknya ada demo "
                     "atau event ya? Tolong update status jalan dong min.",
            "warna": "orange",
            "kategori": "kemacetan",
        },
        {
            "inisial": "YP",
            "nama": "Yunita Pramesti",
            "pesan": "Tol dalam kota KM 8 arah Cawang merayap panjang banget. "
                     "Ini rutin tiap hari Senin, apakah ada rencana rekayasa lalu lintas?",
            "warna": "orange",
            "kategori": "kemacetan",
        },
        {
            "inisial": "MF",
            "nama": "Muhammad Fauzi",
            "pesan": "Persimpangan Kuningan City macet sampai ke Mampang. "
                     "Lampu merahnya kelamaan, siklus hijau terlalu singkat. "
                     "Tolong disesuaikan dong dengan volume kendaraan.",
            "warna": "orange",
            "kategori": "kemacetan",
        },

        # ── PARKIR LIAR / PELANGGARAN ──────────────────────────────────────
        {
            "inisial": "AS",
            "nama": "Andi Saputra",
            "pesan": "Trotoar di depan Pasar Senen penuh motor parkir liar, "
                     "pejalan kaki terpaksa jalan di badan jalan. Sangat berbahaya!",
            "warna": "red",
            "kategori": "parkir_liar",
        },
        {
            "inisial": "NR",
            "nama": "Nurul Rahmawati",
            "pesan": "Bahu jalan Jl. Mangga Dua Raya dijadikan tempat parkir mobil box "
                     "setiap pagi. Satu lajur terblokir total. Sudah lapor tapi belum ada tindakan.",
            "warna": "red",
            "kategori": "parkir_liar",
        },
        {
            "inisial": "SB",
            "nama": "Surya Bakti",
            "pesan": "Motor dan ojol ngetem di jalur TransJakarta Harmoni udah lama banget. "
                     "Busnya jadi terlambat terus. Kapan ada penertiban?",
            "warna": "orange",
            "kategori": "parkir_liar",
        },
        {
            "inisial": "LK",
            "nama": "Laila Kusuma",
            "pesan": "PKL di trotoar Jl. Sabang makin parah, lapak sampai ke badan jalan. "
                     "Arus pejalan kaki terganggu dan rawan kecelakaan saat malam.",
            "warna": "orange",
            "kategori": "parkir_liar",
        },

        # ── GENANGAN / BANJIR ─────────────────────────────────────────────
        {
            "inisial": "FK",
            "nama": "Fahmi Kurniawan",
            "pesan": "Genangan air di underpass Kemayoran setinggi lutut orang dewasa. "
                     "Banyak kendaraan mogok, lalu lintas lumpuh total. "
                     "Pompa airnya masih berfungsi nggak?",
            "warna": "blue",
            "kategori": "genangan",
        },
        {
            "inisial": "IW",
            "nama": "Indah Wahyuni",
            "pesan": "Jl. Casablanca depan mall banjir lagi setelah hujan 30 menit. "
                     "Ini sudah ketiga kalinya bulan ini. Drainase perlu diperbaiki segera.",
            "warna": "blue",
            "kategori": "genangan",
        },
        {
            "inisial": "TA",
            "nama": "Taufik Ardian",
            "pesan": "Gorong-gorong di Jl. Pluit Utama tersumbat, air meluap ke jalan. "
                     "Akses ke pelabuhan terganggu. Mohon perhatian Dinas PUPR.",
            "warna": "blue",
            "kategori": "genangan",
        },
        {
            "inisial": "HC",
            "nama": "Hendra Cipta",
            "pesan": "Banjir kilat di Tebet Barat pasca hujan deras sore tadi. "
                     "Kendaraan roda dua tidak bisa lewat. Butuh pompa mobile segera.",
            "warna": "blue",
            "kategori": "genangan",
        },

        # ── INFRASTRUKTUR JALAN ───────────────────────────────────────────
        {
            "inisial": "PL",
            "nama": "Priyo Laksono",
            "pesan": "Ada lubang besar di Jl. Daan Mogot KM 14. "
                     "Sudah ada yang nyaris jatuh. Tolong segera ditangani sebelum ada korban.",
            "warna": "red",
            "kategori": "infrastruktur",
        },
        {
            "inisial": "EM",
            "nama": "Eka Mutia",
            "pesan": "Marka jalan di Jl. Pondok Indah sudah pudar, terutama di tikungan. "
                     "Saat malam sangat membingungkan pengemudi. Kapan dicat ulang?",
            "warna": "orange",
            "kategori": "infrastruktur",
        },
        {
            "inisial": "GS",
            "nama": "Gunawan Setiadi",
            "pesan": "Lampu PJU di Jl. Pahlawan Revolusi mati sudah seminggu. "
                     "Area jadi gelap gulita dan rawan tindak kriminal. "
                     "Mohon segera diperbaiki.",
            "warna": "orange",
            "kategori": "infrastruktur",
        },
        {
            "inisial": "WR",
            "nama": "Wulan Ramadhani",
            "pesan": "Traffic light di persimpangan Kalimalang tidak sinkron, "
                     "nyala semua merah di keempat arah selama 5 menit. "
                     "Pengendara bingung dan mulai berdesakan.",
            "warna": "red",
            "kategori": "infrastruktur",
        },

        # ── ANGKUTAN UMUM ─────────────────────────────────────────────────
        {
            "inisial": "AT",
            "nama": "Agus Triyanto",
            "pesan": "TransJakarta Koridor 1 headway-nya 20 menit lebih di jam sibuk. "
                     "Halte Tosari penuh sesak sampai ke luar pagar. "
                     "Tolong tambah armada.",
            "warna": "orange",
            "kategori": "angkutan_umum",
        },
        {
            "inisial": "RO",
            "nama": "Rita Oktavia",
            "pesan": "Bus Mikrotrans di rute JAK-01 jarang banget. "
                     "Sudah nunggu 40 menit, tidak ada satu pun yang lewat. "
                     "Apakah sudah tidak beroperasi?",
            "warna": "orange",
            "kategori": "angkutan_umum",
        },
        {
            "inisial": "ZA",
            "nama": "Zulkifli Anwar",
            "pesan": "MRT sudah sangat membantu, tapi tangga stasiun Blok M "
                     "eskalatornya mati lagi. Difabel dan lansia kesulitan. "
                     "Kapan diperbaiki?",
            "warna": "blue",
            "kategori": "angkutan_umum",
        },

        # ── KESELAMATAN PEJALAN KAKI ──────────────────────────────────────
        {
            "inisial": "NA",
            "nama": "Nadia Anggraini",
            "pesan": "Zebra cross di depan SD Menteng Pulo tidak dihormati kendaraan. "
                     "Anak-anak jadi takut menyeberang. Butuh petugas atau traffic cone.",
            "warna": "red",
            "kategori": "keselamatan",
        },
        {
            "inisial": "DS",
            "nama": "Dani Surya",
            "pesan": "Trotoar Jl. M.H. Thamrin masih banyak yang rusak "
                     "pasca proyek revitalisasi. Paving block terangkat, "
                     "berbahaya buat pejalan kaki.",
            "warna": "orange",
            "kategori": "keselamatan",
        },

        # ── PUJIAN / APRESIASI ────────────────────────────────────────────
        {
            "inisial": "CP",
            "nama": "Citra Permata",
            "pesan": "Penertiban parkir liar di Jl. Sabang tadi pagi sangat efektif! "
                     "Jalan jadi lancar dan trotoar kembali bersih. Terima kasih Dishub!",
            "warna": "green",
            "kategori": "apresiasi",
        },
        {
            "inisial": "HA",
            "nama": "Hadi Atmaja",
            "pesan": "Rekayasa lalu lintas satu arah di kawasan Tanah Abang "
                     "sangat membantu mengurangi kemacetan. Harap dipertahankan "
                     "dan dievaluasi untuk jalan-jalan lain.",
            "warna": "green",
            "kategori": "apresiasi",
        },
        {
            "inisial": "MR",
            "nama": "Maya Rosita",
            "pesan": "Smart traffic light di persimpangan Rasuna Said bekerja sangat baik, "
                     "antrian jauh lebih singkat dari biasanya. Ini inovasi yang patut diperluas!",
            "warna": "green",
            "kategori": "apresiasi",
        },
        {
            "inisial": "BS",
            "nama": "Budi Setiawan",
            "pesan": "Petugas Dishub yang berjaga di Bundaran Senayan sangat responsif "
                     "dan profesional. Arus kendaraan terkendali dengan baik. Salut!",
            "warna": "green",
            "kategori": "apresiasi",
        },

        # ── LAPORAN KECELAKAAN ────────────────────────────────────────────
        {
            "inisial": "KS",
            "nama": "Kelvin Susanto",
            "pesan": "Ada kecelakaan minor di Jl. Rasuna Said depan Kuningan City, "
                     "2 motor terlibat. Tidak ada korban jiwa, tapi arus terganggu "
                     "karena kendaraan berhenti menonton.",
            "warna": "red",
            "kategori": "kecelakaan",
        },
        {
            "inisial": "VN",
            "nama": "Vina Novitasari",
            "pesan": "Truk ugal-ugalan di Tol Jagorawi KM 6 hampir menyerempet "
                     "beberapa kendaraan. Nomor polisi sudah saya foto. "
                     "Ke mana harus dilaporkan?",
            "warna": "red",
            "kategori": "kecelakaan",
        },

        # ── PERMINTAAN INFORMASI ──────────────────────────────────────────
        {
            "inisial": "TH",
            "nama": "Tiara Handayani",
            "pesan": "Apakah ada rekayasa lalu lintas untuk marathon besok pagi? "
                     "Rute saya biasanya lewat Jl. Sudirman. Minta info resminya dong.",
            "warna": "blue",
            "kategori": "informasi",
        },
        {
            "inisial": "RN",
            "nama": "Rudi Nugroho",
            "pesan": "Jam berapa proyek galian di Jl. TB Simatupang selesai? "
                     "Sudah seminggu satu lajur tutup, kapan dibuka lagi? "
                     "Ada informasi estimasi penyelesaian?",
            "warna": "blue",
            "kategori": "informasi",
        },
        {
            "inisial": "SP",
            "nama": "Siti Purwanti",
            "pesan": "Sistem OK-Otrip sering error saat tap kartu di halte Dukuh Atas. "
                     "Apakah ada gangguan teknis? Penumpang menumpuk dan tidak bisa masuk.",
            "warna": "orange",
            "kategori": "informasi",
        },
    ]

    # Waktu relatif yang akan dipilih secara acak
    TIME_OPTIONS: list[str] = [
        "just now", "1m ago", "2m ago", "3m ago", "5m ago",
        "7m ago", "10m ago", "12m ago", "15m ago", "18m ago",
        "20m ago", "25m ago", "30m ago", "35m ago", "40m ago",
        "45m ago", "50m ago", "1h ago", "1h 10m ago", "1h 20m ago",
    ]


# ─────────────────────────────────────────────────────────────────────────────
# CORE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class InsightEngine:
    """
    Mesin analitik utama Urban Spatial Behavior Analytics.

    Diinstansiasi sekali (singleton-friendly) dan dapat dipanggil
    berkali-kali tanpa state yang persisten antar pemanggilan.
    """

    def __init__(self, seed_offset: int = 0):
        self._seed_offset = seed_offset
        self._bank = _InsightBank()
        self._sentiment_bank = _SentimentBank()

    # ── PRIVATE HELPERS ───────────────────────────────────────────────────────

    @staticmethod
    def _classify_severity(violation_count: int, current_density: float) -> str:
        """Menentukan tingkat keparahan berdasarkan threshold dual-parameter."""
        for level, thresholds in _SEVERITY_THRESHOLDS.items():
            if violation_count >= thresholds["violation"] or \
               current_density >= thresholds["density"]:
                return level
        return "normal"

    @staticmethod
    def _resolve_zone(zone_type: str) -> str:
        """Menerjemahkan kode zona ke label deskriptif Bahasa Indonesia."""
        return _ZONE_ALIASES.get(zone_type.lower(), _ZONE_ALIASES["unknown"])

    @staticmethod
    def _build_seed(violation_count: int, density: float, zone_type: str) -> int:
        """Membangun seed deterministik agar output konsisten per input unik."""
        raw = f"{violation_count}:{density:.2f}:{zone_type}:{datetime.datetime.now().minute}"
        return int(hashlib.md5(raw.encode()).hexdigest()[:8], 16)

    def _get_template_pool(self, severity: str) -> list[str]:
        """Mengembalikan pool template yang sesuai dengan tingkat keparahan."""
        pools = {
            "critical": self._bank.CRITICAL_TEMPLATES,
            "high":     self._bank.HIGH_TEMPLATES,
            "moderate": self._bank.MODERATE_TEMPLATES,
            "low":      self._bank.LOW_TEMPLATES,
            "normal":   self._bank.NORMAL_TEMPLATES,
        }
        return pools.get(severity, self._bank.NORMAL_TEMPLATES)

    @staticmethod
    def _fill_template(template: str, ctx: _SpatialContext, accuracy: float) -> str:
        """Mengisi placeholder dalam template dengan nilai kontekstual dinamis."""
        rng = random.Random(ctx.seed)

        downstream_candidates = [
            "Koridor Kuningan", "Segmen Grogol", "Node Semanggi",
            "Interchange Cawang", "Simpul Blok M", "Akses Pulogadung",
            "Ramp Pluit", "Interchange Halim", "Segmen Pancoran",
        ]
        sector_candidates = [
            "utara", "selatan", "barat", "timur",
            "tengah", "A", "B", "C", "alfa", "bravo",
        ]

        eta = rng.randint(8, 22)
        eta2 = eta + rng.randint(5, 12)
        drop_pct = round(rng.uniform(8.5, 34.5), 1)
        threshold_val = rng.choice([75, 80, 85, 90])

        return template.format(
            zone_label=ctx.zone_label,
            density=ctx.current_density,
            violation=ctx.violation_count,
            accuracy=accuracy,
            eta=eta,
            eta2=eta2,
            drop_pct=drop_pct,
            threshold=threshold_val,
            downstream_zone=rng.choice(downstream_candidates),
            sector=rng.choice(sector_candidates),
        )

    def _build_zone_prefix(self, zone_type: str, rng: random.Random) -> str:
        """Menambahkan prefiks khusus zona jika tersedia."""
        prefixes = self._bank.ZONE_SPECIFIC_PREFIX.get(zone_type.lower(), [])
        if prefixes and rng.random() < 0.65:
            return rng.choice(prefixes)
        return ""

    def _build_temporal_suffix(self, ctx: _SpatialContext, rng: random.Random) -> str:
        """Menambahkan konteks temporal (jam sibuk / akhir pekan) secara selektif."""
        if ctx.is_peak_hour and rng.random() < 0.70:
            return rng.choice(self._bank.PEAK_HOUR_SUFFIX)
        if ctx.is_weekend and rng.random() < 0.55:
            return rng.choice(self._bank.WEEKEND_SUFFIX)
        return ""

    # ── PUBLIC API ────────────────────────────────────────────────────────────

    def predict(
        self,
        violation_count: int,
        current_density: float,
        zone_type: str,
    ) -> tuple[str, float]:
        """
        Menganalisis kondisi spasial dan menghasilkan insight profesional.

        Parameters
        ----------
        violation_count  : Jumlah pelanggaran aktif yang terdeteksi (int ≥ 0)
        current_density  : Kepadatan lalu lintas dalam persen (float 0–100)
        zone_type        : Kode tipologi zona jalan (str, lihat _ZONE_ALIASES)

        Returns
        -------
        tuple[str, float]
            Kalimat insight (str) dan tingkat akurasi prediksi (float, 0–100).
        """
        # Sanitasi input
        violation_count = max(0, int(violation_count))
        current_density = max(0.0, min(100.0, float(current_density)))
        zone_type       = str(zone_type).strip().lower()

        # Bangun konteks
        severity  = self._classify_severity(violation_count, current_density)
        zone_label = self._resolve_zone(zone_type)
        seed      = self._build_seed(violation_count, current_density, zone_type) + self._seed_offset
        acc_range = _ACCURACY_MAP[severity]

        ctx = _SpatialContext(
            violation_count=violation_count,
            current_density=current_density,
            zone_type=zone_type,
            zone_label=zone_label,
            severity=severity,
            accuracy_range=acc_range,
            seed=seed,
        )

        accuracy = ctx.derive_accuracy()
        rng = random.Random(seed)

        # Pilih dan isi template
        pool     = self._get_template_pool(severity)
        template = rng.choice(pool)
        body     = self._fill_template(template, ctx, accuracy)

        # Gabungkan prefiks zona dan sufiks temporal
        prefix  = self._build_zone_prefix(zone_type, rng)
        suffix  = self._build_temporal_suffix(ctx, rng)
        insight = f"{prefix}{body}{suffix}".strip()

        return insight, accuracy

    def get_sentiments(self, count: int = 5, seed: Optional[int] = None) -> list[dict]:
        """
        Menghasilkan sampel acak data sentimen warga.

        Parameters
        ----------
        count : Jumlah entri yang dikembalikan (default 5, maks 15)
        seed  : Optional seed untuk reproducibility

        Returns
        -------
        list[dict] dengan kunci: inisial, nama, waktu, pesan, warna, kategori
        """
        count = max(1, min(15, int(count)))
        rng   = random.Random(seed if seed is not None else
                              int(datetime.datetime.now().timestamp()))

        pool    = rng.sample(self._sentiment_bank.MESSAGES,
                             min(count, len(self._sentiment_bank.MESSAGES)))
        times   = rng.choices(self._sentiment_bank.TIME_OPTIONS, k=count)

        results: list[dict] = []
        for i, item in enumerate(pool):
            results.append({
                "inisial":  item["inisial"],
                "nama":     item["nama"],
                "waktu":    times[i],
                "pesan":    item["pesan"],
                "warna":    item["warna"],
                "kategori": item.get("kategori", "umum"),
            })

        return results


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE (digunakan oleh fungsi-fungsi publik)
# ─────────────────────────────────────────────────────────────────────────────

_engine = InsightEngine()


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC FUNCTIONS — API EKSTERNAL MODUL
# ─────────────────────────────────────────────────────────────────────────────

def get_ai_prediction(
    violation_count: int,
    current_density: float,
    zone_type: str,
) -> tuple[str, float]:
    """
    Menganalisis kondisi lalu lintas dan menghasilkan insight spasial profesional.

    Parameters
    ----------
    violation_count : int
        Jumlah insiden pelanggaran yang terdeteksi dalam window observasi.
    current_density : float
        Tingkat kepadatan arus kendaraan dalam persen (0–100).
    zone_type : str
        Tipologi zona jalan. Nilai valid:
        'highway', 'arterial', 'residential', 'commercial',
        'industrial', 'school_zone', 'hospital_zone', 'bus_corridor',
        'market', 'toll_gate', 'bridge', 'tunnel', 'unknown'

    Returns
    -------
    tuple[str, float]
        - str   : Kalimat insight dalam Bahasa Indonesia (Command Center style)
        - float : Tingkat akurasi prediksi model (persentase, 0–100)

    Examples
    --------
    >>> insight, acc = get_ai_prediction(30, 92.5, 'highway')
    >>> print(f"[{acc}%] {insight}")
    """
    return _engine.predict(violation_count, current_density, zone_type)


def get_citizen_sentiment(count: int = 5) -> list[dict]:
    """
    Menghasilkan data simulasi sentimen warga yang relevan.

    Parameters
    ----------
    count : int
        Jumlah entri sentimen yang dikembalikan (default 5, maks 15).

    Returns
    -------
    list[dict]
        Setiap dict berisi:
        - 'inisial'  : str  — Inisial nama warga (misal "AS")
        - 'nama'     : str  — Nama lengkap warga
        - 'waktu'    : str  — Waktu relatif laporan (misal "5m ago")
        - 'pesan'    : str  — Isi laporan/komentar warga
        - 'warna'    : str  — Kategori warna: 'red','orange','blue','green'
        - 'kategori' : str  — Label kategori keluhan/pujian

    Examples
    --------
    >>> sentiments = get_citizen_sentiment(3)
    >>> for s in sentiments:
    ...     print(f"[{s['warna'].upper()}] {s['nama']} ({s['waktu']}): {s['pesan'][:60]}...")
    """
    return _engine.get_sentiments(count=count)


# ─────────────────────────────────────────────────────────────────────────────
# DEMO CLI — Jalankan `python insight_engine.py` untuk melihat output sampel
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import textwrap

    SEPARATOR = "─" * 78

    print("\n" + "═" * 78)
    print("  URBAN SPATIAL BEHAVIOR ANALYTICS — INSIGHT ENGINE DEMO")
    print("  Smart City Command Center · Demonstrasi Output Sistem")
    print("═" * 78)

    # ── Skenario Uji Prediksi ─────────────────────────────────────────────────
    test_scenarios = [
        # (violation_count, density, zone_type, label)
        (32, 94.5, "highway",       "🔴 KRITIS    · Arteri Primer Jam Sibuk"),
        (18, 74.0, "bus_corridor",  "🟠 TINGGI    · Koridor BRT Terblokir"),
        (22, 78.0, "hospital_zone", "🔴 TINGGI    · Zona Buffer RS"),
        (9,  55.5, "commercial",    "🟡 SEDANG    · Kawasan Komersial Siang"),
        (4,  35.0, "residential",   "🟢 RENDAH    · Zona Permukiman Pagi"),
        (0,  18.0, "school_zone",   "✅ NORMAL    · Kawasan Sekolah Sepi"),
        (14, 67.0, "market",        "🟠 TINGGI    · Pasar Pagi Aktif"),
        (25, 88.0, "toll_gate",     "🔴 KRITIS    · Pintu Tol Padat"),
    ]

    print("\n📡  A I   P R E D I C T I O N   O U T P U T\n")
    for i, (v, d, z, label) in enumerate(test_scenarios, 1):
        insight, accuracy = get_ai_prediction(v, d, z)
        print(f"  [{i:02d}] {label}")
        print(f"       Input  → Pelanggaran: {v} | Kepadatan: {d}% | Zona: {z}")
        print(f"       Akurasi → {accuracy}%")
        print(f"       Insight:")
        wrapped = textwrap.fill(insight, width=72, initial_indent="         ",
                                subsequent_indent="         ")
        print(wrapped)
        print(f"  {SEPARATOR}")

    # ── Skenario Uji Sentimen ─────────────────────────────────────────────────
    print("\n\n🗣️  C I T I Z E N   S E N T I M E N T   S A M P L E S\n")
    sentiments = get_citizen_sentiment(count=7)
    color_icons = {"red": "🔴", "orange": "🟠", "blue": "🔵", "green": "🟢"}
    for s in sentiments:
        icon = color_icons.get(s["warna"], "⚪")
        print(f"  {icon} {s['nama']} ({s['inisial']}) · {s['waktu']} · [{s['kategori']}]")
        wrapped = textwrap.fill(s["pesan"], width=72, initial_indent="     ",
                                subsequent_indent="     ")
        print(wrapped)
        print()

    print("═" * 78)
    print("  ✔  Semua sistem berjalan normal. Insight Engine siap diintegrasikan.")
    print("═" * 78 + "\n")