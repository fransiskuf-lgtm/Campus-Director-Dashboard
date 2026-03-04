import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="UNAM JEDS Director Dashboard", layout="wide", page_icon="🏫")

# --- DATABASE CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

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

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({"logged_in": False, "user": None, "role": None, "name": None})

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
                user_row = users[users['staff_id'] == sid]
                if not user_row.empty and str(user_row.iloc[0]['password']) == pwd:
                    st.session_state.update({
                        "logged_in": True,
                        "user": sid,
                        "name": user_row.iloc[0]['full_name'],
                        "role": user_row.iloc[0]['role']
                    })
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please check your ID and Password.")

    with auth_mode[1]: # Registration Tab
        with st.form("reg_form"):
            st.info("Enter your details and the security key provided by the Director's office.")
            new_id = st.text_input("Preferred Staff ID (e.g. Employee Number)")
            new_name = st.text_input("Full Name")
            new_email = st.text_input("Email Address")
            new_pwd = st.text_input("Set Password", type="password")
            reg_key = st.text_input("Security Registration Key", type="password")
            
            if st.form_submit_button("Register Account"):
                role = None
                if reg_key == "JEDSACA2026": role = "Academic"
                elif reg_key == "JEDSSUP2026": role = "Maintenance" # Support handles maintenance
                
                if role:
                    users = load_data("staff_registry")
                    if new_id in users['staff_id'].astype(str).values:
                        st.error("This Staff ID is already registered.")
                    else:
                        new_user = pd.DataFrame([{
                            "staff_id": new_id, "full_name": new_name, "email": new_email,
                            "role": role, "password": new_pwd, "department": "Engineering"
                        }])
                        updated_users = pd.concat([users, new_user], ignore_index=True)
                        conn.update(worksheet="staff_registry", data=updated_users)
                        st.success(f"Successfully registered as {role} staff! Please go to the Login tab.")
                else:
                    st.error("Invalid Security Key.")
    st.stop()

# --- SIDEBAR NAV ---
st.sidebar.title("JEDS Dashboard")
st.sidebar.write(f"Logged in as: **{st.session_state.name}**")
st.sidebar.write(f"Access Level: {st.session_state.role}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- ROLE-BASED DASHBOARDS ---

# 1. DIRECTOR ROLE
if st.session_state.role == "Director":
    st.title("🏛️ Campus Director Oversight")
    
    d_tab1, d_tab2, d_tab3 = st.tabs(["Research & APCs", "Maintenance Logs", "Staff Management"])
    
    with d_tab1:
        st.subheader("Research Progress Across Campus")
        res_df = load_data("research_status")
        st.dataframe(res_df, use_container_width=True)
        
        st.subheader("Action Required: Pending APCs")
        pending_apc = res_df[res_df['director_approval'] == "Pending"]
        if not pending_apc.empty:
            target = st.selectbox("Select Project for Approval", pending_apc['paper_title'].tolist())
            col_a, col_b = st.columns(2)
            if col_a.button("✅ Approve APC Request"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Approved"
                conn.update(worksheet="research_status", data=res_df)
                st.success("APC Approved")
                st.rerun()
            if col_b.button("❌ Decline Request"):
                res_df.loc[res_df['paper_title'] == target, 'director_approval'] = "Declined"
                conn.update(worksheet="research_status", data=res_df)
                st.warning("APC Declined")
                st.rerun()
        
        st.download_button("📥 Download Research Report", data=to_excel(res_df), file_name="Campus_Research_Report.xlsx")

    with d_tab2:
        st.subheader("Maintenance Dashboard")
        maint_df = load_data("maintenance_tickets")
        st.dataframe(maint_df, use_container_width=True)
        st.download_button("📥 Download Maintenance Report", data=to_excel(maint_df), file_name="Campus_Maintenance_Report.xlsx")

# 2. ACADEMIC STAFF ROLE
elif st.session_state.role == "Academic":
    st.title("📖 Academic Staff Portal")
    
    with st.form("research_update"):
        st.subheader("Log Research Progress")
        title = st.text_input("Paper Title")
        journal = st.text_input("Target Journal")
        status = st.selectbox("Current Stage", ["Draft", "Under Review", "Pending APC", "Published"])
        apc_amt = st.number_input("APC Amount Required (N$)", min_value=0)
        
        if st.form_submit_button("Update Project"):
            old_res = load_data("research_status")
            new_entry = pd.DataFrame([{
                "staff_id": st.session_state.user, "paper_title": title, "journal": journal,
                "status": status, "apc_amount": apc_amt, 
                "director_approval": "Pending" if status == "Pending APC" else "N/A",
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="research_status", data=pd.concat([old_res, new_entry]))
            st.success("Research status updated successfully!")

# 3. MAINTENANCE MANAGER ROLE
elif st.session_state.role == "Maintenance":
    st.title("🔧 Maintenance Manager Portal")
    m_df = load_data("maintenance_tickets")
    
    st.subheader("Assigned Job Cards")
    open_jobs = m_df[m_df['status'] != "Resolved"]
    st.dataframe(open_jobs, use_container_width=True)
    
    with st.expander("Update Job Progress"):
        if not open_jobs.empty:
            ticket = st.selectbox("Select Ticket ID", open_jobs['ticket_id'].tolist())
            new_stat = st.selectbox("Update Status", ["In-Progress", "Awaiting Parts", "Resolved"])
            remarks = st.text_area("Manager Remarks")
            if st.button("Update System"):
                m_df.loc[m_df['ticket_id'] == ticket, 'status'] = new_stat
                m_df.loc[m_df['ticket_id'] == ticket, 'manager_remarks'] = remarks
                conn.update(worksheet="maintenance_tickets", data=m_df)
                st.success("Job Card Updated")
                st.rerun()

# 4. SHARED FAULT REPORTING (All Staff)
st.sidebar.divider()
if st.sidebar.checkbox("Report a Campus Fault"):
    st.header("New Maintenance Request")
    with st.form("fault_report"):
        loc = st.text_input("Location/Room Number")
        desc = st.text_area("Fault Description")
        pri = st.select_slider("Priority", options=["Low", "Medium", "High"])
        if st.form_submit_button("Report Fault"):
            old_m = load_data("maintenance_tickets")
            new_t = pd.DataFrame([{
                "ticket_id": f"TKT-{datetime.now().strftime('%M%S')}",
                "reporter": st.session_state.name, "location": loc,
                "fault_description": desc, "priority": pri, "status": "Open",
                "manager_remarks": "", "date_reported": datetime.now().strftime("%Y-%m-%d")
            }])
            conn.update(worksheet="maintenance_tickets", data=pd.concat([old_m, new_t]))
            st.success("Fault Reported to Maintenance Manager.")
