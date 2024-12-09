import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
import instructor
import google.generativeai as genai
from typing import List
import sqlite3
import streamlit_authenticator as stauth


# https://blog.streamlit.io/introducing-two-new-caching-commands-to-replace-st-cache/

st.set_page_config(
    page_title="SQL Devin",
    page_icon="⚛️",
)

@st.cache_resource
def initGeminiLLM():
    # load_dotenv()
    # GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    client = instructor.from_gemini(
    client=genai.GenerativeModel(
        model_name="models/gemini-1.5-flash-latest",  # model defaults to "gemini-pro"
    ),
    mode=instructor.Mode.GEMINI_JSON,
)
    
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5, max_retries=3)
    return client, llm

@st.cache_resource
def initConversationHistory():
    conversation_history: List[dict] = []
    return conversation_history

@st.cache_resource
def initSqliteConn(dbName ="mydb.db"):
    try:
        print("connecting to DB...")
        # conn = sqlite3.connect(database=dbName, check_same_thread=False)
        conn = sqlite3.connect('file:' + dbName + '?mode=ro', uri=True, check_same_thread=False)
        print("Connection established with db:", dbName)
        return conn
    except Exception as e:
        print("Cannot establish connection to DB\nError:", str(e))
        return None


# to be used by fusion and query decomposition
if "llm" not in st.session_state:
    st.session_state["client"], st.session_state["llm"] = initGeminiLLM()

if "conversation_history" not in st.session_state:
    st.session_state["conversation_history"] = initConversationHistory()

if "db_client" not in st.session_state:
    db_client = initSqliteConn()
    if not db_client:
        st.write("ERROR! DB not initialzied properly")
    st.session_state["db_client"] = db_client



# st.write("# ⚛️ Welcome to the SQL Devin 🤖")

# st.sidebar.success("Choose Fusion or Query Decomposition to start asking")

st.markdown(
    """
    # **SQL Devin** - Your Natural Language SQL Assistant 🤖

    Welcome to **SQL Devin**, a powerful tool that lets you interact with your databases and tables using **natural language**! Forget about memorizing SQL syntax—just tell SQL Devin what you want, and it will generate the SQL queries for you. Whether you need to create, delete, insert, drop, or perform any other operation on your database, SQL Devin is here to assist!

    ### 🌟 **Key Features:**

    - **Natural Language SQL Generation**: Simply describe what you want to do (e.g., "Insert a new employee into the Sales table") and SQL Devin will generate the appropriate SQL query for you.
    
    - **Database Operations**: Perform all major SQL operations, including:
    - **Create** tables, databases, or views
    - **Delete** records or drop tables
    - **Insert** new data
    - **Update** existing records
    - **Drop** tables, databases, or indexes
    - Any other SQL operations!

    - **Error Handling with Auto-Regeneration**: 
    - If a query fails due to an error (e.g., syntax issues, table not found), SQL Devin will automatically analyze the error message and regenerate the SQL query, fixing the issue for you. No need to troubleshoot manually!

    ### 🚀 **How It Works:**

    1. **Input your request in natural language**: Simply type in your intent, such as "Show me all employees in the Marketing department" or "Give top 5 records from music table".
    
    2. **SQL Devin processes your request**: The system will interpret your input and generate the SQL query corresponding to your request.

    # 3. **Error Handling**: If the query fails, SQL Devin will analyze the error, regenerate the SQL query considering the error message, and provide a corrected query automatically.

    ### 🛠️ **Get Started Now**:

    - Choose your database and table.
    - Describe what you want to do in plain language.
    - Let SQL Devin take care of the rest!

    #### Example Inputs:
    - "Analyze the customer table and provide insights from it."
    - "Insert a new row into Customers with ID=1, Name='John Doe', and Email='john@example.com'."
    - "Delete all records where department is 'HR'."

    Start typing your query and let **SQL Devin** handle the SQL!

    
    """
)