import streamlit as st
import json

st.set_page_config(page_title="Login", page_icon="🔒", layout="centered")

USERS_FILE_PATH = "users.json"

if "logged_in" not in st.session_state:
    st.session_state.logged_in=False

if "username" not in st.session_state:
    try:
        with open(USERS_FILE_PATH, "r") as f:
            st.session_state.username = json.load(f)['username']
            st.session_state.password = json.load(f)['password']
    except Exception as e:
        st.session_state.username = "admin"
        st.session_state.password = "chillbro"


def authenticate(username, password):
    """
    Function to validate user credentials
    """
    return st.session_state['username'] == username and st.session_state['password'] == password

def main():
    # App title
    st.title("Authentication page")

    # Authentication UI
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    login_button = st.sidebar.button("Login")

    if login_button:
        if authenticate(username, password):
            st.sidebar.success(f"Welcome {username}!")
            st.session_state.logged_in = True
            st.switch_page("pages/Welcome.py")
            st.sidebar.success("Login is successful!")
        else:
            st.sidebar.error("Invalid username or password")

    # Content displayed without authentication
    st.write("Authenticate yourself to access SQL Devin") 


if __name__ == "__main__":
    main()