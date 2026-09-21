import io
import re
import numpy as np
import pandas as pd
import streamlit as st

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Taiwan Export Carrier Filter",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 Ứng dụng Phân loại & Tổng hợp Dữ liệu Export Taiwan")

st.sidebar.header("📂 Tải lên Dữ liệu")
uploaded_export_file = st.sidebar.file_uploader(
    "1. Chọn File Export (Excel/CSV)", type=["xlsx", "xls", "csv"]
)
uploaded_master_file = st.sidebar.file_uploader(
    "2. Chọn File Master Doanh Nghiệp (Excel/CSV)", type=["xlsx", "xls", "csv"]
)


def clean_mst(series: pd.Series) -> pd.Series:
    """Làm sạch MST: Xóa dấu ' ở đầu, khoảng trắng thừa và đưa về dạng chuỗi chuẩn."""
    return (
        series.astype(str)
        .str.replace(r"^'", "", regex=True)
        .str.strip()
        .replace(["nan", "None", "NaN", "<NA>"], "")
    )


if uploaded_export_file and uploaded_master_file:
    try:
        with st.spinner("Đang tải dữ liệu..."):
            if uploaded_export_file.name.endswith(".csv"):
                df_export = pd.read_csv(uploaded_export_file, dtype=str)
            else:
                df_export = pd.read_excel(uploaded_export_file, dtype=str)

            if uploaded_master_file.name.endswith(".csv"):
                df_master = pd.read_csv(uploaded_master_file, dtype=str)
            else:
                df_master = pd.read_excel(uploaded_master_file, dtype=str)

        # 1. Chuẩn hóa tên cột
        df_export.columns = df_export.columns.str.strip()
        df_master.columns = df_master.columns.str.strip()

        req_export = ["POD", "CARRIER", "MST SHIPPER", "TÊN SHIPPER TRÊN B/L"]
        missing_exp = [c for c in req_export if c not in df_export.columns]

        if missing_exp:
            st.error(f"File Export thiếu các cột bắt buộc: {missing_exp}")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 1: LỌC TAIWAN PORTS (POD)
        # ---------------------------------------------------------------------
        taiwan_ports = [
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
        pattern_pod = "|".join(taiwan_ports)

        df_taiwan = df_export[
            df_export["POD"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.contains(pattern_pod, regex=True)
        ].copy()

        st.info(
            f"📊 Tìm thấy **{len(df_taiwan)}** dòng lô hàng xuất khẩu đi Taiwan."
        )

        if len(df_taiwan) == 0:
            st.warning("Không tìm thấy dữ liệu phù hợp với các mã cảng Taiwan!")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 2: CHUẨN HÓA MST SHIPPER
        # ---------------------------------------------------------------------
        df_taiwan["MST_SHIPPER_CLEAN"] = clean_mst(df_taiwan["MST SHIPPER"])

        if "MST SHIPPER" in df_master.columns:
            df_master["MST_SHIPPER_CLEAN"] = clean_mst(df_master["MST SHIPPER"])
        else:
            st.error("File Master không có cột 'MST SHIPPER'!")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 3: MERGE VỚI FILE MASTER & LOGIC FALLBACK TÊN DN
        # ---------------------------------------------------------------------
        master_info_cols = [
            "Tên DN(Tiếng Việt)",
            "Tên DN(Tiếng Anh)",
            "Ngành nghề KD",
            "Mặt hàng XNK chính",
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

        existing_master_cols = [
            c for c in master_info_cols if c in df_master.columns
        ]

        # Khử trùng lặp trong File Master trước khi Merge
        master_subset = df_master[
            ["MST_SHIPPER_CLEAN"] + existing_master_cols
        ].drop_duplicates(subset=["MST_SHIPPER_CLEAN"], keep="first")

        # Merge thông tin Master vào Export
        df_merged = pd.merge(
            df_taiwan,
            master_subset,
            on="MST_SHIPPER_CLEAN",
            how="left",
            suffixes=("", "_master"),
        )

        # Fallback tên DN: Nếu thiếu/rỗng từ Master thì lấy 'TÊN SHIPPER TRÊN B/L'
        if "Tên DN(Tiếng Việt)" not in df_merged.columns:
            df_merged["Tên DN(Tiếng Việt)"] = np.nan

        df_merged["Tên DN(Tiếng Việt)"] = np.where(
            (df_merged["Tên DN(Tiếng Việt)"].isna())
            | (
                df_merged["Tên DN(Tiếng Việt)"]
                .astype(str)
                .str.strip()
                .isin(["", "nan", "None"])
            ),
            df_merged["TÊN SHIPPER TRÊN B/L"],
            df_merged["Tên DN(Tiếng Việt)"],
        )

        # Cập nhật cột MST SHIPPER chính thức đã làm sạch
        df_merged["MST SHIPPER"] = df_merged["MST_SHIPPER_CLEAN"]

        # Cột phụ bổ sung từ Export nếu chưa có
        for extra_col in ["MST AGENT", "AGENT HANDLE NAME & SHIPPER"]:
            if extra_col not in df_merged.columns:
                df_merged[extra_col] = ""

        # Cấu trúc các cột chuẩn Final
        target_columns = [
            "MST SHIPPER",
            "Tên DN(Tiếng Việt)",
            "MST AGENT",
            "AGENT HANDLE NAME & SHIPPER",
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

        for col in target_columns:
            if col not in df_merged.columns:
                df_merged[col] = ""

        df_final_all = df_merged[target_columns].copy()

        # ---------------------------------------------------------------------
        # BƯỚC 4: LỌC PHÂN LOẠI CARRIER (OCL / OOCL VS CÁC HÃNG TÀU KHÁC)
        # ---------------------------------------------------------------------
        carrier_clean = (
            df_final_all["CARRIER"].fillna("").astype(str).str.strip().str.upper()
        )

        is_ocl = carrier_clean.str.contains(
            r"\bOCL\b|\bOOCL\b|\bOOL\b|ORIENT OVERSEAS", regex=True
        )

        df_ocl_raw = df_final_all[is_ocl].copy()
        df_non_ocl_raw = df_final_all[~is_ocl].copy()

        # ---------------------------------------------------------------------
        # BƯỚC 5: KHỬ TRÙNG LẶP (ĐẢM BẢO MỖI MST SHIPPER CHỈ XUẤT HIỆN 1 LẦN)
        # ---------------------------------------------------------------------
        # Loại bỏ các dòng bị trống MST SHIPPER
        df_ocl_valid = df_ocl_raw[
            df_ocl_raw["MST SHIPPER"].str.strip() != ""
        ].copy()
        df_non_ocl_valid = df_non_ocl_raw[
            df_non_ocl_raw["MST SHIPPER"].str.strip() != ""
        ].copy()

        # Giữ lại dòng đầu tiên cho mỗi MST SHIPPER
        df_ocl = df_ocl_valid.drop_duplicates(
            subset=["MST SHIPPER"], keep="first"
        ).reset_index(drop=True)
        df_non_ocl = df_non_ocl_valid.drop_duplicates(
            subset=["MST SHIPPER"], keep="first"
        ).reset_index(drop=True)

        # ---------------------------------------------------------------------
        # BƯỚC 6: HIỂN THỊ KẾT QUẢ VÀ TẢI FILE
        # ---------------------------------------------------------------------
        st.success("✅ Đã xử lý & khử trùng lặp thành công!")

        col1, col2 = st.columns(2)

        # --- CỘT 1: FILE OCL / OOCL ---
        with col1:
            st.subheader(f"1. Doanh nghiệp dùng Carrier OCL ({len(df_ocl)} DN)")
            st.dataframe(df_ocl, use_container_width=True, height=300)

            buffer_ocl = io.BytesIO()
            with pd.ExcelWriter(buffer_ocl, engine="openpyxl") as writer:
                df_ocl.to_excel(
                    writer, index=False, sheet_name="OCL_Shippers_Unique"
                )

            st.download_button(
                label="📥 Tải File 1: Danh sách OCL (Đã lọc trùng MST) (.xlsx)",
                data=buffer_ocl.getvalue(),
                file_name="Taiwan_Export_OCL_Unique_Shippers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_ocl",
            )

        # --- CỘT 2: FILE NON-OCL ---
        with col2:
            st.subheader(
                f"2. Doanh nghiệp dùng Carrier khác ({len(df_non_ocl)} DN)"
            )
            st.dataframe(df_non_ocl, use_container_width=True, height=300)

            buffer_non_ocl = io.BytesIO()
            with pd.ExcelWriter(buffer_non_ocl, engine="openpyxl") as writer:
                df_non_ocl.to_excel(
                    writer, index=False, sheet_name="Non_OCL_Shippers_Unique"
                )

            st.download_button(
                label="📥 Tải File 2: Danh sách Carrier Khác (Đã lọc trùng MST) (.xlsx)",
                data=buffer_non_ocl.getvalue(),
                file_name="Taiwan_Export_Non_OCL_Unique_Shippers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_download_non_ocl",
            )

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        st.exception(e)

else:
    st.info("👋 Vui lòng tải lên đầy đủ cả File Export và File Master ở góc trái.")
