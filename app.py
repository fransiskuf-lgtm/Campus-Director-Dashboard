import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import hashlib
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="UNAM JEDS Director Dashboard", layout="wide", page_icon="🏫")

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- HELPERS ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_data(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl=0)
    except:
        return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Campus_Report')
    return output.getvalue()

# --- STANDARDIZED OPTIONS ---
DEPARTMENTS = [
    "Civil and Environmental Engineering",
    "Electrical and Computer Engineering",
    "Mechanical and Marine Engineering",
    "Mining and Metallurgical Engineering",
    "Electronics and Telecommunications",
    "Management & Administration"
]

ARTICLE_TYPES = [
    "Journal Article (Peer Reviewed)",
    "Conference Paper",
    "Book Chapter",
    "Technical Report",
    "Patent Application",
    "Review Paper"
]

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None, "dept": None})

# --- AUTHENTICATION & REGISTRATION ---
if not st.session_state.logged_in:
    st.title("UNAM JEDS Engineering")
    st.subheader("Campus Management System")
    
    auth_mode = st.tabs(["Login", "Staff Registration"])
    
    with auth_mode[0]: # Login Tab
        with st.form("login_form"):
            sid = st.text_input("Staff ID")
            pwd = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                users = load_data("staff_registry")
                user_row = users[users['staff_id'].astype(str) == str(sid)]
                
                if not user_row.empty:
                    if user_row.iloc[0]['password'] == hash_password(pwd):
                        st.session_state.update({
                            "logged_in": True,
                            "user": sid,
                            "name": user_row.iloc[0]['full_name'],
                            "role": user_row.iloc[0]['role'],
                            "dept": user_row.iloc[0]['department']
                        })
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
                else:
                    st.error("Staff ID not found.")

    with auth_mode[1]: # Registration Tab
        with st.form("reg_form"):
            st.info("Registration requires a security key provided by the Director.")
            new_id = st.text_input("Staff ID (Employee Number)")
            new_name = st.text_input("Full Name")
            new_dept = st.selectbox("Department", DEPARTMENTS)
            new_email = st.text_input("Email Address")
            new_pwd = st.text_input("Set Password", type="password")
            reg_key = st.text_input("Security Registration Key", type="password")
            
            if st.form_submit_button("Register Account"):
                role = None
                if reg_key == "JEDSACA2026": role = "Academic"
                elif reg_key == "JEDSSUP2026": role = "Maintenance"
                
                if role:
                    users = load_data("staff_registry")
                    if str(new_id) in users['staff_id'].astype(str).values:
                        st.error("This Staff ID is already registered.")
                    else:
                        new_user = pd.DataFrame([{
                            "staff_id": new_id, 
                            "full_name": new_name, 
                            "email": new_email,
                            "role": role, 
                            "password": hash_password(new_pwd), 
                            "department": new_dept
                        }])
                        conn.update(worksheet="staff_registry", data=pd.concat([users, new_user], ignore_index=True))
                        st.success(f"Successfully registered as {role}! You can now Login.")
                else:
                    st.error("Invalid Security Key.")
    st.stop()

