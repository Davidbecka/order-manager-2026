import streamlit as st
import pandas as pd
from datetime import datetime
import io
from streamlit_autorefresh import st_autorefresh
from streamlit_gsheets import GSheetsConnection

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống Order Online 2026", layout="wide")

# Tự động làm mới mỗi 30 giây
st_autorefresh(interval=30 * 1000, key="datarefresh")

# --- KẾT NỐI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    try:
        # ttl="0" để luôn lấy dữ liệu mới nhất từ Google Sheets
        return conn.read(worksheet=sheet_name, ttl="0")
    except Exception as e:
        return pd.DataFrame()

def save_data(df, sheet_name):
    conn.update(worksheet=sheet_name, data=df)
    st.cache_data.clear()

# --- HÀM TẠO FILE MẪU ---
def create_template(cols):
    df = pd.DataFrame(columns=cols)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- KIỂM TRA ĐĂNG NHẬP ---
try:
    from passwords import USER_DB
except ImportError:
    st.error("❌ Không tìm thấy file 'passwords.py' trên GitHub!")
    st.stop()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 HỆ THỐNG ĐIỀU PHỐI ORDER 2026</h2>", unsafe_allow_html=True)
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

# --- TẢI DỮ LIỆU BAN ĐẦU (CẬP NHẬT CHỐNG LỖI KEYERROR) ---
df_config = load_data("Config")
df_history = load_data("LichSu")
df_catalog = load_data("Catalog")

# Tự động tạo khung nếu tab trống hoặc thiếu cột
if df_config.empty or 'Line' not in df_config.columns:
    df_config = pd.DataFrame(columns=["Line", "Deadline"])

if df_history.empty or 'Line' not in df_history.columns:
    df_history = pd.DataFrame(columns=['Ngày', 'Shop', 'Line', 'TenSP', 'BienThe', 'SKU', 'SoLuong', 'GiaBan', 'TongTien', 'GhiChu', 'LichSu', 'Timestamp'])

if df_catalog.empty or 'Line' not in df_catalog.columns:
    df_catalog = pd.DataFrame(columns=['TenSP', 'BienThe', 'SKU', 'DonGia', 'Line'])

# ---------------------------------------------------------
# GIAO DIỆN ADMIN
# ---------------------------------------------------------
if user_role == "admin":
    st.title("🛠️ QUẢN TRỊ VIÊN (ADMIN)")
    tab1, tab2, tab3 = st.tabs(["🚀 Line & Danh mục", "📊 Điều phối & Nhật ký", "📦 Gom đơn NCC"])

    with tab1:
        st.subheader("1. Cài đặt các Line hàng (Đợt hàng)")
        ed_config = st.data_editor(df_config, num_rows="dynamic", use_container_width=True)
        if st.button("Lưu cấu hình Line"):
            save_data(ed_config, "Config")
            st.success("Đã đồng bộ Line hàng lên Google Sheets!")

        st.divider()
        st.subheader("2. Đăng tải sản phẩm cho Line")
        st.download_button("📥 Tải File Mẫu Danh Mục (Admin)", data=create_template(['TenSP', 'BienThe', 'SKU', 'DonGia']), file_name="Mau_DanhMuc_Admin.xlsx")
        
        line_target = st.selectbox("Chọn Line muốn đăng SP:", df_config['Line'].unique() if not df_config.empty else [])
        up_cat = st.file_uploader("Úp file Excel danh mục cho Line này", type=['xlsx'])
        if up_cat and st.button(f"Xác nhận cập nhật SP cho {line_target}"):
            df_new = pd.read_excel(up_cat, dtype={'SKU': str})
            df_new['Line'] = line_target
            # Xóa bỏ SP cũ của Line này và thêm mới
            df_updated_cat = pd.concat([df_catalog[df_catalog['Line'] != line_target], df_new], ignore_index=True)
            save_data(df_updated_cat, "Catalog")
            st.success(f"Đã cập nhật sản phẩm cho {line_target}!")

    with tab2:
        st.subheader("Bảng điều phối & Theo dõi lịch sử")
        line_view = st.selectbox("Lọc theo Line:", ["Tất cả"] + list(df_config['Line'].unique() if not df_config.empty else []))
        disp_df = df_history if line_view == "Tất cả" else df_history[df_history['Line'] == line_view]
        
        if not disp_df.empty:
            st.write(f"Đang hiển thị đơn hàng: **{line_view}**")
            edited_df = st.data_editor(disp_df, use_container_width=True, 
                                     column_config={"LichSu": st.column_config.TextColumn("Nhật ký tương tác", width="large", disabled=True)})
            
            if st.button("💾 Xác nhận lưu & Đẩy dữ liệu xuống Shop"):
                time_now = datetime.now().strftime("%H:%M %d/%m")
                # Tự động ghi Log lịch sử nếu Admin sửa số lượng
                for idx in edited_df.index:
                    if idx in df_history.index and edited_df.at[idx, 'SoLuong'] != df_history.at[idx, 'SoLuong']:
                        old_val = df_history.at[idx, 'SoLuong']
                        new_val = edited_df.at[idx, 'SoLuong']
                        edited_df.at[idx, 'LichSu'] = str(edited_df.at[idx, 'LichSu']) + f" | [Admin sửa SL: {old_val}->{new_val} lúc {time_now}]"
                
                edited_df['TongTien'] = edited_df['SoLuong'] * edited_df['GiaBan']
                df_history.update(edited_df)
                save_data(df_history, "LichSu")
                st.success("Đã đồng bộ thay đổi thành công!"); st.rerun()
        else:
            st.warning("Chưa có shop nào đặt hàng cho Line này.")

    with tab3:
        st.subheader("Gom tổng SKU gửi Nhà cung cấp")
        line_sum = st.selectbox("Chọn Line gom đơn:", df_config['Line'].unique() if not df_config.empty else [])
        df_target = df_history[df_history['Line'] == line_sum]
        if not df_target.empty:
            summary = df_target.groupby(['SKU', 'TenSP', 'BienThe']).agg({'SoLuong': 'sum', 'GiaBan': 'first'}).reset_index()
            st.dataframe(summary, use_container_width=True)
            output = io.BytesIO(); summary.to_excel(output, index=False)
            st.download_button("📥 Tải file tổng gửi NCC", data=output.getvalue(), file_name=f"Tong_Dat_Hang_{line_sum}.xlsx")

