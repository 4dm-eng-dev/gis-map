import streamlit as st
import pandas as pd
import numpy as np
import rasterio
from pyproj import Transformer
import plotly.graph_objects as go
import base64
from io import BytesIO
from PIL import Image

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(layout="wide")
st.title("🗺️ Interactive Cadastral Map Viewer")

# =========================================================
# SESSION STATE
# =========================================================
if "transformer" not in st.session_state:
    st.session_state.transformer = Transformer.from_crs(
        "EPSG:4326",
        "EPSG:22992",
        always_xy=True
    )

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.header("Control Panel")

csv_file = st.sidebar.file_uploader(
    "1. Load Cadastral CSV",
    type="csv"
)

# =========================================================
# MAIN
# =========================================================
if csv_file:

    try:
        # -------------------------------------------------
        # READ CSV
        # -------------------------------------------------
        df = pd.read_csv(
            csv_file,
            sep=";",
            encoding="utf-8-sig"
        )

        # -------------------------------------------------
        # CLEAN COLUMN NAMES
        # -------------------------------------------------
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
        )

        # DEBUG
        st.write("Detected columns:", df.columns.tolist())
        st.write(df.head())

        # -------------------------------------------------
        # CHECK REQUIRED COLUMNS
        # -------------------------------------------------
        if "x" not in df.columns or "y" not in df.columns:
            st.error("CSV must contain columns named x and y")
            st.stop()

        # -------------------------------------------------
        # CONVERT TO NUMERIC
        # -------------------------------------------------
        df["x"] = pd.to_numeric(df["x"], errors="coerce")
        df["y"] = pd.to_numeric(df["y"], errors="coerce")

        # REMOVE INVALID ROWS
        df = df.dropna(subset=["x", "y"])

        if len(df) == 0:
            st.error("No valid coordinate rows found.")
            st.stop()

        # -------------------------------------------------
        # TRANSFORM COORDINATES
        # -------------------------------------------------
        xs, ys = st.session_state.transformer.transform(
            df["x"].values,
            df["y"].values
        )

        xs = np.array(xs)
        ys = np.array(ys)

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------
        st.write("X range:", np.min(xs), np.max(xs))
        st.write("Y range:", np.min(ys), np.max(ys))

        # -------------------------------------------------
        # CENTROID
        # -------------------------------------------------
        centroid_x = np.mean(xs)
        centroid_y = np.mean(ys)

        map_x = int(centroid_x / 1500) * 1.5
        map_y = int(centroid_y / 1000)

        map_number = f"{map_y}/{map_x}"

        st.sidebar.success(f"Sheet No: {map_number}")

        # =================================================
        # TIFF FILE
        # =================================================
        tif_file = st.sidebar.file_uploader(
            f"2. Load TIFF File (Map {map_number})",
            type=["tif", "tiff"]
        )

        # =================================================
        # STYLE CONTROLS
        # =================================================
        marker_color = st.sidebar.selectbox(
            "Color",
            ["red", "blue", "green", "black", "orange", "purple"]
        )

        marker_size = st.sidebar.slider(
            "Size",
            2,
            20,
            6
        )

        # =================================================
        # FIGURE
        # =================================================
        fig = go.Figure()

        # -------------------------------------------------
        # TIFF BACKGROUND
        # -------------------------------------------------
        if tif_file:

            with rasterio.open(tif_file) as src:

                left, bottom, right, top = src.bounds

                img = src.read()

                # Handle grayscale
                if img.shape[0] == 1:
                    img = np.repeat(img, 3, axis=0)

                # RGB only
                img = np.transpose(img[:3], (1, 2, 0))

                # Normalize
                img = img.astype(np.float32)

                img = (
                    (img - img.min()) /
                    (img.max() - img.min() + 1e-9)
                )

                img = (img * 255).astype(np.uint8)

                # PIL conversion
                pil_img = Image.fromarray(img)

                buffer = BytesIO()

                pil_img.save(buffer, format="PNG")

                encoded = base64.b64encode(
                    buffer.getvalue()
                ).decode()

                fig.add_layout_image(
                    dict(
                        source="data:image/png;base64," + encoded,
                        xref="x",
                        yref="y",
                        x=left,
                        y=top,
                        sizex=(right - left),
                        sizey=(top - bottom),
                        sizing="stretch",
                        opacity=1,
                        layer="below"
                    )
                )

        # -------------------------------------------------
        # SURVEY POINTS
        # -------------------------------------------------
        fig.add_trace(go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker=dict(
                size=marker_size,
                color=marker_color,
                line=dict(width=1, color="black")
            ),
            name="Survey Points"
        ))

        # -------------------------------------------------
        # CENTROID
        # -------------------------------------------------
        fig.add_trace(go.Scatter(
            x=[centroid_x],
            y=[centroid_y],
            mode="markers",
            marker=dict(
                size=14,
                color="blue"
            ),
            name="Centroid"
        ))

        # =================================================
        # AUTO ZOOM
        # =================================================
        pad_x = max(
            (np.max(xs) - np.min(xs)) * 0.1,
            10
        )

        pad_y = max(
            (np.max(ys) - np.min(ys)) * 0.1,
            10
        )

        fig.update_layout(
            title=f"🗺️ Cadastral Map — Sheet {map_number}",
            height=850,
            dragmode="pan",
            paper_bgcolor="#34d5eb",
            plot_bgcolor="#bff3fb"
        )

        fig.update_xaxes(
            range=[
                np.min(xs) - pad_x,
                np.max(xs) + pad_x
            ],
            showgrid=True
        )

        fig.update_yaxes(
            range=[
                np.min(ys) - pad_y,
                np.max(ys) + pad_y
            ],
            scaleanchor="x",
            scaleratio=1,
            showgrid=True
        )

        # =================================================
        # OUTPUT
        # =================================================
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"scrollZoom": True}
        )

    except Exception as e:
        st.exception(e)

else:
    st.info("Upload a CSV file to start mapping.")