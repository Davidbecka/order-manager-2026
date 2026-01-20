import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống Order Online 2026", layout="wide")

# Tự động làm mới mỗi 30 giây để cập nhật dữ liệu mới từ các shop/admin
st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- 2. KẾT NỐI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        # ttl="0" giúp dữ liệu luôn mới nhất, không bị lưu trong bộ nhớ đệm
        df = conn.read(worksheet=sheet_name, ttl="0")
        return df.dropna(how='all')
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

# --- 3. KIỂM TRA VÀ TẠO KHUNG DỮ LIỆU (CHỐNG LỖI KEYERROR) ---
df_config = load_data("Config")
df_history = load_data("LichSu")
df_catalog = load_data("Catalog")

if df_config.empty or 'Line' not in df_config.columns:
    df_config = pd.DataFrame(columns=['Line', 'Deadline'])
if df_history.empty or 'Line' not in df_history.columns:
    df_history = pd.DataFrame(columns=['Ngày', 'Shop', 'Line', 'TenSP', 'BienThe', 'SKU', 'SoLuong', 'GiaBan', 'TongTien', 'GhiChu', 'LichSu', 'Timestamp'])
if df_catalog.empty or 'Line' not in df_catalog.columns:
    df_catalog = pd.DataFrame(columns=['TenSP', 'BienThe', 'SKU', 'DonGia', 'Line'])

# --- 4. ĐĂNG NHẬP ---
try:
    from passwords import USER_DB
except ImportError:
    st.error("❌ Không tìm thấy file 'passwords.py' trên GitHub!")
    st.stop()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 ĐĂNG NHẬP HỆ THỐNG ORDER 2026</h2>", unsafe_allow_html=True)
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

