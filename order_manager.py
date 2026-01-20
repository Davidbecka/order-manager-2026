import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống Order Online 2026", layout="wide")
st_autorefresh(interval=60 * 1000, key="datarefresh") # Tự động làm mới mỗi 1 phút

# --- 2. KẾT NỐI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        df = conn.read(worksheet=sheet_name, ttl="0")
        df = df.dropna(how='all')
        # TỰ ĐỘNG ÉP KIỂU SỐ để tránh lỗi tính toán
        numeric_cols = ['SoLuong', 'GiaBan', 'TongTien', 'DonGia']
        for col in numeric_cols:
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
        st.error(f"❌ Lỗi ghi dữ liệu: {e}")
        return False

# --- 3. KIỂM TRA DỮ LIỆU ---
df_config = load_data("Config")
df_history = load_data("LichSu")
df_catalog = load_data("Catalog")

# Đảm bảo cột số là kiểu số để định dạng được
if not df_catalog.empty:
    df_catalog['DonGia'] = pd.to_numeric(df_catalog['DonGia'], errors='coerce').fillna(0)
if not df_history.empty:
    df_history['GiaBan'] = pd.to_numeric(df_history['GiaBan'], errors='coerce').fillna(0)
    df_history['TongTien'] = pd.to_numeric(df_history['TongTien'], errors='coerce').fillna(0)
    df_history['SoLuong'] = pd.to_numeric(df_history['SoLuong'], errors='coerce').fillna(0)

# Khởi tạo khung nếu trống
if df_config.empty: df_config = pd.DataFrame(columns=['Line', 'Deadline'])
if df_history.empty: df_history = pd.DataFrame(columns=['Ngày', 'Shop', 'Line', 'TenSP', 'BienThe', 'SKU', 'SoLuong', 'GiaBan', 'TongTien', 'GhiChu', 'LichSu', 'Timestamp'])
if df_catalog.empty: df_catalog = pd.DataFrame(columns=['TenSP', 'BienThe', 'SKU', 'DonGia', 'Line'])

# --- 4. ĐĂNG NHẬP ---
try:
    from passwords import USER_DB
except ImportError:
    st.error("❌ Thiếu file passwords.py!")
    st.stop()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: user = st.selectbox("Tài khoản", [""] + list(USER_DB.keys()))
    with c2: pwd = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập", use_container_width=True, type="primary"):
        if user in USER_DB and USER_DB[user] == pwd:
            st.session_state.logged_in = True
            st.session_state.user_role = user
            st.rerun()
        else: st.error("Sai mật khẩu!")
    st.stop()

user_role = st.session_state.user_role

