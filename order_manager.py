import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống Order Online 2026", layout="wide")

# Tự động làm mới mỗi 30 giây để cập nhật dữ liệu từ Admin/Shop khác
st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- KẾT NỐI GOOGLE SHEETS ---
# Thiết lập kết nối (Cấu hình link Sheets sẽ nằm trong phần Secrets của Streamlit Cloud)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    # Đọc dữ liệu từ tab tương ứng, ttl=0 để luôn lấy dữ liệu mới nhất
    return conn.read(worksheet=sheet_name, ttl="0s").dropna(how='all')

def save_data(df, sheet_name):
    # Ghi dữ liệu đè lên tab tương ứng
    conn.update(worksheet=sheet_name, data=df)
    st.cache_data.clear()

# --- HÀM TẠO FILE MẪU ---
def create_template(cols):
    df = pd.DataFrame(columns=cols)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- ĐĂNG NHẬP ---
try:
    from passwords import USER_DB
except ImportError:
    st.error("❌ Thiếu file 'passwords.py' trên GitHub!")
    st.stop()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 ĐĂNG NHẬP HỆ THỐNG ORDER</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: user = st.selectbox("Tài khoản chi nhánh", [""] + list(USER_DB.keys()))
    with c2: pwd = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập", use_container_width=True, type="primary"):
        if user in USER_DB and USER_DB[user] == pwd:
            st.session_state.logged_in = True
            st.session_state.user_role = user
            st.rerun()
        else: st.error("Sai mật khẩu!")
    st.stop()

user_role = st.session_state.user_role

# --- TẢI DỮ LIỆU TỪ GOOGLE SHEETS ---
try:
    df_config = load_data("Config")
    df_history = load_data("LichSu")
except Exception as e:
    st.error(f"❌ Lỗi kết nối Google Sheets: {e}")
    st.stop()

# ---------------------------------------------------------
# GIAO DIỆN ADMIN
# ---------------------------------------------------------
if user_role == "admin":
    st.title("🛠️ QUẢN TRỊ VIÊN")
    tab1, tab2, tab3 = st.tabs(["🚀 Line & Danh mục", "📊 Điều phối & Nhật ký", "📦 Gom đơn NCC"])

    with tab1:
        st.subheader("1. Cài đặt Line hàng")
        ed_config = st.data_editor(df_config, num_rows="dynamic", use_container_width=True)
        if st.button("Lưu cấu hình Line"):
            save_data(ed_config, "Config")
            st.success("Đã cập nhật danh sách Line lên Google Sheets!")

        st.divider()
        st.subheader("2. Đăng tải sản phẩm cho Line")
        st.download_button("📥 Tải File Mẫu Danh Mục", data=create_template(['TenSP', 'BienThe', 'SKU', 'DonGia']), file_name="Mau_DanhMuc.xlsx")
        
        line_to_up = st.selectbox("Chọn Line:", df_config['Line'].unique())
        up_cat = st.file_uploader("Úp file Excel danh mục", type=['xlsx'])
        if up_cat and st.button(f"Đăng sản phẩm cho {line_to_up}"):
            df_new_cat = pd.read_excel(up_cat, dtype={'SKU': str})
            # Lưu danh mục vào Sheet riêng hoặc Sheet Catalog có cột Line
            # Để đơn giản, bản này hỗ trợ lưu vào sheet 'Catalog'
            df_all_cat = load_data("Catalog")
            df_new_cat['Line'] = line_to_up
            df_all_cat = pd.concat([df_all_cat[df_all_cat['Line'] != line_to_up], df_new_cat], ignore_index=True)
            save_data(df_all_cat, "Catalog")
            st.success(f"Đã cập nhật sản phẩm cho {line_to_up}!")

    with tab2:
        line_view = st.selectbox("Lọc theo Line:", ["Tất cả"] + list(df_config['Line'].unique()))
        disp_df = df_history if line_view == "Tất cả" else df_history[df_history['Line'] == line_view]
        
        if not disp_df.empty:
            edited_df = st.data_editor(disp_df, use_container_width=True)
            if st.button("💾 Lưu chỉnh sửa (Đồng bộ Google Sheets)"):
                time_now = datetime.now().strftime("%H:%M %d/%m")
                # Ghi lịch sử tự động (Log)
                for idx in edited_df.index:
                    if edited_df.at[idx, 'SoLuong'] != df_history.loc[idx, 'SoLuong']:
                        log_msg = f" | [Admin sửa SL: {df_history.loc[idx, 'SoLuong']}->{edited_df.at[idx, 'SoLuong']} lúc {time_now}]"
                        edited_df.at[idx, 'LichSu']
