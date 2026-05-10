import streamlit as st
import requests
import pandas as pd
import time
import re
import json
import base64
from datetime import date, datetime
import cloudscraper

# ------------------------------
# PAGE CONFIG
# ------------------------------
st.set_page_config(
    page_title="WealthoraPrime Panel",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="collapsed"
)

# ------------------------------
# CREDENTIALS
# ------------------------------
try:
    EMAIL = st.secrets["credentials"]["email"]
    PASSWORD = st.secrets["credentials"]["password"]
    BASE_URL = st.secrets["api"]["base_url"]
except Exception:
    # Fallback for local testing – NEVER commit real credentials
    EMAIL = "aryanrathod03097@gmail.com"
    PASSWORD = "bcgn2QhhJX$4cLp"
    BASE_URL = "https://x.mnitnetwork.com/mapi/v1"

# ------------------------------
# INITIALIZE CLOUDFLARE BYPASS
# ------------------------------
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

# ------------------------------
# SESSION STATE
# ------------------------------
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = ""
if 'token_expiry' not in st.session_state:
    st.session_state.token_expiry = 0
if 'cf_clearance' not in st.session_state:
    st.session_state.cf_clearance = ""
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'last_search_result' not in st.session_state:
    st.session_state.last_search_result = None

# ------------------------------
# HELPER: Cloudflare Clearance
# ------------------------------
def generate_cf_clearance():
    try:
        res = scraper.get("https://x.mnitnetwork.com")
        if 'cf_clearance' in scraper.cookies:
            st.session_state.cf_clearance = scraper.cookies['cf_clearance']
    except Exception as e:
        st.warning(f"CF bypass warning: {e}")

# ------------------------------
# LOGIN FUNCTION
# ------------------------------
def login():
    generate_cf_clearance()
    url = f"{BASE_URL}/mauth/login"
    payload = {"email": EMAIL, "password": PASSWORD}
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://x.mnitnetwork.com",
        "referer": "https://x.mnitnetwork.com/mauth/login",
        "user-agent": "Mozilla/5.0"
    }
    try:
        r = scraper.post(url, json=payload, headers=headers)
        data = r.json()
        if data.get('meta', {}).get('code') == 200:
            tk = data['data']['token']
            st.session_state.auth_token = tk
            st.session_state.user_info = data['data'].get('user', {})
            st.session_state.is_logged_in = True
            # decode JWT expiry
            try:
                payload_b64 = tk.split('.')[1]
                payload_b64 += '=' * (4 - len(payload_b64) % 4)
                decoded = json.loads(base64.b64decode(payload_b64))
                st.session_state.token_expiry = decoded.get('exp', 0)
            except Exception:
                st.session_state.token_expiry = time.time() + 43200
            return True
        else:
            st.error(f"Login failed: {data.get('message')}")
            return False
    except Exception as e:
        st.error(f"Login error: {e}")
        return False

def ensure_token():
    if not st.session_state.auth_token or time.time() > (st.session_state.token_expiry - 300):
        return login()
    return True

# ------------------------------
# API CALL WITH AUTO‑REFRESH
# ------------------------------
def api_call(endpoint, method="GET", json_data=None):
    if not ensure_token():
        return None
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "mauthtoken": st.session_state.auth_token,
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://x.mnitnetwork.com",
        "user-agent": "Mozilla/5.0"
    }
    try:
        if method == "POST":
            r = scraper.post(url, headers=headers, json=json_data)
        else:
            r = scraper.get(url, headers=headers)
        if r.status_code == 401:
            if login():
                return api_call(endpoint, method, json_data)
            return None
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None

# ------------------------------
# DATA HELPERS
# ------------------------------
def extract_otp(text):
    if not text:
        return ""
    # matches plain digits (4-8) or hyphenated codes like 354-367
    match = re.search(r'(\d{4,8}|\d{3,4}-\d{3,4})', str(text))
    return match.group(1) if match else ""

def get_range_id(number):
    if not number:
        return "Unknown"
    num = re.sub(r'\D', '', str(number))
    return num[:6] + "XXXX" if len(num) > 6 else num

