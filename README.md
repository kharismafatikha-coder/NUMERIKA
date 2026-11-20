# NUMERIKA

Aplikasi belajar Metode Numerik interaktif (Streamlit): materi, kalkulator Newton-Raphson,
visualisasi garis singgung, kuis bertingkat, dan profil pengguna.

## Fitur utama
- **Materi Newton-Raphson lengkap** (8 tab): konsep, penurunan rumus, algoritma + kode Python,
  contoh hitung, konvergensi & galat, kelebihan/kekurangan, kasus gagal, dan latihan.
- **Kuis bertingkat**: Level 1 Dasar, Level 2 Menengah, Level 3 Mahir (masing-masing 15 soal di bank,
  10 soal diambil acak per percobaan) dan Tantangan Campuran (15 soal). Batas lulus 70%.
- Riwayat dan skor terbaik per level tersimpan di profil.

## Menjalankan di komputer
    pip install -r requirements.txt
    python -m streamlit run app.py

Database SQLite (`numerika.db`) dibuat/dimigrasi otomatis saat aplikasi pertama kali dijalankan.

## Menambah atau mengubah soal kuis
Semua soal ada di `konten.py` pada `QUIZ_BANK`. Format satu soal:

    ("Pertanyaan", ["pilihan A", "pilihan B", "pilihan C", "pilihan D"], indeks_jawaban_benar, "Pembahasan")

Urutan pilihan diacak otomatis. Jumlah soal per percobaan dan batas lulus diatur di `LEVELS` dan `PASS_PERCENT`.