# ---------------------------------------------------------
# 5. GIAO DIỆN ADMIN
# ---------------------------------------------------------
if user_role == "admin":
    st.title("🛠️ QUẢN TRỊ VIÊN (ADMIN)")
    tab1, tab2, tab3 = st.tabs(["🚀 Line & Danh mục", "📊 Điều phối đơn", "📦 Gom đơn NCC"])

    with tab1:
        st.subheader("1. Cấu hình Line hàng")
        ed_config = st.data_editor(df_config, num_rows="dynamic", use_container_width=True)
        if st.button("Lưu cấu hình Line"):
            if save_data(ed_config, "Config"): st.success("Đã lưu!"); st.rerun()

        st.divider()
        st.subheader("2. Quản lý Danh mục Sản phẩm")
        line_target = st.selectbox("Chọn Line để quản lý:", df_config['Line'].unique() if not df_config.empty else [])
        
        if line_target:
            # TÍNH NĂNG KÉO THẢ/THU GỌN DANH SÁCH
            with st.expander(f"📦 Xem/Sửa danh sách sản phẩm của {line_target}", expanded=True):
                current_cat = df_catalog[df_catalog['Line'] == line_target].copy()
                
                # BỘ LỌC TÌM KIẾM
                f_search = st.text_input("🔍 Tìm nhanh sản phẩm (theo Tên hoặc SKU):", "")
                if f_search:
                    current_cat = current_cat[current_cat['TenSP'].str.contains(f_search, case=False, na=False) | 
                                            current_cat['SKU'].str.contains(f_search, case=False, na=False)]
                
                # CHỈNH SỬA TRỰC TIẾP VÀ ĐỊNH DẠNG SỐ
                st.info("💡 Bạn có thể sửa trực tiếp trên bảng này và bấm 'Cập nhật thay đổi' phía dưới.")
                edited_cat = st.data_editor(
                    current_cat, 
                    use_container_width=True, 
                    num_rows="dynamic",
                    column_config={
                        "DonGia": st.column_config.NumberColumn("Đơn Giá", format="%d"),
                        "SKU": st.column_config.TextColumn("Mã SKU")
                    },
                    key="cat_editor"
                )
                
                if st.button(f"💾 Cập nhật thay đổi cho {line_target}"):
                    # Gộp lại với các Line khác để lưu
                    df_others = df_catalog[df_catalog['Line'] != line_target]
                    df_final_cat = pd.concat([df_others, edited_cat], ignore_index=True)
                    if save_data(df_final_cat, "Catalog"):
                        st.success("Đã lưu chỉnh sửa danh mục!"); st.rerun()

            st.markdown("---")
            st.write("🔼 **Hoặc tải lên file mới cho Line này:**")
            up_cat = st.file_uploader("Chọn file Excel (.xlsx)", type=['xlsx'], key="upload_cat")
            if up_cat and st.button(f"🚀 Ghi đè file mới cho {line_target}"):
                df_new = pd.read_excel(up_cat, dtype={'SKU': str})
                df_new['Line'] = line_target
                df_updated_cat = pd.concat([df_catalog[df_catalog['Line'] != line_target], df_new], ignore_index=True)
                if save_data(df_updated_cat, "Catalog"): st.success("Đã cập nhật!"); st.rerun()

    with tab2:
        st.subheader("📊 Điều phối đơn hàng (Tự động tính toán)")
        l_filter = st.selectbox("Lọc theo Line:", ["Tất cả"] + list(df_config['Line'].unique()))
        disp_df = df_history if l_filter == "Tất cả" else df_history[df_history['Line'] == l_filter]
        
        if not disp_df.empty:
            # TÍNH NĂNG TỰ ĐỘNG: Hiển thị bảng chỉnh sửa
            edited_history = st.data_editor(
                disp_df, 
                use_container_width=True,
                column_config={
                    "SoLuong": st.column_config.NumberColumn("Số Lượng", format="%d", min_value=0),
                    "GiaBan": st.column_config.NumberColumn("Giá Bán", format="%d"),
                    "TongTien": st.column_config.NumberColumn("Tổng Tiền (Tự động)", format="%d", disabled=True), # Khóa ô này để máy tự tính
                },
                key="admin_order_editor"
            )
            
            # LOGIC TỰ ĐỘNG TÍNH TOÁN
            if st.button("💾 Xác nhận & Đồng bộ lên Google Sheets"):
                # Máy tự tính: Tổng tiền = Số lượng * Giá bán
                edited_history['TongTien'] = edited_history['SoLuong'] * edited_history['GiaBan']
                
                # Cập nhật thời gian chỉnh sửa tự động
                t_now = datetime.now().strftime("%H:%M %d/%m")
                edited_history['LichSu'] = edited_history['LichSu'].astype(str) + f" | [Admin cập nhật {t_now}]"
                
                if save_data(edited_history, "LichSu"):
                    st.success("✅ Đã tự động tính toán và lưu dữ liệu thành công!"); st.rerun()    with tab3:
        # Giữ nguyên logic gom đơn cũ...
        line_sum = st.selectbox("Chọn Line gom đơn:", df_config['Line'].unique() if not df_config.empty else [])
        df_target = df_history[df_history['Line'] == line_sum]
        if not df_target.empty:
            sum_df = df_target.groupby(['SKU', 'TenSP', 'BienThe']).agg({'SoLuong': 'sum', 'GiaBan': 'first'}).reset_index()
            sum_df['Thành Tiền'] = sum_df['SoLuong'] * sum_df['GiaBan']
            st.dataframe(sum_df, use_container_width=True, column_config={
                "GiaBan": st.column_config.NumberColumn(format="%d"),
                "Thành Tiền": st.column_config.NumberColumn(format="%d")
            })

# ---------------------------------------------------------
# 6. GIAO DIỆN SHOP
# ---------------------------------------------------------
else:
    st.title(f"🏬 Chi nhánh: {user_role}")
    l_sel = st.selectbox("Chọn Line hàng:", df_config['Line'].unique() if not df_config.empty else [])
    
    if l_sel:
        df_l_cat = df_catalog[df_catalog['Line'] == l_sel]
        if df_l_cat.empty:
            st.warning("Admin chưa đăng sản phẩm cho Line này.")
        else:
            with st.form("shop_order"):
                st.write("🛒 **Đặt hàng lẻ**")
                sp = st.selectbox("Sản phẩm", df_l_cat['TenSP'].unique())
                bt = st.selectbox("Biến thể", df_l_cat[df_l_cat['TenSP']==sp]['BienThe'].unique())
                sl = st.number_input("Số lượng", min_value=1, step=1)
                if st.form_submit_button("Gửi đơn hàng"):
                    it = df_l_cat[(df_l_cat['TenSP']==sp) & (df_l_cat['BienThe']==bt)].iloc[0]
                    t_now = datetime.now().strftime("%H:%M %d/%m")
                    new_order = pd.DataFrame([{
                        'Ngày': t_now, 'Shop': user_role, 'Line': l_sel, 'TenSP': sp, 'BienThe': bt,
                        'SKU': str(it['SKU']), 'SoLuong': sl, 'GiaBan': it['DonGia'], 'TongTien': sl*it['DonGia'],
                        'GhiChu': "", 'LichSu': f"[Tạo {t_now}]", 'Timestamp': datetime.now().timestamp()
                    }])
                    df_history = pd.concat([df_history, new_order], ignore_index=True)
                    if save_data(df_history, "LichSu"): st.success("Đã gửi đơn!"); st.rerun()

    st.divider()
    st.subheader("📋 Đơn hàng đã đặt")
    st.dataframe(df_history[df_history['Shop']==user_role], use_container_width=True, column_config={
        "GiaBan": st.column_config.NumberColumn(format="%d"),
        "TongTien": st.column_config.NumberColumn(format="%d")
    })

with st.sidebar:
    if st.button("Đăng xuất"): 
        st.session_state.logged_in = False
        st.rerun()
