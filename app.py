ok import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import pandas as pd
import plotly.express as px
from datetime import datetime, date

# 1. KONFIGURASI API GEMINI (Ganti dengan API Key Anda)
# Membaca API Key secara aman dari Secrets Streamlit
GENAI_API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=GENAI_API_KEY)


# Konfigurasi Halaman Streamlit
st.set_page_config(page_title="FitTrack AI - Calorie & Weight Tracker", page_icon="🎾", layout="centered")

# File lokal untuk menyimpan histori berat badan agar tidak hilang
WEIGHT_FILE = "weight_history.csv"

# Inisialisasi file CSV jika belum ada
try:
    df_weight = pd.read_csv(WEIGHT_FILE)
except FileNotFoundError:
    # Buat data awal berdasarkan progres Anda (66kg ke 63kg dalam 2 minggu terakhir)
    initial_data = {
        "Tanggal": [
            (date.today() - pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
            (date.today() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
            date.today().strftime("%Y-%m-%d")
        ],
        "Berat (kg)": [66.0, 64.5, 63.0]
    }
    df_weight = pd.DataFrame(initial_data)
    df_weight.to_csv(WEIGHT_FILE, index=False)

# Inisialisasi State Tracker Kalori Harian
if "calories_in" not in st.session_state:
    st.session_state.calories_in = 0
if "protein" not in st.session_state:
    st.session_state.protein = 0
if "carbs" not in st.session_state:
    st.session_state.carbs = 0
if "fat" not in st.session_state:
    st.session_state.fat = 0
if "calories_out" not in st.session_state:
    st.session_state.calories_out = 0

# Tampilan Header Aplikasi
st.title("🎾 FitTrack AI Pro")
st.subheader("Pendamping Diet Intermittent Fasting & Tenis Anda")
st.markdown("---")

# ================= 1. DASHBOARD KALORI HARIAN =================
st.header("📊 Ringkasan Kalori Hari Ini")
net_calories = st.session_state.calories_in - st.session_state.calories_out

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Kalori Masuk (Makanan)", value=f"{st.session_state.calories_in} kcal")
with col2:
    st.metric(label="Kalori Dibakar (Olahraga)", value=f"{st.session_state.calories_out} kcal")
with col3:
    st.metric(label="Net Kalori", value=f"{net_calories} kcal")

# Tampilan Makronutrisi
st.markdown("##### 🥩 Makronutrisi Terkumpul")
col_p, col_c, col_f = st.columns(3)
col_p.write(f"**Protein:** {st.session_state.protein}g")
col_c.write(f"**Karbohidrat:** {st.session_state.carbs}g")
col_f.write(f"**Lemak:** {st.session_state.fat}g")

if st.button("Reset Data Harian", type="secondary"):
    st.session_state.calories_in = 0
    st.session_state.protein = 0
    st.session_state.carbs = 0
    st.session_state.fat = 0
    st.session_state.calories_out = 0
    st.rerun()

st.markdown("---")

# ================= 2. GRAFIK BERAT BADAN (FITUR BARU!) =================
st.header("📈 Grafik Perkembangan Berat Badan")

# Input Berat Badan Baru
col_input1, col_input2 = st.columns([2, 1])
with col_input1:
    input_date = st.date_input("Tanggal Timbang", value=date.today())
with col_input2:
    input_weight = st.number_input("Berat (kg)", min_value=30.0, max_value=150.0, value=63.0, step=0.1)

if st.button("Simpan Berat Badan", type="primary"):
    # Baca data terbaru, tambahkan data baru, lalu simpan ke CSV
    df_weight = pd.read_csv(WEIGHT_FILE)
    new_entry = pd.DataFrame({"Tanggal": [input_date.strftime("%Y-%m-%d")], "Berat (kg)": [input_weight]})
    
    # Hapus entri lama jika menginput di tanggal yang sama agar tidak duplikat
    df_weight = df_weight[df_weight["Tanggal"] != input_date.strftime("%Y-%m-%d")]
    
    df_weight = pd.concat([df_weight, new_entry], ignore_index=True)
    df_weight = df_weight.sort_values(by="Tanggal") # Urutkan berdasarkan tanggal
    df_weight.to_csv(WEIGHT_FILE, index=False)
    st.success(f"Berat badan {input_weight} kg berhasil disimpan!")
    st.rerun()

# Menampilkan Grafik Menggunakan Plotly
df_plot = pd.read_csv(WEIGHT_FILE)
df_plot["Tanggal"] = pd.to_datetime(df_plot["Tanggal"])

if not df_plot.empty:
    fig = px.line(
        df_plot, 
        x="Tanggal", 
        y="Berat (kg)", 
        title="Tren Penurunan Berat Badan Anda",
        markers=True,
        color_discrete_sequence=["#1E90FF"] # Warna biru tenis
    )
    # Atur tampilan grafik agar cantik di HP
    fig.update_layout(
        xaxis_title="Tanggal",
        yaxis_title="Berat Badan (kg)",
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Belum ada data berat badan yang dimasukkan.")

st.markdown("---")

# ================= 3. FITUR DETEKSI MAKANAN (KAMERA) =================
st.header("📸 Pindai Makanan Anda")
img_file = st.camera_input("Ambil Foto Makanan")

def analyze_food_image(image_bytes):
    model = genai.GenerativeModel('gemini-pro-vision') # <-- Diganti menjadi gemini-pro-vision
    prompt = """

    Kamu adalah ahli nutrisi AI. Analisis gambar makanan ini dan berikan estimasi nutrisinya.
    Format jawaban HARUS persis seperti template di bawah ini, jangan menulis kalimat pembuka atau penutup lain.
    Format output:
    Nama Makanan: [Nama Makanan]
    Estimasi Porsi: [Misal: 1 piring sedang, 150 gram]
    Kalori: [Angka saja dalam kcal, misal: 350]
    Protein: [Angka saja dalam gram, misal: 25]
    Karbohidrat: [Angka saja dalam gram, misal: 40]
    Lemak: [Angka saja dalam gram, misal: 12]
    """
    image = Image.open(io.BytesIO(image_bytes))
    response = model.generate_content([prompt, image])
    return response.text

if img_file is not None:
    bytes_data = img_file.getvalue()
    with st.spinner("Sedang menganalisis makanan Anda dengan AI..."):
        try:
            analysis_result = analyze_food_image(bytes_data)
            st.success("Analisis Selesai!")
            st.text_area("Hasil Analisis AI:", value=analysis_result, height=200)
            
            lines = analysis_result.strip().split("\n")
            temp_data = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    temp_data[key.strip()] = val.strip()
            
            cal = int(''.join(filter(str.isdigit, temp_data.get("Kalori", "0"))))
            prot = int(''.join(filter(str.isdigit, temp_data.get("Protein", "0"))))
            carb = int(''.join(filter(str.isdigit, temp_data.get("Karbohidrat", "0"))))
            fat = int(''.join(filter(str.isdigit, temp_data.get("Lemak", "0"))))
            
            if st.button("Tambahkan ke Tracker Hari Ini", type="primary"):
                st.session_state.calories_in += cal
                st.session_state.protein += prot
                st.session_state.carbs += carb
                st.session_state.fat += fat
                st.success(f"Berhasil menambahkan {temp_data.get('Nama Makanan', 'Makanan')} ke log harian!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Gagal menganalisis gambar. Pastikan API Key Anda benar. Error: {e}")

st.markdown("---")

# ================= 4. FITUR KALORI TERBAKAR (TENIS & OLAHRAGA) =================
st.header("🎾 Catat Olahraga (Kalori Terbakar)")

sport_option = st.selectbox("Pilih Jenis Olahraga", ["Tenis", "Kalistenik/Olahraga Beban", "Lari/Jogging"])
duration = st.number_input("Durasi Olahraga (Menit)", min_value=1, max_value=300, value=60)

if sport_option == "Tenis":
    cal_burned_per_min = 7.3
elif sport_option == "Kalistenik/Olahraga Beban":
    cal_burned_per_min = 4.5
else:
    cal_burned_per_min = 8.0

total_burned = int(duration * cal_burned_per_min)
st.write(f"Estimasi kalori yang terbakar: **{total_burned} kcal**")

if st.button("Catat Kalori Terbakar"):
    st.session_state.calories_out += total_burned
    st.success(f"Berhasil mencatat {total_burned} kcal yang dibakar!")
    st.rerun()
