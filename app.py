import io
import pandas as pd
import streamlit as st

# Danh sách Port Code cảng Đài Loan (Taiwan)
TAIWAN_POD_KEYWORDS = [
    "TWTXG",
    "TWTPE",
    "TWKEL",
    "TWKHH",
    "TWTYU",
    "TW042",
    "TWWT1",
    "TWTAW",
    "TW078",
]

# Danh sách 15 cột bắt buộc của File Final
FINAL_COLUMNS = [
    "MST SHIPPER",
    "Tên DN(Tiếng Việt)",
    "Tên DN(Tiếng Anh)",
    "Ngành nghề KD",
    "Mặt hàng XNK chính",
    "CARRIER",
    "Điện thoại",
    "Website",
    "Email",
    "Lãnh đạo",
    "Nhân viên làm Thủ tục XNK",
    "Nhân viên của DN làm Thủ tục XNK",
    "Người phụ trách XNK",
    "ĐT người phụ trách XNK",
    "Email người phụ trách XNK",
]

st.set_page_config(
    page_title="Lọc Data Export Taiwan & Carrier", layout="wide"
)
st.title("Ứng dụng Lọc & Đối chiếu Data Doanh Nghiệp Xuất Khẩu Taiwan")

# 1. Tải lên 2 file dữ liệu
col1, col2 = st.columns(2)
with col1:
    file_export = st.file_uploader(
        "1. Upload File Export (Chứa POD, CARRIER, MST SHIPPER)",
        type=["xlsx", "xls", "csv"],
    )
with col2:
    file_master = st.file_uploader(
        "2. Upload File Master Danh Bạ Doanh Nghiệp",
        type=["xlsx", "xls", "csv"],
    )


def load_data(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file, dtype=str)
    return pd.read_excel(file, dtype=str)


def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# Hàm làm sạch dấu nháy đơn ' và khoảng trắng thừa trong Mã Số Thuế
def clean_mst(series):
    return (
        series.astype(str)
        .str.replace("'", "", regex=False)  # Loại bỏ dấu nháy đơn ở đầu/trong chuỗi
        .str.replace('"', "", regex=False)  # Loại bỏ dấu nháy kép nếu có
        .str.strip()  # Loại bỏ khoảng trắng thừa ở 2 đầu
    )


if file_export is not None and file_master is not None:
    try:
        df_export = load_data(file_export)
        df_master = load_data(file_master)

        st.success("Tải thành công cả 2 file dữ liệu!")

        st.write("---")
        st.subheader("Kiểm tra & Khớp cột giữa các file:")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            col_pod = st.selectbox(
                "Cột POD:",
                df_export.columns,
                index=(
                    df_export.columns.get_loc("POD")
                    if "POD" in df_export.columns
                    else 0
                ),
            )
        with c2:
            col_carrier = st.selectbox(
                "Cột CARRIER:",
                df_export.columns,
                index=(
                    df_export.columns.get_loc("CARRIER")
                    if "CARRIER" in df_export.columns
                    else 0
                ),
            )
        with c3:
            col_mst_exp = st.selectbox(
                "Cột MST SHIPPER (File Export):",
                df_export.columns,
                index=(
                    df_export.columns.get_loc("MST SHIPPER")
                    if "MST SHIPPER" in df_export.columns
                    else 0
                ),
            )
        with c4:
            col_mst_master = st.selectbox(
                "Cột MST SHIPPER (File Master):",
                df_master.columns,
                index=(
                    df_master.columns.get_loc("MST SHIPPER")
                    if "MST SHIPPER" in df_master.columns
                    else 0
                ),
            )

        if st.button("Tiến hành Lọc & Tách File", type="primary"):
            # Bước 1: Lọc dữ liệu xuất đi Taiwan
            pattern = "|".join(TAIWAN_POD_KEYWORDS)
            df_taiwan = df_export[
                df_export[col_pod]
                .astype(str)
                .str.upper()
                .str.contains(pattern, na=False)
            ].copy()

            # Bước 2: Tách hãng tàu OCL và Carrier khác
            is_ocl = (
                df_taiwan[col_carrier]
                .astype(str)
                .str.upper()
                .str.strip()
                .str.contains("OCL", na=False)
            )

            df_ocl_exp = df_taiwan[is_ocl].copy()
            df_non_ocl_exp = df_taiwan[~is_ocl].copy()

            # Làm sạch MST trong file Master
            df_master[col_mst_master] = clean_mst(df_master[col_mst_master])

            # Hàm Merge đối chiếu dữ liệu với File Master đã làm sạch
            def process_merge(df_sub):
                if df_sub.empty:
                    return pd.DataFrame(columns=FINAL_COLUMNS)

                # Làm sạch MST trong file Export
                df_sub[col_mst_exp] = clean_mst(df_sub[col_mst_exp])

                # Loại bỏ dòng MST rỗng hoặc không hợp lệ
                df_sub_clean = df_sub[
                    ~df_sub[col_mst_exp].isin(["nan", "None", ""])
                ].copy()

                merged = pd.merge(
                    df_sub_clean,
                    df_master,
                    left_on=col_mst_exp,
                    right_on=col_mst_master,
                    how="left",
                    suffixes=("", "_master"),
                )

                # Loại bỏ trùng lặp theo Mã số thuế
                merged = merged.drop_duplicates(subset=[col_mst_exp])

                # Khởi tạo kết quả đủ 15 cột
                res = pd.DataFrame()
                for col in FINAL_COLUMNS:
                    if col in merged.columns:
                        res[col] = merged[col]
                    elif f"{col}_master" in merged.columns:
                        res[col] = merged[f"{col}_master"]
                    elif col == "MST SHIPPER":
                        res[col] = merged[col_mst_exp]
                    elif col == "CARRIER":
                        res[col] = merged[col_carrier]
                    else:
                        res[col] = ""
                return res[FINAL_COLUMNS]

            final_ocl = process_merge(df_ocl_exp)
            final_non_ocl = process_merge(df_non_ocl_exp)

            # Hiển thị kết quả & Download
            st.write("---")
            st.subheader("Kết quả xử lý:")
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng lô xuất Taiwan", len(df_taiwan))
            m2.metric("Số DN dùng Carrier OCL", len(final_ocl))
            m3.metric("Số DN dùng Carrier khác", len(final_non_ocl))

            col_down1, col_down2 = st.columns(2)
            with col_down1:
                st.write("### File 1: Doanh nghiệp sử dụng OCL")
                st.dataframe(final_ocl.head(5))
                st.download_button(
                    label="Tải về File OCL (.xlsx)",
                    data=to_excel_bytes(final_ocl),
                    file_name="DS_DoanhNghiep_Taiwan_Carrier_OCL.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with col_down2:
                st.write("### File 2: Doanh nghiệp sử dụng Carrier Khác")
                st.dataframe(final_non_ocl.head(5))
                st.download_button(
                    label="Tải về File Non-OCL (.xlsx)",
                    data=to_excel_bytes(final_non_ocl),
                    file_name="DS_DoanhNghiep_Taiwan_Carrier_Non_OCL.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    except Exception as e:
        st.error(f"Xảy ra lỗi xử lý file: {e}")
