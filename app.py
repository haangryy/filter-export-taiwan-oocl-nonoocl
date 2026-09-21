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
        .str.replace(r"^'", "", regex=True)  # Xóa dấu ' ở đầu
        .str.strip()
        .replace(["nan", "None", "NaN", "<NA>"], "")
    )


if uploaded_export_file and uploaded_master_file:
    try:
        with st.spinner("Đang tải dữ liệu..."):
            # 1. Đọc file
            if uploaded_export_file.name.endswith(".csv"):
                df_export = pd.read_csv(uploaded_export_file, dtype=str)
            else:
                df_export = pd.read_excel(uploaded_export_file, dtype=str)

            if uploaded_master_file.name.endswith(".csv"):
                df_master = pd.read_csv(uploaded_master_file, dtype=str)
            else:
                df_master = pd.read_excel(uploaded_master_file, dtype=str)

        # Chuẩn hóa tên cột (xóa khoảng trắng thừa ở đầu/cuối tên cột)
        df_export.columns = df_export.columns.str.strip()
        df_master.columns = df_master.columns.str.strip()

        # Kiểm tra cột bắt buộc
        req_export = [
            "POD",
            "CARRIER",
            "MST SHIPPER",
            "TÊN SHIPPER TRÊN B/L",
        ]
        missing_exp = [c for c in req_export if c not in df_export.columns]

        if missing_exp:
            st.error(f"File Export thiếu các cột bắt buộc: {missing_exp}")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 1: LỌC DATA TAIWAN BẰNG CỘT 'POD'
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

        # Biểu thức chính quy tìm các mã cảng Taiwan
        pattern_pod = "|".join(taiwan_ports)
        df_taiwan = df_export[
            df_export["POD"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.contains(pattern_pod, regex=True)
        ].copy()

        st.info(
            f"📊 Tìm thấy **{len(df_taiwan)}** dòng xuất khẩu đi Taiwan (trên tổng số {len(df_export)} dòng)."
        )

        if len(df_taiwan) == 0:
            st.warning("Không tìm thấy dữ liệu phù hợp với các mã cảng Taiwan!")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 2: FIX LỖI MST SHIPPER (XÓA DẤU ' Ở ĐẦU)
        # ---------------------------------------------------------------------
        df_taiwan["MST SHIPPER_CLEAN"] = clean_mst(df_taiwan["MST SHIPPER"])

        if "MST SHIPPER" in df_master.columns:
            df_master["MST SHIPPER_CLEAN"] = clean_mst(df_master["MST SHIPPER"])
        else:
            st.error("File Master không có cột 'MST SHIPPER'!")
            st.stop()

        # ---------------------------------------------------------------------
        # BƯỚC 3: MERGE VỚI FILE MASTER & LOGIC FALLBACK
        # ---------------------------------------------------------------------
        # Danh sách các cột mong muốn lấy từ File Master
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

        # Chỉ lấy những cột thực sự có trong File Master
        existing_master_cols = [
            c for c in master_info_cols if c in df_master.columns
        ]

        # Bổ sung cột 'MST SHIPPER_CLEAN' vào danh sách dùng để merge
        master_subset = df_master[
            ["MST SHIPPER_CLEAN"] + existing_master_cols
        ].drop_duplicates(subset=["MST SHIPPER_CLEAN"])

        # Thực hiện Left Join
        df_merged = pd.merge(
            df_taiwan,
            master_subset,
            on="MST SHIPPER_CLEAN",
            how="left",
            suffixes=("", "_master"),
        )

        # Logic Fallback cho 'Tên DN(Tiếng Việt)':
        # Nếu thiếu/rỗng trong Master -> Lấy 'TÊN SHIPPER TRÊN B/L' của File Export
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

        # Đảm bảo các cột cần chèn tồn tại (nếu trong Export chưa có)
        for extra_col in ["MST AGENT", "AGENT HANDLE NAME & SHIPPER"]:
            if extra_col not in df_merged.columns:
                df_merged[extra_col] = ""

        # ---------------------------------------------------------------------
        # BƯỚC 4: SẮP XẾP & LỌC CÁC CỘT THEO YÊU CẦU FINAL FILE
        # ---------------------------------------------------------------------
        final_column_structure = [
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

        # Bổ sung các cột chưa tồn tại thành cột trống
        for col in final_column_structure:
            if col not in df_merged.columns:
                df_merged[col] = ""

        # Cập nhật lại giá trị MST SHIPPER đã làm sạch
        df_merged["MST SHIPPER"] = df_merged["MST SHIPPER_CLEAN"]

        # Trích xuất đúng cấu hình cột Final
        df_final_all = df_merged[final_column_structure].copy()

        # ---------------------------------------------------------------------
        # BƯỚC 5: TÁCH THÀNH 2 FILE (OOCL VS NON-OOCL)
        # ---------------------------------------------------------------------
        # Lọc các carrier chứa từ khóa OOCL hoặc OOL
        pattern_ocl = r"\b(OCL|OOCL|OOL)\b|OCL|OOCL|OOL"
        is_oocl = (
            df_final_all["CARRIER"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.contains("OOCL|OOL", regex=True)
        )

        df_oocl = df_final_all[is_oocl].reset_index(drop=True)
        df_non_oocl = df_final_all[~is_oocl].reset_index(drop=True)

        # ---------------------------------------------------------------------
        # BƯỚC 6: HIỂN THỊ KẾT QUẢ VÀ TẢI FILE
        # ---------------------------------------------------------------------
        st.success("Xử lý và tổng hợp dữ liệu thành công!")

        col1, col2 = st.columns(2)

        # --- CỘT 1: FILE OOCL ---
        with col1:
            st.subheader(f"1. Doanh nghiệp dùng Hãng tàu OOCL ({len(df_oocl)})")
            st.dataframe(df_oocl.head(10), use_container_width=True)

            buffer_oocl = io.BytesIO()
            with pd.ExcelWriter(buffer_oocl, engine="openpyxl") as writer:
                df_oocl.to_excel(
                    writer, index=False, sheet_name="Taiwan_OOCL_Shippers"
                )

            st.download_button(
                label="📥 Tải xuống File OOCL (.xlsx)",
                data=buffer_oocl.getvalue(),
                file_name="Taiwan_Export_OOCL_Shippers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_oocl",
            )

        # --- CỘT 2: FILE NON-OOCL ---
        with col2:
            st.subheader(
                f"2. Doanh nghiệp dùng Hãng tàu còn lại ({len(df_non_oocl)})"
            )
            st.dataframe(df_non_oocl.head(10), use_container_width=True)

            buffer_non_oocl = io.BytesIO()
            with pd.ExcelWriter(buffer_non_oocl, engine="openpyxl") as writer:
                df_non_oocl.to_excel(
                    writer, index=False, sheet_name="Taiwan_NonOOCL_Shippers"
                )

            st.download_button(
                label="📥 Tải xuống File Non-OOCL (.xlsx)",
                data=buffer_non_oocl.getvalue(),
                file_name="Taiwan_Export_NonOOCL_Shippers.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btn_non_oocl",
            )

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")
        st.exception(e)

else:
    st.info("👋 Vui lòng tải lên cả 2 file (File Export & File Master) ở cột bên trái để bắt đầu.")
