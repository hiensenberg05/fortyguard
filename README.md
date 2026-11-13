# FortyGuard Temperature Studio & MCP Agent 🌡️

A modern geospatial microclimate intelligence platform and autonomous AI agent powered by **FortyGuard's Temperature API®**, **Model Context Protocol (MCP)**, and **Groq / Grok LLMs**.

Built with **Streamlit**, **Folium**, and **Plotly**.

---

## 🌟 Key Features

* **🤖 Autonomous Thermal AI Agent:** Conversational agent powered by Groq LPUs (`qwen/qwen3.8-27b`) or xAI Grok with native tool-calling through the remote FortyGuard MCP gateway.
* **🗺️ Temperature-Aware Routing Studio:** Real-time multi-criteria route optimization comparing **Fastest**, **Balanced**, and **Coolest** driving corridors with thermal exposure metrics ($^\circ\text{C}\cdot\text{min}$) and interactive Folium maps.
* **📊 Environmental Point Intelligence:** Point-level microclimate analysis providing heat index, apparent temperature, wet-bulb temperature, AQI breakdown ($\text{PM2.5}, \text{PM10}, \text{NO}_2, \text{SO}_2, \text{O}_3, \text{CO}$), and solar irradiance components ($\text{GHI}, \text{DNI}, \text{DHI}$).
* **🧪 Diagnostic & Benchmark Suite:** Automated 10-point test runner validating MCP protocol compliance, latency profiling, geographic bounds, and credit consumption.

---

## 🚀 Quickstart & Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/hiensenberg05/fortyguard.git
cd fortyguard
```

### 2. Set up virtual environment
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```env
FORTY_GUARD_API_KEY=your_fortyguard_api_key_here
GROQ_API_KEY=your_groq_api_key_here
# Optional:
GROK_API_KEY=your_xai_grok_api_key_here
```

### 5. Run the application
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🧪 Running the Automated Test Suite

```bash
# Run unit tests
python test_endpoints.py

# Run comprehensive benchmark suite across all climate zones
python test_suite.py
```

---

## 📄 Evaluation Report

For our detailed empirical analysis, benchmark matrices, and recommendations, see:
* [FORTYGUARD_TEST_REPORT.md](FORTYGUARD_TEST_REPORT.md)
* [brief.md](brief.md)