# ---------------------------------------------------------
# 5. GIAO DIỆN ADMIN
# ---------------------------------------------------------
if user_role == "admin":
    st.title("🛠️ QUẢN TRỊ VIÊN (ADMIN)")
    tab1, tab2, tab3 = st.tabs(["🚀 Line & Danh mục", "📊 Điều phối & Nhật ký", "📦 Gom đơn NCC"])

    with tab1:
        st.subheader("1. Quản lý Line hàng (Đợt hàng)")
        ed_config = st.data_editor(df_config, num_rows="dynamic", use_container_width=True, key="ed_config")
        if st.button("Lưu cấu hình Line"):
            if save_data(ed_config, "Config"):
                st.success("Đã đồng bộ Line hàng!"); st.rerun()

        st.divider()
        st.subheader("2. Quản lý Danh mục Sản phẩm")
        line_target = st.selectbox("Chọn Line để quản lý:", df_config['Line'].unique() if not df_config.empty else [])
        
        if line_target:
            # Hiển thị sản phẩm hiện có của Line này
            current_cat = df_catalog[df_catalog['Line'] == line_target]
            st.write(f"Sản phẩm hiện có trong **{line_target}**:")
            st.dataframe(current_cat, use_container_width=True)
            
            # Cập nhật sản phẩm mới
            up_cat = st.file_uploader(f"Úp file Excel để ghi đè danh mục cho {line_target}", type=['xlsx'])
            if up_cat and st.button(f"Xác nhận cập nhật SP cho {line_target}"):
                df_new = pd.read_excel(up_cat, dtype={'SKU': str})
                df_new['Line'] = line_target
                # Giữ lại SP của các Line khác, chỉ ghi đè Line đang chọn
                df_updated_cat = pd.concat([df_catalog[df_catalog['Line'] != line_target], df_new], ignore_index=True)
                if save_data(df_updated_cat, "Catalog"):
                    st.success("Đã cập nhật danh mục!"); st.rerun()

    with tab2:
        st.subheader("Bảng điều phối & Bộ lọc đơn hàng")
        all_lines = ["Tất cả"] + list(df_config['Line'].unique())
        line_filter = st.selectbox("Lọc danh sách đặt hàng theo Line:", all_lines)
        
        disp_df = df_history if line_filter == "Tất cả" else df_history[df_history['Line'] == line_filter]
        
        if not disp_df.empty:
            st.info(f"Đang hiển thị đơn hàng của: {line_filter}")
            # Cho phép Admin sửa số lượng hoặc ghi chú trực tiếp
            edited_df = st.data_editor(disp_df, use_container_width=True, key="admin_order_editor")
            
            if st.button("💾 Lưu thay đổi đơn hàng"):
                # Tự động tính lại tổng tiền
                edited_df['TongTien'] = edited_df['SoLuong'] * edited_df['GiaBan']
                # Cập nhật vào dữ liệu gốc
                df_history.update(edited_df)
                if save_data(df_history, "LichSu"):
                    st.success("Đã đồng bộ thay đổi đơn hàng!"); st.rerun()
        else:
            st.warning("Hiện chưa có đơn hàng nào cho mục này.")

    with tab3:
        st.subheader("Gom tổng đơn gửi Nhà cung cấp")
        line_sum = st.selectbox("Chọn Line cần gom:", df_config['Line'].unique() if not df_config.empty else [])
        df_target = df_history[df_history['Line'] == line_sum]
        if not df_target.empty:
            summary = df_target.groupby(['SKU', 'TenSP', 'BienThe']).agg({'SoLuong': 'sum', 'GiaBan': 'first'}).reset_index()
            summary['Thành Tiền'] = summary['SoLuong'] * summary['GiaBan']
            st.dataframe(summary, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary.to_excel(writer, index=False)
            st.download_button("📥 Tải đơn tổng NCC (.xlsx)", data=output.getvalue(), file_name=f"Tong_Dat_Hang_{line_sum}.xlsx")

# ---------------------------------------------------------
# 6. GIAO DIỆN SHOP (CHI NHÁNH)
# ---------------------------------------------------------
else:
    st.title(f"🏬 Chi nhánh: {user_role}")
    line_sel = st.selectbox("Chọn Line hàng bạn muốn đặt:", df_config['Line'].unique() if not df_config.empty else [])
    
    if line_sel:
        df_line_cat = df_catalog[df_catalog['Line'] == line_sel]
        
        if df_line_cat.empty:
            st.warning("Admin chưa đăng tải sản phẩm cho Line này.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 🛒 Đặt hàng lẻ")
                with st.form("manual_form", clear_on_submit=True):
                    sp_name = st.selectbox("Sản phẩm", df_line_cat['TenSP'].unique())
                    bt_name = st.selectbox("Màu/Size", df_line_cat[df_line_cat['TenSP']==sp_name]['BienThe'].unique())
                    qty = st.number_input("Số lượng", min_value=1, step=1)
                    
                    if st.form_submit_button("Xác nhận gửi đơn"):
                        item = df_line_cat[(df_line_cat['TenSP']==sp_name) & (df_line_cat['BienThe']==bt_name)].iloc[0]
                        # SỬA LỖI NAMEERROR: Khai báo t_now trước khi dùng
                        t_now = datetime.now().strftime("%H:%M %d/%m")
                        new_row = pd.DataFrame([{
                            'Ngày': t_now, 'Shop': user_role, 'Line': line_sel, 'TenSP': sp_name, 'BienThe': bt_name,
                            'SKU': str(item['SKU']), 'SoLuong': qty, 'GiaBan': item['DonGia'], 'TongTien': qty * item['DonGia'],
                            'GhiChu': "", 'LichSu': f"[Shop tạo {t_now}]", 'Timestamp': datetime.now().timestamp()
                        }])
                        df_history = pd.concat([df_history, new_row], ignore_index=True)
                        if save_data(df_history, "LichSu"):
                            st.success("Gửi đơn thành công!"); st.rerun()
            
            with c2:
                st.markdown("### 📁 Đặt hàng theo file")
                up_file = st.file_uploader("Úp file mẫu SKU/SoLuong", type=['xlsx'])
                if up_file and st.button("🚀 Gửi đơn hàng loạt"):
                    df_up = pd.read_excel(up_file, dtype={'SKU': str})
                    t_now = datetime.now().strftime("%H:%M %d/%m")
                    df_final = df_up.merge(df_line_cat, on='SKU', how='left')
                    df_final['Ngày'] = t_now
                    df_final['Shop'] = user_role
                    df_final['Line'] = line_sel
                    df_final['GiaBan'] = df_final['DonGia']
                    df_final['TongTien'] = df_final['SoLuong'] * df_final['GiaBan']
                    df_final['LichSu'] = f"[Shop úp file {t_now}]"
                    df_final['Timestamp'] = datetime.now().timestamp()
                    df_history = pd.concat([df_history, df_final], ignore_index=True)
                    if save_data(df_history, "LichSu"):
                        st.success("Đã gửi đơn file thành công!"); st.rerun()

    st.divider()
    st.subheader("📋 Đơn hàng của bạn")
    my_orders = df_history[(df_history['Shop'] == user_role) & (df_history['Line'] == line_sel)]
    st.dataframe(my_orders, use_container_width=True)

with st.sidebar:
    st.write(f"Đăng nhập: **{user_role}**")
    if st.button("Đăng xuất"): 
        st.session_state.logged_in = False
        st.rerun()
