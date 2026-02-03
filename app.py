import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image, PageBreak
)

# =====================================================
# STREAMLIT UI
# =====================================================
st.set_page_config(page_title="FC Daily Charging Report", layout="centered")
st.title("⚡ FC Daily Charging Report Generator")

uploaded_file = st.file_uploader(
    "Upload Charging Session Excel / CSV",
    type=["csv", "xlsx"]
)

if uploaded_file:
    # ================= LOAD DATA =================
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()

    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce")
    df["End Time"] = pd.to_datetime(df["End Time"], errors="coerce")
    df["Date"] = df["Start Time"].dt.date

    dates = sorted(df["Date"].dropna().unique())
    report_date = st.selectbox("Select Report Date", dates)

    daily_df = df[df["Date"] == report_date].copy()
    if daily_df.empty:
        st.error("No data available for selected date.")
        st.stop()

    daily_df["Driver Name"] = daily_df["Device ID"].astype(str)

    # ================= KPIs =================
    total_sessions = len(daily_df)
    total_energy = round(pd.to_numeric(daily_df["Usage (kWh)"], errors="coerce").sum(), 2)

    # ================= DRIVER DATA (TOP 8 + OTHERS) =================
    driver_usage = (
        daily_df.groupby("Driver Name", as_index=False)["Usage (kWh)"]
        .sum()
        .sort_values("Usage (kWh)", ascending=False)
    )

    top_drivers = driver_usage.head(8)
    other_drivers = driver_usage.iloc[8:]["Usage (kWh)"].sum()

    if other_drivers > 0:
        top_drivers = pd.concat([
            top_drivers,
            pd.DataFrame([{"Driver Name": "Others", "Usage (kWh)": other_drivers}])
        ])

    # ================= HUB DATA (TOP 6 + OTHERS) =================
    hub_usage = (
        daily_df.groupby("Hub Name", as_index=False)["Usage (kWh)"]
        .sum()
        .sort_values("Usage (kWh)", ascending=False)
    )

    top_hubs = hub_usage.head(6)
    other_hubs = hub_usage.iloc[6:]["Usage (kWh)"].sum()

    if other_hubs > 0:
        top_hubs = pd.concat([
            top_hubs,
            pd.DataFrame([{"Hub Name": "Others", "Usage (kWh)": other_hubs}])
        ])

    # ================= DRIVER BAR CHART (ONLY VALUE FORMAT CHANGED) =================
    fig_driver = px.bar(
        top_drivers,
        x="Usage (kWh)",
        y="Driver Name",
        orientation="h",
        text=top_drivers["Usage (kWh)"].round(2),  # ✅ ONLY CHANGE
        title="Driver-wise Energy Usage (kWh)",
        color_discrete_sequence=["#2563eb"]
    )

    fig_driver.update_traces(textposition="outside")
    fig_driver.update_layout(
        height=520,
        font=dict(size=14),
        title_font_size=18,
        margin=dict(l=180, r=40, t=60, b=40)
    )

    # ================= HUB DONUT CHART =================
    fig_hub = px.pie(
        top_hubs,
        names="Hub Name",
        values="Usage (kWh)",
        hole=0.5,
        title="Hub-wise Energy Distribution",
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    fig_hub.update_traces(
        textinfo="percent+label",
        textposition="inside",
        insidetextfont=dict(size=16)
    )
    fig_hub.update_layout(
        height=520,
        font=dict(size=14),
        title_font_size=18,
        legend=dict(
            orientation="h",
            y=-0.2,
            x=0.5,
            xanchor="center"
        ),
        margin=dict(t=70, b=60)
    )

    st.plotly_chart(fig_driver, use_container_width=True)
    st.plotly_chart(fig_hub, use_container_width=True)

    # ================= PDF GENERATION =================
    if st.button("📄 Generate Final PDF"):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="HeaderTitle",
            fontSize=18,
            textColor=colors.white,
            alignment=1
        )

        elements = []

        # ---------- HEADER ----------
        header = Table(
            [[Paragraph("FC Daily Charging Report", title_style)]],
            colWidths=[450],
            rowHeights=[40]
        )
        header.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#1f4e79")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        elements.append(header)
        elements.append(Spacer(1, 8))

        # ---------- KPI ----------
        kpi = Table(
            [[
                f"Date: {report_date}",
                f"Total Sessions: {total_sessions}",
                f"Total Energy: {total_energy} kWh"
            ]],
            colWidths=[150, 150, 150]
        )
        kpi.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
            ("FONT", (0,0), (-1,-1), "Helvetica-Bold"),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOX", (0,0), (-1,-1), 0.6, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 10),
        ]))
        elements.append(kpi)
        elements.append(Spacer(1, 16))

        # ---------- DASHBOARD ----------
        fig_driver.write_image("driver.png", width=1000, height=520, scale=2)
        fig_hub.write_image("hub.png", width=1000, height=520, scale=2)

        elements.append(Image("driver.png", width=500, height=260))
        elements.append(Spacer(1, 12))
        elements.append(Image("hub.png", width=500, height=260))

        elements.append(PageBreak())

        # ---------- SESSION TABLE ----------
        cell_style = ParagraphStyle(
            name="Cell",
            fontSize=7.2,
            leading=9,
            wordWrap="CJK"
        )
        header_cell_style = ParagraphStyle(
            name="HeaderCell",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=1
        )

        elements.append(Paragraph("Session Details", styles["Heading2"]))
        elements.append(Spacer(1, 8))

        headers = [
            "Hub", "Session ID", "Driver", "VIN",
            "kWh", "Duration", "Status",
            "SOC In", "End SOC", "Start", "End"
        ]

        table_data = [[Paragraph(h, header_cell_style) for h in headers]]

        for _, r in daily_df.iterrows():
            table_data.append([
                Paragraph(str(r.get("Hub Name","")), cell_style),
                Paragraph(str(r.get("Session ID","")), cell_style),
                Paragraph(str(r.get("Driver Name","")), cell_style),
                Paragraph(str(r.get("VIN NUMBER","")), cell_style),
                Paragraph(str(r.get("Usage (kWh)","")), cell_style),
                Paragraph(str(r.get("Duration","")), cell_style),
                Paragraph(str(r.get("Status","")), cell_style),
                Paragraph(str(r.get("SOC In (%)","")), cell_style),
                Paragraph(str(r.get("End SOC","")), cell_style),
                Paragraph(r["Start Time"].strftime("%d-%m %H:%M"), cell_style),
                Paragraph(r["End Time"].strftime("%d-%m %H:%M"), cell_style),
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[50, 50, 60, 85, 35, 45, 55, 45, 45, 60, 60]
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f4e79")),
            ("GRID", (0,0), (-1,-1), 0.35, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))

        elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        st.download_button(
            "⬇ Download Final PDF Report",
            buffer,
            file_name=f"FC_Daily_Charging_Report_{report_date}.pdf",
            mime="application/pdf"
        )
