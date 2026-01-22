import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- 1. CẤU HÌNH ---
st.set_page_config(page_title="Badminton & Pickleball Manager", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh") 

# Kết nối Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Lỗi cấu hình Secrets! Kiểm tra lại private_key.")
    st.stop()

def load_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="0")
        df = df.dropna(how='all')
        # Ép kiểu số tự động để tránh lỗi tính toán
        for col in ['SoLuong', 'GiaBan', 'TongTien', 'DonGia', 'SoLuongCo']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def save_data(df, sheet_name):
    try:
        conn.update(worksheet=sheet_name, data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Lỗi lưu dữ liệu: {e}")
        return False

# --- 2. TẢI DỮ LIỆU ---
df_config = load_data("Config")
df_catalog = load_data("Catalog")
df_history = load_data("LichSu")

# --- 3. ĐĂNG NHẬP ---
try:
    from passwords import USER_DB
except:
    st.error("Thiếu file passwords.py!")
    st.stop()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.title("🔐 ĐĂNG NHẬP HỆ THỐNG")
    u = st.selectbox("Tài khoản", [""] + list(USER_DB.keys()))
    p = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        if u in USER_DB and USER_DB[u] == p:
            st.session_state.logged_in, st.session_state.user_role = True, u
            st.rerun()
    st.stop()

user_role = st.session_state.user_role

# --- 4. GIAO DIỆN ADMIN ---
if user_role == "admin":
    st.title("🛡️ QUẢN TRỊ VIÊN")
    tab1, tab2, tab3 = st.tabs(["⚙️ Cấu hình & SP", "📊 Quản lý Đơn hàng", "📦 Gom đơn NCC"])

    with tab1:
        # Cấu hình Deadline
        st.subheader("1. Cài đặt Line & Deadline")
        ed_config = st.data_editor(df_config, num_rows="dynamic", use_container_width=True)
        if st.button("Lưu cấu hình Line"):
            if save_data(ed_config, "Config"): st.success("Đã lưu!"); st.rerun()
        
        st.divider()
        # Quản lý Sản phẩm
        st.subheader("2. Quản lý Danh mục Sản phẩm")
        target_line = st.selectbox("Chọn Line để quản lý:", df_config['Line'].unique() if not df_config.empty else [])
        if target_line:
            curr_cat = df_catalog[df_catalog['Line'] == target_line]
            ed_cat = st.data_editor(curr_cat, use_container_width=True, num_rows="dynamic")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Lưu Catalog {target_line}"):
                    final_cat = pd.concat