def safe_df(data, col_map):
    if not data:
        return pd.DataFrame(columns=col_map.values())
    df = pd.DataFrame(data)
    cols = [k for k in col_map if k in df.columns]
    return df[cols].rename(columns=col_map)

# ------------------------------
# INITIAL LOGIN
# ------------------------------
if not st.session_state.is_logged_in:
    with st.spinner("Logging in..."):
        login()
    st.rerun()

# ------------------------------
# UI HEADER
# ------------------------------
st.title("💎 WealthoraPrime Panel")
col1, col2, col3 = st.columns([5, 3, 4])
with col1:
    st.markdown(f"**Logged in as:** {st.session_state.user_info.get('username', EMAIL)}")
with col2:
    exp = datetime.fromtimestamp(st.session_state.token_expiry) if st.session_state.token_expiry else "N/A"
    st.markdown(f"**Token expires:** {exp}")
with col3:
    if st.button("🔄 Force Refresh"):
        st.rerun()

st.markdown("---")

# ------------------------------
# SEARCH
# ------------------------------
st.subheader("🔍 Number Lookup")
c1, c2 = st.columns([7, 3])
with c1:
    search_val = st.text_input("Enter Range ID", placeholder="23762195xxxxxx")
with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Search", type="primary", use_container_width=True):
        if search_val:
            payload = {"range": search_val, "is_national": False, "remove_plus": False}
            res = api_call("/mdashboard/getnum/number", "POST", payload)
            if res and res.get('meta', {}).get('code') == 200:
                st.session_state.last_search_result = res['data']
                st.success("Number found!")
            else:
                st.error("Not found / error")
        else:
            st.warning("Enter a range ID")

st.markdown("---")

# ------------------------------
# DATA FETCH
# ------------------------------
console_data = api_call("/mdashboard/console/info")
nums_data = api_call(f"/mdashboard/getnum/info?date={date.today()}&page=1&search=&status=")

all_nums = nums_data.get('data', {}).get('numbers', []) if nums_data else []
pending = [n for n in all_nums if str(n.get('status', '')).lower() == 'pending']
success = [n for n in all_nums if str(n.get('status', '')).lower() == 'success']

# inject last search result
if st.session_state.last_search_result:
    if not any(n.get('number') == st.session_state.last_search_result.get('number') for n in pending):
        pending.append(st.session_state.last_search_result)

# ------------------------------
# PENDING TABLE
# ------------------------------
st.subheader("🟡 Pending Allocation")
p_map = {"number": "📱 Number", "country": "🌍 Country", "operator": "📡 Operator", "status": "📌 Status", "last_activity": "⏰ Activity"}
st.dataframe(safe_df(pending, p_map), use_container_width=True)

# ------------------------------
# SUCCESS TABLE WITH OTP
# ------------------------------
st.subheader("🟢 Success & OTP")
if success:
    s_list = []
    for n in success:
        s_list.append({
            "📱 Number": n.get('number'),
            "🌍 Country": n.get('country'),
            "📡 Operator": n.get('operator'),
            "🔐 OTP": extract_otp(n.get('message')),
            "💬 Full Message": n.get('message', '')[:80],
            "⏰ Time": n.get('last_activity')
        })
    st.dataframe(pd.DataFrame(s_list), use_container_width=True)
else:
    st.info("No success numbers")

# ------------------------------
# ANALYTICS FROM SUCCESS NUMBERS
# ------------------------------
st.subheader("📊 Traffic Analytics")

# Top 10 Ranges
ranges_data = []
for n in success:
    ranges_data.append({
        "Range ID": get_range_id(n.get('number')),
        "Country": n.get('country', 'Unknown'),
        "Hits": 1,
        "Last OTP": extract_otp(n.get('message'))
    })
dr = pd.DataFrame(ranges_data)
top_ranges = pd.DataFrame()
if not dr.empty:
    top_ranges = dr.groupby(["Range ID", "Country"]).agg(
        Total_Success=('Hits','sum'),
        Sample_OTP=('Last OTP','last')
    ).reset_index().nlargest(10, 'Total_Success')

