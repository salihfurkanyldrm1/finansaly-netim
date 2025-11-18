import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import hashlib

# =============================
# 🔧 Firebase Bağlantısı (Secrets ile)
# =============================
if not firebase_admin._apps:
    firebase_config = st.secrets["FIREBASE"]
    # private_key düzgün formatta olmalı
    firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
    cred = credentials.Certificate(firebase_config)

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://finansalyon-default-rtdb.firebaseio.com/"
    })

# =============================
# 🔐 Basit Kullanıcı Doğrulama
# =============================
def hash_password(password: str, username: str) -> str:
    return hashlib.sha256((password + username).encode("utf-8")).hexdigest()

def get_cred_ref(username: str):
    return db.reference(f"kullanici_creds/{username}")

def signup_user(username: str, password: str) -> (bool, str):
    cred_ref = get_cred_ref(username)
    if cred_ref.get() is not None:
        return False, "Bu kullanıcı adı zaten alınmış."
    hashed = hash_password(password, username)
    cred_ref.set({"password_hash": hashed, "created_at": datetime.now().isoformat()})
    return True, "Hesap başarıyla oluşturuldu."

def signin_user(username: str, password: str) -> (bool, str):
    cred_ref = get_cred_ref(username)
    data = cred_ref.get()
    if data is None:
        return False, "Kullanıcı bulunamadı."
    hashed = hash_password(password, username)
    if hashed != data.get("password_hash"):
        return False, "Şifre hatalı."
    return True, "Giriş başarılı."

# =============================
# 🧾 Oturum Yönetimi
# =============================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None

st.title("💸 Kişisel Finans Takip Uygulaması")
st.write("Her kullanıcı kendi verilerini görür, tüm kayıtlar bulutta saklanır ☁️")

if not st.session_state["logged_in"]:
    st.subheader("Giriş Yap / Kayıt Ol")
    col1, col2 = st.columns(2)
    with col1:
        kullanici_input = st.text_input("Kullanıcı adı:")
    with col2:
        sifre_input = st.text_input("Şifre:", type="password")

    signup_checkbox = st.checkbox("Yeni hesap oluşturmak istiyorum")

    if st.button("Devam Et"):
        if signup_checkbox:
            ok, msg = signup_user(kullanici_input, sifre_input)
        else:
            ok, msg = signin_user(kullanici_input, sifre_input)

        if ok:
            st.success(msg)
            st.session_state["logged_in"] = True
            st.session_state["user"] = kullanici_input
            st.experimental_rerun()
        else:
            st.error(msg)

    st.stop()

# =============================
# Oturum Açılmış
# =============================
kullanici = st.session_state["user"]
st.sidebar.markdown(f"**Giriş yapan:** {kullanici}")

if st.sidebar.button("Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.experimental_rerun()

user_ref = db.reference(f"kullanicilar/{kullanici}")

# =============================
# 📊 Veri Yükleme
# =============================
veri = user_ref.get()
df = pd.DataFrame(veri) if veri else pd.DataFrame(columns=["Tarih", "Tür", "Kategori", "Tutar", "Gider Türü"])

# =============================
# 📝 Yeni Kayıt Ekleme
# =============================
st.header("📝 Yeni Kayıt Ekle")

tur = st.radio("Tür seçin:", ["Gelir", "Gider"], horizontal=True)

if tur == "Gelir":
    kategori = st.selectbox("Kategori seçin:", ["Maaş", "Ek Gelir", "Yatırım", "Diğer"])
    gider_turu = "-"
else:
    kategori = st.selectbox("Kategori seçin:", ["Market", "Fatura", "Kişisel Bakım","Kredi","Ulaşım", "Eğitim", "Sağlık", "Cafe/Restaurant", "Diğer"])
    gider_turu = st.radio("Gider türü seçin:", ["İhtiyaç", "İstek"])

tutar = st.number_input("Tutar (₺)", min_value=0.0, step=10.0)

if st.button("💾 Kaydı Ekle"):
    yeni = {
        "Tarih": datetime.now().strftime("%Y-%m-%d"),
        "Tür": tur,
        "Kategori": kategori,
        "Tutar": tutar,
        "Gider Türü": gider_turu
    }
    liste = df.to_dict(orient="records") if not df.empty else []
    liste.append(yeni)
    user_ref.set(liste)
    st.success("Kayıt eklendi!")
    st.experimental_rerun()

# =============================
# 📋 Kayıtları Göster
# =============================
st.header("📋 Kayıtlar")
if not df.empty:
    st.dataframe(df)
else:
    st.info("Henüz kayıt yok.")

# =============================
# 🗑️ Kayıt Silme
# =============================
st.subheader("🗑️ Kayıt Sil")
if not df.empty:
    sec = st.selectbox("Silinecek kayıt:", df.index)
    if st.button("❌ Sil"):
        df = df.drop(sec).reset_index(drop=True)
        user_ref.set(df.to_dict(orient="records"))
        st.success("Kayıt silindi.")
        st.experimental_rerun()

# =============================
# 📈 ANLIK ANALİZ
# =============================
st.header("📈 Anlık Finans Analizi")

if not df.empty:
    df["Tutar"] = pd.to_numeric(df["Tutar"], errors="coerce").fillna(0)

    toplam_gelir = df[df["Tür"]=="Gelir"]["Tutar"].sum()
    toplam_gider = df[df["Tür"]=="Gider"]["Tutar"].sum()
    bakiye = toplam_gelir - toplam_gider

    st.metric("Toplam Gelir", f"{toplam_gelir:.2f} ₺")
    st.metric("Toplam Gider", f"{toplam_gider:.2f} ₺")
    st.metric("Kalan Bakiye", f"{bakiye:.2f} ₺")

    # -----------------------------
    # 🍩 1) İhtiyaç / İstek Pie Chart
    # -----------------------------
    st.subheader("🟣 İhtiyaç - İstek Dağılımı")

    ihtiyac = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="İhtiyaç")]["Tutar"].sum()
    istek = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="İstek")]["Tutar"].sum()

    if toplam_gider > 0:
        plt.figure(figsize=(5,5))
        plt.pie([ihtiyac, istek], labels=["İhtiyaç", "İstek"], autopct="%1.1f%%")
        st.pyplot(plt)
        plt.close()
    else:
        st.info("Gider olmadığı için grafik oluşturulamadı.")

    # -----------------------------
    # 🍕 2) Gider Kategorileri Pie Chart (YENİ)
    # -----------------------------
    st.subheader("🟠 Gider Kategorilerinin Yüzdesel Dağılımı")

    gider_df = df[df["Tür"] == "Gider"]

    if not gider_df.empty:
        kategori_toplam = gider_df.groupby("Kategori")["Tutar"].sum()

        plt.figure(figsize=(6,6))
        plt.pie(kategori_toplam, labels=kategori_toplam.index, autopct="%1.1f%%")
        st.pyplot(plt)
        plt.close()
    else:
        st.info("Kategori bazlı grafik için gider yok.")

    # -----------------------------
    # 📅 Son 30 gün grafiği
    # -----------------------------
    st.subheader("📆 Son 30 Günlük Gelir/Gider Grafiği")
    df["Tarih"] = pd.to_datetime(df["Tarih"])
    son_30 = df[df["Tarih"] >= (datetime.now() - timedelta(days=30))]
    gunluk = son_30.groupby(["Tarih", "Tür"])["Tutar"].sum().unstack().fillna(0)
    st.line_chart(gunluk)

else:
    st.info("Analiz için veri yok.")
st.write("Test mesajı: kod güncellendi ✅")