# --- LOGGED IN UI ---
st.sidebar.title("JEDS Dashboard")
st.sidebar.write(f"**User:** {st.session_state.name}")
st.sidebar.write(f"**Dept:** {st.session_state.dept}")
st.sidebar.write(f"**Role:** {st.session_state.role}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- DIRECTOR MODULE ---
if st.session_state.role == "Director":
    st.title("🏛️ Campus Director Dashboard")
    t1, t2 = st.tabs(["Research Oversight", "Maintenance Audit"])
    
    with t1:
        res_df = load_data("research_status")
        st.subheader("Academic Research Summary")
        
        # Metric Tiles
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Papers", len(res_df))
        c2.metric("Published", len(res_df[res_df['status']=="Published"]))
        c3.metric("Pending APCs", len(res_df[res_df['director_approval']=="Pending"]))

        # Filter View
        search_dept = st.selectbox("View Departmental Progress", ["All"] + DEPARTMENTS)
        display_df = res_df if search_dept == "All" else res_df[res_df['department'] == search_dept]
        st.dataframe(display_df, use_container_width=True)
        
        # Approval Logic
        pending = res_df[res_df['director_approval'] == "Pending"]
        if not pending.empty:
            st.divider()
            st.subheader("Action Required: Funding Approvals")
            target = st.selectbox("Select Paper for Approval/Decline", pending['paper_title'].tolist())
            col_a, col_b = st.columns(2)
            if col_a.button("✅ Approve APC"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.success(f"APC for {target} Approved.")
                st.rerun()
            if col_b.button("❌ Decline APC"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Declined"
                conn.update(worksheet="research_status", data=res_df)
                st.warning(f"APC for {target} Declined.")
                st.rerun()
        
        st.divider()
        st.download_button("📥 Download Research Excel Report", data=to_excel(res_df), file_name="JEDS_Research_Status.xlsx")

    with t2:
        st.subheader("Campus Maintenance Tracking")
        m_df = load_data("maintenance_tickets")
        st.dataframe(m_df, use_container_width=True)
        st.download_button("📥 Download Maintenance Logs", data=to_excel(m_df), file_name="JEDS_Maintenance_Log.xlsx")

# --- ACADEMIC STAFF MODULE ---
elif st.session_state.role == "Academic":
    st.title("📖 Academic Staff Portal")
    
    with st.form("res_submission"):
        st.subheader("Submit or Update Research Progress")
        p_title = st.text_input("Title of the Paper/Article")
        p_type = st.selectbox("Article Type", ARTICLE_TYPES)
        p_status = st.selectbox("Current Status", ["Draft", "Under Review", "Pending APC", "Published"])
        p_apc = st.number_input("APC Amount Requested (if any)", min_value=0)
        
        if st.form_submit_button("Submit Update"):
            old_data = load_data("research_status")
            new_entry = pd.DataFrame([{
                "staff_id": st.session_state.user,
                "full_name": st.session_state.name,
                "department": st.session_state.dept,
                "paper_title": p_title,
                "article_type": p_type,
                "status": p_status,
                "apc_amount": p_apc,
                "director_approval": "Pending" if p_status == "Pending APC" else "N/A",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            }])
            conn.update(worksheet="research_status", data=pd.concat([old_data, new_entry], ignore_index=True))
            st.success("Research status successfully recorded.")

# --- MAINTENANCE MANAGER MODULE ---
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Management")
    m_df = load_data("maintenance_tickets")
    
    st.subheader("Active Job Cards")
    active_jobs = m_df[m_df['status'] != "Resolved"]
    st.dataframe(active_jobs, use_container_width=True)
    
    if not active_jobs.empty:
        with st.expander("Update Ticket / Job Card"):
            sel_tkt = st.selectbox("Ticket ID", active_jobs['ticket_id'].tolist())
            up_stat = st.selectbox("New Status", ["In-Progress", "Awaiting Parts", "Resolved"])
            up_rem = st.text_area("Manager Remarks")
            if st.button("Update Progress"):
                m_df.loc[m_df['ticket_id'] == sel_tkt, 'status'] = up_stat
                m_df.loc[m_df['ticket_id'] == sel_tkt, 'manager_remarks'] = up_rem
                conn.update(worksheet="maintenance_tickets", data=m_df)
                st.success("Job card updated.")
                st.rerun()

# --- SHARED FAULT REPORTING ---
st.sidebar.divider()
if st.sidebar.checkbox("Report a Fault / Complaint"):
    st.info("Directly alert the maintenance manager of campus faults.")
    with st.form("fault_report"):
        f_loc = st.text_input("Location (Building & Room)")
        f_desc = st.text_area("Description of Fault")
        f_pri = st.select_slider("Priority Level", options=["Low", "Medium", "High"])
        if st.form_submit_button("Send Report"):
            m_old = load_data("maintenance_tickets")
            new_ticket = pd.DataFrame([{
                "ticket_id": f"JEDS-{datetime.now().strftime('%M%S')}",
                "reporter": st.session_state.name,
                "location": f_loc,
                "fault_description": f_desc,
                "priority": f_pri,
                "status": "Open",
                "manager_remarks": "",
                "date_reported": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([m_old, new_ticket], ignore_index=True))
            st.success("Fault reported to the system.")