# Top Applications (success‑based)
apps_data = []
for n in success:
    app = n.get('app_name')
    if not app:
        msg = n.get('message','')
        app = msg.split()[0] if msg else "Unknown"
    apps_data.append({
        "App Name": app,
        "Range ID": get_range_id(n.get('number')),
        "Hits": 1,
        "Sample SMS": n.get('message','')[:50]
    })
da = pd.DataFrame(apps_data)
top_apps = pd.DataFrame()
if not da.empty:
    top_apps = da.groupby(["App Name", "Range ID"]).agg(
        Total_Hits=('Hits','sum'),
        Last_SMS=('Sample SMS','last')
    ).reset_index().nlargest(10, 'Total_Hits')

colA, colB = st.columns(2)
with colA:
    st.markdown("**🏆 Top 10 High Traffic Ranges**")
    st.dataframe(top_ranges if not top_ranges.empty else pd.DataFrame({"Info": ["No data"]}), use_container_width=True)
with colB:
    st.markdown("**📱 Top 10 Applications by Traffic**")
    # remove Application column as requested
    if not top_apps.empty:
        top_apps_disp = top_apps.drop(columns=["App Name"], errors='ignore')
        st.dataframe(top_apps_disp, use_container_width=True)
    else:
        st.dataframe(pd.DataFrame({"Info": ["No data"]}), use_container_width=True)

# ------------------------------
# CONSOLE SERVER TRAFFIC (NEW)
# ------------------------------
st.subheader("🖥️ Console Server High Traffic")
logs = console_data.get('data', {}).get('logs', []) if console_data else []

# Top Server Ranges
srv_ranges = []
for log in logs:
    srv_ranges.append({
        "Server Range": get_range_id(log.get('number')) or log.get('range', 'Unknown'),
        "Country": log.get('country', 'Unknown'),
        "Requests": 1
    })
df_sr = pd.DataFrame(srv_ranges)
top_srv_ranges = pd.DataFrame()
if not df_sr.empty:
    top_srv_ranges = df_sr.groupby(["Server Range", "Country"]).agg(
        Total_Server_Requests=('Requests','sum')
    ).reset_index().nlargest(10, 'Total_Server_Requests')

# Top Server Apps
srv_apps = []
for log in logs:
    srv_apps.append({
        "Application": log.get('app_name', 'Unknown').upper(),
        "Range": get_range_id(log.get('number')) or log.get('range', 'Unknown'),
        "Sessions": 1
    })
df_sa = pd.DataFrame(srv_apps)
top_srv_apps = pd.DataFrame()
if not df_sa.empty:
    top_srv_apps = df_sa.groupby(["Application", "Range"]).agg(
        Total_Sessions=('Sessions','sum')
    ).reset_index().nlargest(10, 'Total_Sessions')

colC, colD = st.columns(2)
with colC:
    st.markdown("**🔥 Top 10 Server Ranges (Console)**")
    st.dataframe(top_srv_ranges if not top_srv_ranges.empty else pd.DataFrame({"Info": ["No logs"]}), use_container_width=True)
with colD:
    st.markdown("**📲 Top Apps (Console)**")
    st.dataframe(top_srv_apps if not top_srv_apps.empty else pd.DataFrame({"Info": ["No logs"]}), use_container_width=True)

# Recent console logs
st.markdown("**📋 Recent Console Logs**")
c_map = {"time":"⏰ Time","app_name":"📱 App","number":"☎️ Number","range":"📍 Range","country":"🌍 Country","sms":"💬 SMS"}
st.dataframe(safe_df(logs[:20], c_map), use_container_width=True)

# ------------------------------
# FOOTER
# ------------------------------
st.markdown("---")
st.markdown(f"""
<div style='text-align:center; color:#888; font-size:14px;'>
    <strong>© {date.today().year} WealthoraPrime Panel</strong><br>
    Developed by <strong>Aryan Rathod 🇮🇳</strong><br>
    Channel: <a href='https://t.me/filesbykaiiddo'>filesbykaiiddo.t.me</a>
</div>
""", unsafe_allow_html=True)

# ---------- 2‑SECOND AUTO REFRESH ----------
time.sleep(2)
st.rerun()
