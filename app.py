import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import hashlib
from io import BytesIO

# --- 1. PAGE CONFIG & SCROLL FIX ---
st.set_page_config(page_title="UNAM JEDS Dashboard", layout="wide", page_icon="🏫")

st.markdown("""
    <style>
    .main .block-container { overflow-y: auto; height: auto; padding-top: 2rem; }
    html, body { overflow: auto; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #003366; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION & HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(sheet_name):
    # ttl=0 ensures we always pull live data for real-time analytics
    return conn.read(worksheet=sheet_name, ttl=0)

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

# --- 3. CONSTANTS ---
TITLES = ["Mr.", "Ms.", "Mrs.", "Dr.", "Prof.", "Eng."]
DEPARTMENTS = ["Electrical and Computer Engineering", "Mechanical and Metalurgical Engineering", "Civil and Mining Engineering", "Management & Administration"]
STATUS_OPTIONS = ["Draft", "Under Review", "Accepted", "Pending APC", "Published"]
ARTICLE_TYPES = ["Journal Article", "Conference Paper", "Book Chapter", "Technical Report"]

# --- 4. SESSION STATE (Persistence) ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None, "dept": None, "title": None})

# --- 5. AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("UNAM School of Engineering")
    auth_tabs = st.tabs(["Login", "Staff Registration"])
    
    with auth_tabs[0]:
        with st.form("login_form"):
            sid = st.text_input("Staff ID (e.g., 202246)")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users = load_data("staff_registry")
                user_row = users[users['staff_id'].astype(str).str.strip() == str(sid).strip()]
                if not user_row.empty and user_row.iloc[0]['password'] == hash_password(pwd):
                    st.session_state.update({
                        "logged_in": True, "user": str(sid).strip(), "name": user_row.iloc[0]['full_name'],
                        "role": user_row.iloc[0]['role'], "dept": user_row.iloc[0].get('department', 'N/A'),
                        "title": user_row.iloc[0].get('title', '')
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    
    with auth_tabs[1]:
        with st.form("reg_form"):
            c1, c2 = st.columns([1, 3])
            r_title, r_name = c1.selectbox("Title", TITLES), c2.text_input("Full Name (Surname First)")
            r_id = st.text_input("Staff ID")
            r_dept = st.selectbox("Department", DEPARTMENTS)
            r_pwd = st.text_input("Set Password", type="password")
            r_key = st.text_input("Security Key", type="password")
            if st.form_submit_button("Register"):
                role = "Academic" if r_key == "JEDSACA2026" else "Maintenance" if r_key == "JEDSSUP2026" else "Coordinator" if r_key == "JEDSCOR2026" else "Director" if r_key == "JEDSDir2026" else None
                if role:
                    users = load_data("staff_registry")
                    new_u = pd.DataFrame([{"staff_id": r_id, "title": r_title, "full_name": r_name, "role": role, "password": hash_password(r_pwd), "department": r_dept}])
                    conn.update(worksheet="staff_registry", data=pd.concat([users, new_u], ignore_index=True))
                    st.success(f"Registered as {role}!")
                else: st.error("Invalid Key.")
    st.stop()

# --- 6. SIDEBAR ---
st.sidebar.write(f"**Welcome, {st.session_state.title} {st.session_state.name}**")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- 7. DIRECTOR & COORDINATOR MODULE ---
if st.session_state.role in ["Director", "Coordinator"]:
    st.title(f"📊 {st.session_state.role} Dashboard")
    
    if st.session_state.role == "Director":
        tabs = st.tabs(["Research Analytics", "Maintenance Audit"])
        t_res, t_maint = tabs[0], tabs[1]
    else:
        t_res, t_maint = st.tabs(["Research Analytics"])[0], None

    with t_res:
        res_df = load_data("research_status")
        if not res_df.empty:
            # CLEANING: Sort by newest and drop duplicate titles to get ACTUAL status
            res_df['timestamp'] = pd.to_datetime(res_df['timestamp'], errors='coerce')
            unique_res = res_df.sort_values('timestamp', ascending=False).drop_duplicates('paper_title')
            
            # METRICS
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("✅ Published", len(unique_res[unique_res['status'] == "Published"]))
            c2.metric("🎉 Accepted", len(unique_res[unique_res['status'] == "Accepted"]))
            c3.metric("🔍 Under Review", len(unique_res[unique_res['status'] == "Under Review"]))
            c4.metric("💳 Pending APC", len(unique_res[unique_res['status'] == "Pending APC"]))
            c5.metric("📚 Unique Works", len(unique_res))
            
            # APC APPROVAL PANEL (Director Only)
            if st.session_state.role == "Director":
                pending = res_df[(res_df['status'] == "Pending APC") & (res_df['director_approval'] != "Approved")].drop_duplicates('paper_title')
                if not pending.empty:
                    st.divider()
                    st.subheader("💳 APC Approval Panel")
                    p_opt = pending.apply(lambda x: f"{x['paper_title']} | {x['full_name']} (N$ {x['apc_amount']})", axis=1).tolist()
                    sel = st.selectbox("Select Paper", p_opt)
                    if st.button("Approve APC Funding", type="primary"):
                        title_only = sel.split(" | ")[0]
                        res_df.loc[res_df['paper_title'] == title_only, ['director_approval', 'status']] = ["Approved", "Accepted"]
                        conn.update(worksheet="research_status", data=res_df)
                        st.cache_data.clear()
                        st.rerun()
            
            st.divider()
            st.subheader("Research Log")
            st.dataframe(res_df, use_container_width=True)
        else: st.info("No research data found.")

    if t_maint:
        with t_maint:
            st.subheader("Maintenance Oversight")
            m_df = load_data("maintenance_tickets")
            st.dataframe(m_df, use_container_width=True)
            st.download_button("Export Audit", data=to_excel(m_df), file_name="Maint_Audit.xlsx")

# --- 8. ACADEMIC STAFF MODULE ---
elif st.session_state.role == "Academic":
    st.title("📖 Academic Staff Portal")
    tab_reg, tab_fault = st.tabs(["Research Registry", "Maintenance Faults"])
    
    with tab_reg:
        with st.form("res_form"):
            p_title = st.text_input("Paper Title")
            p_status = st.selectbox("Status", STATUS_OPTIONS)
            p_apc = st.number_input("APC Amount (N$)", min_value=0)
            if st.form_submit_button("Submit Record"):
                old = load_data("research_status")
                new_r = pd.DataFrame([{"staff_id": st.session_state.user, "full_name": st.session_state.name, "department": st.session_state.dept, "paper_title": p_title, "status": p_status, "apc_amount": p_apc, "director_approval": "Pending" if p_status=="Pending APC" else "N/A", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}])
                conn.update(worksheet="research_status", data=pd.concat([old, new_r], ignore_index=True))
                st.cache_data.clear()
                st.rerun()
        
        st.divider()
        st.subheader("Your Research History")
        all_res = load_data("research_status")
        if not all_res.empty:
            all_res['staff_id'] = all_res['staff_id'].astype(str).str.split('.').str[0].str.strip()
            my_res = all_res[all_res['staff_id'] == st.session_state.user]
            st.dataframe(my_res, use_container_width=True)

    with tab_fault:
        with st.form("fault_form"):
            f_loc, f_desc = st.text_input("Location"), st.text_area("Fault Details")
            if st.form_submit_button("Report Fault"):
                old_m = load_data("maintenance_tickets")
                new_f = pd.DataFrame([{"ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}", "reporter": st.session_state.name, "reporter_id": st.session_state.user, "location": f_loc, "fault_description": f_desc, "status": "Open", "date_reported": datetime.now().strftime("%Y-%m-%d")}])
                conn.update(worksheet="maintenance_tickets", data=pd.concat([old_m, new_f], ignore_index=True))
                st.cache_data.clear()
                st.rerun()

# --- 9. MAINTENANCE MANAGER ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Manager")
    m_df = load_data("maintenance_tickets")
    st.dataframe(m_df[m_df['status'] != "Resolved"], use_container_width=True)
    with st.expander("Update Ticket"):
        open_j = m_df[m_df['status'] != "Resolved"]
        if not open_j.empty:
            tid = st.selectbox("Ticket ID", open_j['ticket_id'].tolist())
            ns = st.selectbox("Status", ["In-Progress", "Awaiting Parts", "Resolved"])
            if st.button("Update"):
                m_df.loc[m_df['ticket_id'] == tid, 'status'] = ns
                conn.update(worksheet="maintenance_tickets", data=m_df)
                st.cache_data.clear()
                st.rerun()