# ---------------------------------------------------------
# GIAO DIỆN SHOP (CHI NHÁNH)
# ---------------------------------------------------------
else:
    st.title(f"🏬 Chi nhánh: {user_role}")
    line_sel = st.selectbox("Chọn Line hàng bạn muốn đặt:", df_config['Line'].unique() if not df_config.empty else [])
    
    if line_sel:
        # Lấy danh mục SP và Deadline của Line này
        df_line_cat = df_catalog[df_catalog['Line'] == line_sel]
        line_info = df_config[df_config['Line'] == line_sel].iloc[0]
        
        try:
            deadline = datetime.strptime(str(line_info['Deadline']), "%Y-%m-%d %H:%M:%S")
            is_expired = datetime.now() > deadline
        except:
            is_expired = False # Phòng trường hợp định dạng ngày sai

        if df_line_cat.empty:
            st.warning("Admin chưa đăng tải danh mục sản phẩm cho Line này.")
        elif is_expired:
            st.error(f"⌛ Đã hết hạn đặt hàng cho {line_sel} ({line_info['Deadline']})")
            st.dataframe(df_history[(df_history['Shop'] == user_role) & (df_history['Line'] == line_sel)], use_container_width=True)
        else:
            st.success(f"⏰ Hạn chót đặt hàng: {line_info['Deadline']}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### ✍️ Đặt hàng lẻ")
                with st.form("manual_form", clear_on_submit=True):
                    sp_name = st.selectbox("Sản phẩm", df_line_cat['TenSP'].unique())
                    bt_name = st.selectbox("Màu/Size", df_line_cat[df_line_cat['TenSP']==sp_name]['BienThe'].unique())
                    qty = st.number_input("Số lượng", min_value=1, step=1)
                    if st.form_submit_button("Xác nhận đặt"):
                        item = df_line_cat[(df_line_cat['TenSP']==sp_name) & (df_line_cat['BienThe']==bt_name)].iloc[0]
                        t_str = datetime.now().strftime("%H:%M %d/%m")
                        new_row = pd.DataFrame([{
                            'Ngày': t_now, 'Shop': user_role, 'Line': line_sel, 'TenSP': sp_name, 'BienThe': bt_name,
                            'SKU': str(item['SKU']), 'SoLuong': qty, 'GiaBan': item['DonGia'], 'TongTien': qty * item['DonGia'],
                            'GhiChu': "", 'LichSu': f"[Shop tạo lúc {t_str}]", 'Timestamp': datetime.now().timestamp()
                        }])
                        df_history = pd.concat([df_history, new_row], ignore_index=True)
                        save_data(df_history, "LichSu"); st.rerun()
            
            with c2:
                st.markdown("### 📁 Đặt hàng theo file")
                st.download_button("📥 Tải File Mẫu (Shop)", data=create_template(['SKU', 'SoLuong']), file_name="Mau_Dat_Hang_Shop.xlsx")
                up_file = st.file_uploader("Úp file mẫu đã điền", type=['xlsx'])
                if up_file and st.button("🚀 Gửi đơn hàng loạt"):
                    df_up = pd.read_excel(up_file, dtype={'SKU': str})
                    t_str = datetime.now().strftime("%H:%M %d/%m")
                    df_final = df_up.merge(df_line_cat, on='SKU', how='left')
                    df_final['Ngày'] = t_str; df_final['Shop'] = user_role; df_final['Line'] = line_sel
                    df_final['GiaBan'] = df_final['DonGia']; df_final['TongTien'] = df_final['SoLuong'] * df_final['GiaBan']
                    df_final['LichSu'] = f"[Shop úp file lúc {t_str}]"; df_final['Timestamp'] = datetime.now().timestamp()
                    df_history = pd.concat([df_history, df_final], ignore_index=True)
                    save_data(df_history, "LichSu"); st.success("Đã gửi đơn thành công!"); st.rerun()

        st.divider()
        st.subheader("📋 Trạng thái đơn của bạn (Tự động cập nhật)")
        my_orders = df_history[(df_history['Shop'] == user_role) & (df_history['Line'] == line_sel)]
        st.dataframe(my_orders, use_container_width=True)

with st.sidebar:
    st.write(f"Đăng nhập: **{user_role}**")
    if st.button("Đăng xuất"): st.session_state.logged_in = False; st.rerun()
