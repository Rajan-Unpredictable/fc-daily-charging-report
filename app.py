import streamlit as st
import pandas as pd
from io import BytesIO
import plotly.express as px
import matplotlib.pyplot as plt
import numpy as np

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

    # ================= DRIVER DATA =================
    driver_usage = (
        daily_df.groupby("Driver Name", as_index=False)["Usage (kWh)"]
        .sum()
        .sort_values("Usage (kWh)", ascending=False)
    )

    top_drivers = driver_usage.head(8)
    other_val = driver_usage.iloc[8:]["Usage (kWh)"].sum()

    if other_val > 0:
        top_drivers = pd.concat([
            top_drivers,
            pd.DataFrame([{"Driver Name": "Others", "Usage (kWh)": other_val}])
        ])

    # ================= HUB DATA =================
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

    # ================= DASHBOARD (BROWSER – Plotly) =================
    fig_driver = px.bar(
        top_drivers,
        x="Usage (kWh)",
        y="Driver Name",
        orientation="h",
        text=top_drivers["Usage (kWh)"].round(2),
        title="Driver-wise Energy Usage (kWh)",
        color_discrete_sequence=["#2563eb"]
    )
    fig_driver.update_traces(textposition="outside")
    fig_driver.update_layout(margin=dict(l=160, r=60))

    fig_hub = px.pie(
        top_hubs,
        names="Hub Name",
        values="Usage (kWh)",
        title="Hub-wise Energy Distribution"
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
            fontSize=16,
            textColor=colors.white,
            alignment=1,
            leading=18
        )

        elements = []

        # ---------- HEADER ----------
        header = Table(
            [[Paragraph("FC Daily Charging Report", title_style)]],
            colWidths=[450],
            rowHeights=[45]
        )
        header.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#1f4e79")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))
        elements.append(header)
        elements.append(Spacer(1, 10))

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
            ("BACKGROUND",(0,0),(-1,-1),colors.whitesmoke),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("FONT",(0,0),(-1,-1),"Helvetica-Bold"),
        ]))
        elements.append(kpi)
        elements.append(Spacer(1, 18))

        # ================= DRIVER BAR (PDF) =================
        plt.figure(figsize=(10, 5.5))
        bars = plt.barh(
            top_drivers["Driver Name"],
            top_drivers["Usage (kWh)"],
            color="#2563eb"
        )

        max_val = top_drivers["Usage (kWh)"].max()
        plt.xlim(0, max_val * 1.25)

        for bar in bars:
            w = bar.get_width()
            plt.text(
                w + max_val * 0.02,
                bar.get_y() + bar.get_height()/2,
                f"{w:.2f}",
                va="center",
                fontsize=10
            )

        plt.xlabel("Energy (kWh)")
        plt.title("Driver-wise Energy Usage (kWh)")
        plt.tight_layout()
        plt.savefig("driver_pdf.png")
        plt.close()

        # ================= HUB PIE (PDF – FIXED) =================
        plt.figure(figsize=(6.5, 5))
        plt.pie(
            top_hubs["Usage (kWh)"],
            labels=top_hubs["Hub Name"],
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.75,
            labeldistance=1.08,
            textprops={"fontsize": 10}
        )
        plt.title("Hub-wise Energy Distribution", fontsize=13)
        plt.tight_layout()
        plt.savefig("hub_pdf.png")
        plt.close()

        elements.append(Image("driver_pdf.png", width=480, height=250))
        elements.append(Spacer(1, 18))
        elements.append(Image("hub_pdf.png", width=420, height=280))

        elements.append(PageBreak())

        # ---------- SESSION TABLE ----------
        cell_style = ParagraphStyle(name="Cell", fontSize=7.2, leading=9)
        header_style = ParagraphStyle(name="HeaderCell", fontSize=8, textColor=colors.white)

        headers = [
            "Hub", "Session ID", "Driver", "VIN",
            "kWh", "Duration", "Status",
            "SOC In", "End SOC", "Start", "End"
        ]

        table_data = [[Paragraph(h, header_style) for h in headers]]

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
            colWidths=[50,50,60,85,35,45,55,45,45,60,60]
        )
        table.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1f4e79")),
            ("GRID",(0,0),(-1,-1),0.3,colors.grey),
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
