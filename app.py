import os
import json
import time
from datetime import datetime
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from config import (
    FORTY_GUARD_API_KEY,
    GROQ_API_KEY,
    GROK_API_KEY,
    TOOL_CREDIT_COSTS,
    is_within_us_bounds,
)
from fortyguard_mcp import FortyGuardMCPClient
from llm_agent import ThermalAgent
from rest_client import FortyGuardRESTClient
from test_suite import run_test_suite

# Set page config
st.set_page_config(
    page_title="FortyGuard Thermal Studio",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        color: #f8fafc;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .badge-cool {
        background-color: #059669;
        color: white;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-fast {
        background-color: #0284c7;
        color: white;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-balanced {
        background-color: #7c3aed;
        color: white;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = []
if "last_routes" not in st.session_state:
    st.session_state.last_routes = None
if "last_env_params" not in st.session_state:
    st.session_state.last_env_params = None
if "test_results" not in st.session_state:
    st.session_state.test_results = None
if "credit_balance" not in st.session_state:
    st.session_state.credit_balance = 993600

# Clients
mcp_client = FortyGuardMCPClient()
rest_client = FortyGuardRESTClient()

# Sidebar
with st.sidebar:
    st.title("🌡️ FortyGuard Studio")
    st.caption("Microclimate & Thermal Intelligence")

    st.subheader("💳 Credit Telemetry")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.metric("Credits Left", f"{st.session_state.credit_balance:,}")
    with col_c2:
        if st.button("🔄 Refresh", use_container_width=True):
            bal_res = mcp_client.get_credit_balance()
            if bal_res.get("ok"):
                st.session_state.credit_balance = bal_res.get("available_credits", 0)
                st.rerun()

    st.divider()

    st.subheader("🧠 LLM Configuration")
    provider = st.selectbox("LLM Provider", ["Groq (LPU)", "Grok (xAI)"], index=0)
    provider_key = "groq" if "Groq" in provider else "grok"

    if provider_key == "groq":
        model_choice = st.selectbox("Groq Model", ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"])
    else:
        model_choice = st.selectbox("Grok Model", ["grok-2-latest", "grok-beta"])

    st.divider()
    st.info("⚠️ **Coverage Boundary**: FortyGuard currently supports contiguous United States regions only. Coordinate checks are enforced.")

# Main Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🤖 Thermal AI Agent",
    "🗺️ Routing Studio",
    "📊 Environmental Parameters",
    "🧪 Diagnostic Test Suite",
])

# -------------------------------------------------------------
# TAB 1: THERMAL AI AGENT
# -------------------------------------------------------------
with tab1:
    st.header("Thermal Intelligence AI Agent")
    st.markdown("Powered by **Groq / Grok** tool calling through the **FortyGuard MCP Gateway**.")

    # Quick Prompts
    st.write("**Quick Inquiries:**")
    qp_cols = st.columns(4)
    preset_prompt = None
    if qp_cols[0].button("📍 Coolest Route (Phoenix)", use_container_width=True):
        preset_prompt = "Find me the coolest temperature route from Downtown Phoenix (33.4484, -112.0740) to Biltmore (33.5092, -112.0362) at 2024-07-15T14:00:00Z."
    if qp_cols[1].button("☀️ Heat Stress (Austin)", use_container_width=True):
        preset_prompt = "What is the heat index, wet-bulb temperature, and solar irradiance in Austin, TX (30.2672, -97.7431) when ambient temperature is 35°C on 2024-07-15?"
    if qp_cols[2].button("💳 Check API Credits", use_container_width=True):
        preset_prompt = "How many Enterprise API credits do I have left on FortyGuard?"
    if qp_cols[3].button("🌴 Miami Microclimate", use_container_width=True):
        preset_prompt = "Check the apparent temperature and AQI for Miami (25.7617, -80.1918) at 32°C on 2024-07-15."

    # Render Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "tool_traces" in msg and msg["tool_traces"]:
                with st.expander("🛠️ Tool Invocations & Trace", expanded=False):
                    for trace in msg["tool_traces"]:
                        st.markdown(f"**Tool:** `{trace.get('name')}`")
                        st.json(trace.get("arguments", {}))

    # User Input
    user_input = st.chat_input("Ask about routes, urban heat islands, or point climate metrics...") or preset_prompt

    if user_input:
        # Add user msg
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Agent Execution
        with st.chat_message("assistant"):
            with st.spinner("Agent analyzing and executing MCP tools..."):
                try:
                    agent = ThermalAgent(provider=provider_key, model=model_choice, mcp_client=mcp_client)
                    agent_res = agent.chat(user_input, chat_history=st.session_state.agent_messages)
                    response_text = agent_res.get("response", "")
                    tool_traces = agent_res.get("tool_calls", [])
                    artifacts = agent_res.get("artifacts", {})

                    st.markdown(response_text)

                    if tool_traces:
                        with st.expander("🛠️ Tool Invocations & Trace", expanded=True):
                            for trace in tool_traces:
                                st.markdown(f"**Tool:** `{trace.get('name')}`")
                                st.json(trace.get("arguments", {}))

                    # If routes were returned, render preview map
                    if "routes" in artifacts and artifacts["routes"]:
                        st.session_state.last_routes = artifacts["routes"]
                        st.success("✅ Multi-criteria routes generated. Switch to the Routing Studio tab for full visualization!")

                    # Update history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response_text,
                        "tool_traces": tool_traces,
                    })
                    st.session_state.agent_messages.append({"role": "user", "content": user_input})
                    st.session_state.agent_messages.append({"role": "assistant", "content": response_text})

                except Exception as e:
                    err_msg = f"Agent encountered an error: {e}"
                    st.error(err_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": err_msg})

# -------------------------------------------------------------
# TAB 2: ROUTING STUDIO
# -------------------------------------------------------------
with tab2:
    st.header("Temperature-Aware Routing Studio")
    st.markdown("Compare routes optimized for **Speed** vs. **Reduced Thermal Stress & Urban Heat Island Avoidance**.")

    col_r1, col_r2 = st.columns([1, 2])

    with col_r1:
        st.subheader("Route Configuration")
        city_preset = st.selectbox("Select Preset Corridor", [
            "Phoenix, AZ: Downtown → Biltmore",
            "Las Vegas, NV: Strip → Summerlin",
            "Austin, TX: Downtown → Airport",
            "Custom Coordinates",
        ])

        if "Phoenix" in city_preset:
            orig_lat, orig_lon = 33.4484, -112.0740
            dest_lat, dest_lon = 33.5092, -112.0362
        elif "Las Vegas" in city_preset:
            orig_lat, orig_lon = 36.1147, -115.1728
            dest_lat, dest_lon = 36.1915, -115.2974
        elif "Austin" in city_preset:
            orig_lat, orig_lon = 30.2672, -97.7431
            dest_lat, dest_lon = 30.1975, -97.6664
        else:
            orig_lat, orig_lon = 33.4484, -112.0740
            dest_lat, dest_lon = 33.5092, -112.0362

        o_lat = st.number_input("Origin Latitude", value=orig_lat, format="%.5f")
        o_lon = st.number_input("Origin Longitude", value=orig_lon, format="%.5f")
        d_lat = st.number_input("Destination Latitude", value=dest_lat, format="%.5f")
        d_lon = st.number_input("Destination Longitude", value=dest_lon, format="%.5f")
        dep_time = st.text_input("Departure Time (ISO-8601)", value="2024-07-15T14:00:00Z")

        run_route_btn = st.button("🚀 Calculate Temperature Routes", type="primary", use_container_width=True)

        if run_route_btn:
            with st.spinner("Submitting routing job and polling FortyGuard MCP..."):
                res = mcp_client.get_temperature_routing(
                    origin={"lat": o_lat, "lon": o_lon},
                    destination={"lat": d_lat, "lon": d_lon},
                    departure_time=dep_time,
                )
                if res.get("ok"):
                    st.session_state.last_routes = res.get("routes", [])
                    st.success(f"Generated {len(st.session_state.last_routes)} routes in {res.get('total_poll_time_sec')}s!")
                else:
                    st.error(f"Routing failed: {res.get('error')}")

    with col_r2:
        if st.session_state.last_routes:
            routes = st.session_state.last_routes
            st.subheader(f"Discovered Routes ({len(routes)})")

            # Route Metrics Cards
            cols = st.columns(len(routes))
            color_map = {
                "Fastest": "#0284c7",
                "Coolest": "#059669",
                "Balanced": "#7c3aed",
                "Option 4": "#ea580c",
            }

            for idx, r in enumerate(routes):
                p = r.get("properties", {})
                label = p.get("label", f"Route {idx+1}")
                therm = p.get("thermal", {})
                badge_class = f"badge-{label.lower()}" if label.lower() in ["fastest", "coolest", "balanced"] else "badge-fast"

                with cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <span class="{badge_class}">{label}</span>
                        <h3 style="margin: 8px 0 4px 0;">{p.get('duration_min', 0):.1f} min</h3>
                        <p style="color: #94a3b8; font-size: 0.85rem; margin: 0;">Distance: {p.get('distance_km', 0):.2f} km</p>
                        <p style="color: #f59e0b; font-size: 0.85rem; margin: 0;">Mean: {therm.get('mean_c', 0):.2f} °C</p>
                        <p style="color: #ef4444; font-size: 0.85rem; margin: 0;">Peak: {therm.get('peak_c', 0):.2f} °C</p>
                        <p style="color: #cbd5e1; font-size: 0.8rem; margin: 0;">Heat Exposure: {therm.get('degree_minutes_above_threshold', 0):.1f} °C·min</p>
                    </div>
                    """, unsafe_allow_html=True)

            st.write("")

            # Folium Map
            center_lat = (o_lat + d_lat) / 2
            center_lon = (o_lon + d_lon) / 2
            m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="CartoDB dark_matter")

            # Add Origin & Destination Markers
            folium.Marker([o_lat, o_lon], tooltip="Origin", icon=folium.Icon(color="green", icon="play")).add_to(m)
            folium.Marker([d_lat, d_lon], tooltip="Destination", icon=folium.Icon(color="red", icon="flag")).add_to(m)

            for idx, r in enumerate(routes):
                p = r.get("properties", {})
                label = p.get("label", f"Route {idx+1}")
                coords = r.get("geometry", {}).get("coordinates", [])
                # GeoJSON coordinates are [lon, lat], folium expects [lat, lon]
                lat_lngs = [[pt[1], pt[0]] for pt in coords]
                c = color_map.get(label, "#94a3b8")

                folium.PolyLine(
                    locations=lat_lngs,
                    color=c,
                    weight=5,
                    opacity=0.85,
                    tooltip=f"{label} - {p.get('duration_min', 0):.1f} min | Mean: {p.get('thermal', {}).get('mean_c', 0):.2f}°C",
                ).add_to(m)

            st_folium(m, height=450, use_container_width=True)

            # Thermal Profile Comparison Plot
            st.subheader("📈 Thermal Stress & Duration Comparison")
            df_routes = []
            for r in routes:
                p = r.get("properties", {})
                therm = p.get("thermal", {})
                df_routes.append({
                    "Route": p.get("label"),
                    "Duration (min)": p.get("duration_min"),
                    "Mean Temp (°C)": therm.get("mean_c"),
                    "Peak Temp (°C)": therm.get("peak_c"),
                    "Degree-Minutes Above Threshold": therm.get("degree_minutes_above_threshold"),
                })
            df = pd.DataFrame(df_routes)

            fig = px.bar(
                df,
                x="Route",
                y="Degree-Minutes Above Threshold",
                color="Route",
                color_discrete_map=color_map,
                text="Mean Temp (°C)",
                title="Cumulative Heat Exposure Above 32°C (Degree-Minutes)",
            )
            fig.update_layout(template="plotly_dark", height=320)
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("👈 Enter origin & destination coordinates and click 'Calculate Temperature Routes' to begin.")

# -------------------------------------------------------------
# TAB 3: ENVIRONMENTAL PARAMETERS
# -------------------------------------------------------------
with tab3:
    st.header("Point-Level Environmental Intelligence")
    st.markdown("Query deep microclimate parameters: **apparent temperature, wet-bulb temp, AQI, and solar irradiance splits**.")

    col_e1, col_e2 = st.columns([1, 2])

    with col_e1:
        st.subheader("Location & Parameters")
        env_city = st.selectbox("Preset City", ["Phoenix, AZ", "Austin, TX", "Miami, FL", "Las Vegas, NV", "Custom"])
        if env_city == "Phoenix, AZ":
            plat, plon, ptemp = 33.4484, -112.0740, 38.0
        elif env_city == "Austin, TX":
            plat, plon, ptemp = 30.2672, -97.7431, 34.0
        elif env_city == "Miami, FL":
            plat, plon, ptemp = 25.7617, -80.1918, 31.0
        elif env_city == "Las Vegas, NV":
            plat, plon, ptemp = 36.1699, -115.1398, 40.0
        else:
            plat, plon, ptemp = 33.4484, -112.0740, 35.0

        p_lat = st.number_input("Latitude", value=plat, format="%.5f", key="e_lat")
        p_lon = st.number_input("Longitude", value=plon, format="%.5f", key="e_lon")
        p_temp = st.number_input("Ambient Temperature (°C)", value=ptemp, format="%.1f", key="e_temp")
        p_date = st.text_input("Date (YYYY-MM-DD)", value="2024-07-15", key="e_date")
        p_time = st.text_input("Local Wall Time", value="14:00", key="e_time")

        if st.button("🔍 Analyze Environmental Conditions", type="primary", use_container_width=True):
            with st.spinner("Fetching point environmental intelligence..."):
                res = mcp_client.get_env_params(
                    latitude=p_lat,
                    longitude=p_lon,
                    temperature=p_temp,
                    date_str=p_date,
                    time_str=p_time,
                )
                if res.get("ok"):
                    st.session_state.last_env_params = res.get("data", {})
                    st.success("Data successfully retrieved!")
                else:
                    st.error(f"Analysis failed: {res.get('error')}")

    with col_e2:
        if st.session_state.last_env_params:
            data = st.session_state.last_env_params
            # Extract first location if nested
            loc = {}
            if isinstance(data, dict):
                locations = data.get("locations", [])
                if locations:
                    loc = locations[0]
                else:
                    loc = data

            params = loc.get("parameters", {})
            solar = loc.get("solar_irradiance", {})

            st.subheader("Microclimate Readings")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Heat Index", f"{params.get('heat_index_celsius', [0])[0]:.1f} °C")
            c2.metric("Apparent Temp", f"{params.get('apparent_temperature_celsius', [0])[0]:.1f} °C")
            c3.metric("Wet Bulb Temp", f"{params.get('wet_bulb_temperature_celsius', [0])[0]:.1f} °C")
            c4.metric("Relative Humidity", f"{params.get('relative_humidity_percent', [0])[0]:.1f} %")

            st.divider()

            # Air Quality
            st.subheader("Air Quality Breakdown")
            aq_cols = st.columns(5)
            aq_cols[0].metric("AQI (Overall)", f"{params.get('air_quality:idx', [0])[0]:.1f}")
            aq_cols[1].metric("PM2.5", f"{params.get('air_quality_pm2p5:idx', [0])[0]:.1f}")
            aq_cols[2].metric("PM10", f"{params.get('air_quality_pm10:idx', [0])[0]:.1f}")
            aq_cols[3].metric("NO₂", f"{params.get('air_quality_no2:idx', [0])[0]:.1f}")
            aq_cols[4].metric("O₃ (Ozone)", f"{params.get('air_quality_o3:idx', [0])[0]:.1f}")

            st.divider()

            # Solar Irradiance
            st.subheader("Solar Irradiance Profile")
            s1, s2, s3 = st.columns(3)
            s1.metric("GHI (Global Horizontal)", f"{solar.get('ghi_wm2', [0])[0] if isinstance(solar.get('ghi_wm2'), list) else 0} W/m²")
            s2.metric("DNI (Direct Normal)", f"{solar.get('dni_wm2', [0])[0] if isinstance(solar.get('dni_wm2'), list) else 0} W/m²")
            s3.metric("DHI (Diffuse Horizontal)", f"{solar.get('dhi_wm2', [0])[0] if isinstance(solar.get('dhi_wm2'), list) else 0} W/m²")

        else:
            st.info("👈 Enter coordinate parameters and click 'Analyze Environmental Conditions'.")

# -------------------------------------------------------------
# TAB 4: DIAGNOSTIC TEST SUITE & FEEDBACK FORM EXPORT
# -------------------------------------------------------------
with tab4:
    st.header("FortyGuard API & MCP Diagnostic Suite")
    st.markdown("Run automated benchmark tests across authentication, endpoints, latency, and boundary conditions to generate evaluation data for your feedback form.")

    col_d1, col_d2 = st.columns([1, 1])
    with col_d1:
        if st.button("🧪 Run Comprehensive Test Suite", type="primary", use_container_width=True):
            with st.spinner("Executing full automated benchmark suite across all endpoints..."):
                results = run_test_suite()
                st.session_state.test_results = results
                st.success("Test suite execution complete!")

    if st.session_state.test_results:
        res = st.session_state.test_results
        summary = res.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        avg_lat = round(summary.get("total_latency_ms", 0) / max(total, 1), 1)

        st.subheader("Execution Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tests", total)
        m2.metric("Passed", f"{passed} ({round((passed/max(total, 1))*100, 1)}%)")
        m3.metric("Failed", failed)
        m4.metric("Avg Latency", f"{avg_lat} ms")

        # Table of tests
        st.subheader("Test Execution Details")
        test_rows = []
        for t in res.get("tests", []):
            test_rows.append({
                "Test Name": t.get("name"),
                "Status": "✅ PASS" if t.get("passed") else "❌ FAIL",
                "Latency (ms)": t.get("latency_ms"),
                "Observations / Notes": t.get("notes"),
            })
        st.dataframe(pd.DataFrame(test_rows), use_container_width=True)

        st.subheader("📥 Export for Feedback Form")
        col_down1, col_down2 = st.columns(2)

        if os.path.exists("FORTYGUARD_TEST_REPORT.md"):
            with open("FORTYGUARD_TEST_REPORT.md", "r", encoding="utf-8") as f:
                report_md = f.read()
            col_down1.download_button(
                label="📄 Download Markdown Report (FORTYGUARD_TEST_REPORT.md)",
                data=report_md,
                file_name="FORTYGUARD_TEST_REPORT.md",
                mime="text/markdown",
                use_container_width=True,
            )

        if os.path.exists("fortyguard_benchmark_results.json"):
            with open("fortyguard_benchmark_results.json", "r", encoding="utf-8") as f:
                report_json = f.read()
            col_down2.download_button(
                label="📊 Download Raw Benchmark JSON",
                data=report_json,
                file_name="fortyguard_benchmark_results.json",
                mime="application/json",
                use_container_width=True,
            )
