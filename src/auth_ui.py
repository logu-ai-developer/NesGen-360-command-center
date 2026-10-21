"""Authentication gate renders before any dashboard route or source load."""
import streamlit as st
from src import auth

st.markdown("""
<style>
/* Normal: yellow background, red text */
.st-key-auth_logout button {
    background-color: #FFFF00 !important;
    border-color: #FFFF00 !important;
    color: #CC0000 !important;
    transition: background-color 0.25s ease, color 0.25s ease;
}

.st-key-auth_logout button p {
    color: #CC0000 !important;
    transition: color 0.25s ease;
}

/* Hover: blue background, yellow text */
.st-key-auth_logout button:hover {
    background-color: #0057B8 !important;
    border-color: #0057B8 !important;
    color: #FFFF00 !important;
}

.st-key-auth_logout button:hover p {
    color: #FFFF00 !important;
}
</style>
""", unsafe_allow_html=True)

def clear_session():
    token=st.session_state.get('auth_token')
    if token:auth.logout(token)
    for key in list(st.session_state):del st.session_state[key]
    auth.bind(None)

def gate():
    auth.bind(None)
    token=st.session_state.get('auth_token')
    user=auth.principal(token) if token else None
    if user:
        auth.bind(token)
        with st.sidebar:
            st.caption(f"Signed in: {user['user_name']} · {user['role']}")
            if st.button('Log out',key='auth_logout', type='primary'):
                clear_session();st.rerun()
        return user
    if token:clear_session()
    st.title('NesGen 360°')
    st.subheader('Operations & Governance · Demo sign-in')
    st.info('Synthetic or approved sanitized data only. AI can make mistakes. Check cited evidence; operational decisions require human review. Local demo authentication is not enterprise identity verification.')
    if not auth.has_admin():
        st.warning('First-time setup required. Run python scripts/setup_admin.py locally, then refresh. No default administrator password is shipped.')
        st.stop()
    login_tab,register_tab=st.tabs(['Sign in','Create demo account'])
    with login_tab:
        with st.form('auth_login',clear_on_submit=True):
            name=st.text_input('Username',max_chars=40)
            password=st.text_input('Password',type='password',max_chars=128)
            submitted=st.form_submit_button('Sign in',type='primary')
        if submitted:
            token=auth.login(name,password)
            if token:
                clear_session();st.session_state.auth_token=token;st.rerun()
            else:st.error('Sign-in unsuccessful. Check your credentials or wait before trying again.')
    with register_tab:
        st.caption('Registration creates an end-user account only. Use demo profile details; email is optional and not verified.')
        with st.form('auth_register',clear_on_submit=True):
            name=st.text_input('Choose username',max_chars=40)
            display=st.text_input('Display name',max_chars=100)
            group=st.selectbox('Stakeholder group',auth.GROUPS)
            email=st.text_input('Email (optional)',max_chars=254)
            password=st.text_input('Choose password (15–128 characters)',type='password',max_chars=128)
            confirm=st.text_input('Confirm password',type='password',max_chars=128)
            consent=st.checkbox('I understand this is a demo and will not enter confidential information.')
            submitted=st.form_submit_button('Create end-user account')
        if submitted:
            if not consent:st.error('Please acknowledge the demo notice.')
            elif password!=confirm:st.error('Passwords do not match.')
            else:
                try:auth.register_end_user(name,password,display,group,email);st.success('Account created. Use Sign in to continue.')
                except ValueError as exc:st.error(str(exc))
    st.stop()

def user_management():
    auth.require_admin()
    with st.expander('Demo user management'):
        users=auth.list_users();st.dataframe(users,hide_index=True,width='stretch')
        end_users=[u for u in users if u['role']=='end_user']
        if end_users:
            selected=st.selectbox('End-user account',[u['user_name'] for u in end_users])
            target=next(u for u in end_users if u['user_name']==selected)
            active=st.checkbox('Account active',value=bool(target['is_active']))
            if st.button('Save account status'):
                auth.set_user_active(target['id'],active);st.success('Account status saved; existing sessions revoked.');st.rerun()
