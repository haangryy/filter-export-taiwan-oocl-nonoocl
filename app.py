import io
import numpy as np
import pandas as pd
import streamlit as st

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Filter & Process Export Data",
    layout="wide",
)

st.title("Ứng dụng Xử lý & Đổi tên Doanh nghiệp (Export Data)")

st.sidebar.header("Tải lên dữ liệu")
uploaded_export_file = st.sidebar.file_uploader(
    "1. Chọn File Export (Excel/CSV)", type=["xlsx", "xls", "csv"]
)
uploaded_master_file = st.sidebar.file_uploader(
    "2. Chọn File Master (Excel/CSV)", type=["xlsx", "xls", "csv"]
)

if uploaded_export_file and uploaded_master_file:
    try:
        # ==========================================
        # 1. ĐỌC DỮ LIỆU
        # ==========================================
        with st.spinner("Đang đọc dữ liệu..."):
            if uploaded_export_file.name.endswith(".csv"):
                df_export = pd.read_csv(uploaded_export_file)
            else:
                df_export = pd.read_excel(uploaded_export_file)

            if uploaded_master_file.name.endswith(".csv"):
                df_master = pd.read_csv(uploaded_master_file)
            else:
                df_master = pd.read_excel(uploaded_master_file)

        # Kiểm tra các cột bắt buộc
        req_export_cols = ["MST SHIPPER", "TÊN SHIPPER TRÊN B/L"]
        req_master_cols = ["MST SHIPPER", "Tên DN(Tiếng Việt)"]

        missing_export = [
            col for col in req_export_cols if col not in df_export.columns
        ]
        missing_master = [
            col for col in req_master_cols if col not in df_master.columns
        ]

        if missing_export or missing_master:
            if missing_export:
                st.error(f"File Export thiếu các cột: {missing_export}")
            if missing_master:
                st.error(f"File Master thiếu các cột: {missing_master}")
        else:
            # ==========================================
            # 2. MERGE & FALLBACK LOGIC
            # ==========================================
            with st.spinner("Đang xử lý ghép dữ liệu & Fallback tên DN..."):
                # Ép kiểu MST về string để tránh lỗi merge do lệch kiểu dữ liệu
                df_export["MST SHIPPER"] = (
                    df_export["MST SHIPPER"].astype(str).str.strip()
                )
                df_master["MST SHIPPER"] = (
                    df_master["MST SHIPPER"].astype(str).str.strip()
                )

                # Merge / Lookup từ File Master sang Export
                df_merged = pd.merge(
                    df_export,
                    df_master[["MST SHIPPER", "Tên DN(Tiếng Việt)"]],
                    on="MST SHIPPER",
                    how="left",
                )

                # Logic Fallback: Nếu không tìm thấy hoặc rỗng thì lấy 'TÊN SHIPPER TRÊN B/L'
                df_merged["Tên DN(Tiếng Việt)"] = np.where(
                    (df_merged["Tên DN(Tiếng Việt)"].isna())
                    | (
                        df_merged["Tên DN(Tiếng Việt)"]
                        .astype(str)
                        .str.strip()
                        == ""
                    ),
                    df_merged["TÊN SHIPPER TRÊN B/L"],
                    df_merged["Tên DN(Tiếng Việt)"],
                )

                # ==========================================
                # 3. SẮP XẾP LẠI THỨ TỰ CÁC CỘT
                # ==========================================
                cols = list(df_merged.columns)

                # Loại bỏ các cột cần chèn/di chuyển để tránh trùng
                target_cols = [
                    "Tên DN(Tiếng Việt)",
                    "MST AGENT",
                    "AGENT HANDLE NAME & SHIPPER",
                ]
                for col in target_cols:
                    if col in cols:
                        cols.remove(col)

                # Tìm vị trí ngay sau cột 'TÊN SHIPPER TRÊN B/L'
                if "TÊN SHIPPER TRÊN B/L" in cols:
                    insert_loc = cols.index("TÊN SHIPPER TRÊN B/L") + 1
                    new_col_order = (
                        cols[:insert_loc] + target_cols + cols[insert_loc:]
                    )
                else:
                    new_col_order = cols + target_cols

                # Giữ lại những cột thực sự tồn tại trong DataFrame
                final_cols = [c for c in new_col_order if c in df_merged.columns]
                df_final = df_merged[final_cols]

            st.success("Xử lý dữ liệu thành công!")

            # Hiển thị xem trước dữ liệu
            st.subheader("Dữ liệu sau khi xử lý (Preview):")
            st.dataframe(df_final.head(10))

            # ==========================================
            # 4. TẠO FILE EXCEL ĐỂ TẢI VỀ
            # ==========================================
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_final.to_excel(writer, index=False, sheet_name="Data_Final")
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Tải xuống File Excel Hoàn Chỉnh",
                data=processed_data,
                file_name="File_Final_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")

else:
    st.info("Vui lòng tải lên đầy đủ cả 2 file ở thanh bên trái để bắt đầu.")
