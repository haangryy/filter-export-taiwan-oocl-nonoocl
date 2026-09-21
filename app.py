import io
import pandas as pd
import streamlit as st

# Danh sách mã cảng Taiwan
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

# Danh sách 15 cột đầu ra chuẩn
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

# 1. Upload files
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


if file_export is not None and file_master is not None:
    try:
        df_export = load_data(file_export)
        df_master = load_data(file_master)

        st.success("Đã tải xong 2 file dữ liệu!")

        # Ghép khớp cột
        st.write("---")
        st.subheader("Kiểm tra tên các cột ghép nối:")
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
            # Lọc POD đi Taiwan
            pattern = "|".join(TAIWAN_POD_KEYWORDS)
            df_taiwan = df_export[
                df_export[col_pod]
                .astype(str)
                .str.upper()
                .str.contains(pattern, na=False)
            ].copy()

            # Tách OCL và Non-OCL
            is_ocl = (
                df_taiwan[col_carrier]
                .astype(str)
                .str.upper()
                .str.strip()
                .str.contains("OCL", na=False)
            )

            df_ocl_exp = df_taiwan[is_ocl].copy()
            df_non_ocl_exp = df_taiwan[~is_ocl].copy()

            # Merge dữ liệu
            df_master[col_mst_master] = (
                df_master[col_mst_master].astype(str).str.strip()
            )

            def process_merge(df_sub):
                if df_sub.empty:
                    return pd.DataFrame(columns=FINAL_COLUMNS)

                df_sub[col_mst_exp] = (
                    df_sub[col_mst_exp].astype(str).str.strip()
                )

                merged = pd.merge(
                    df_sub,
                    df_master,
                    left_on=col_mst_exp,
                    right_on=col_mst_master,
                    how="left",
                    suffixes=("", "_master"),
                )

                # Khử trùng lặp theo MST
                merged = merged.drop_duplicates(subset=[col_mst_exp])

                # Build kết quả chuẩn 15 cột
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
            st.subheader("Kết quả lọc:")
            m1, m2, m3 = st.columns(3)
            m1.metric("Tổng lô xuất Taiwan", len(df_taiwan))
            m2.metric("Số DN dùng OCL", len(final_ocl))
            m3.metric("Số DN dùng Carrier khác", len(final_non_ocl))

            col_down1, col_down2 = st.columns(2)
            with col_down1:
                st.write("### File 1: Doanh nghiệp dùng OCL")
                st.dataframe(final_ocl.head(5))
                st.download_button(
                    label="Tải về File OCL (.xlsx)",
                    data=to_excel_bytes(final_ocl),
                    file_name="DS_DoanhNghiep_Taiwan_Carrier_OCL.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with col_down2:
                st.write("### File 2: Doanh nghiệp dùng Carrier Khác")
                st.dataframe(final_non_ocl.head(5))
                st.download_button(
                    label="Tải về File Non-OCL (.xlsx)",
                    data=to_excel_bytes(final_non_ocl),
                    file_name="DS_DoanhNghiep_Taiwan_Carrier_Non_OCL.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    except Exception as e:
        st.error(f"Lỗi xử lý file: {e}")