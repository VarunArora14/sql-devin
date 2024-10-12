import os
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, inspect
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain.chains import create_sql_query_chain

load_dotenv()

def initSqliteDBLangchain(dbName = "mydb.db"):
    try:
        print("connecting to DB...")
        dbUri = f"sqlite:///{dbName}"
        db = SQLDatabase.from_uri(dbUri)
        print("Connection established! Url:", dbUri)
        return db
    except Exception as e:
        print("Cannot establish connection to DB\nError:", str(e))
        return None

db = initSqliteDBLangchain()

def get_schema(db):
    schema = db.get_table_info()
    return schema

schema = get_schema(db)
print(schema)


template = """Based on the table schema below, write a SQL query that would answer the user's question:
{schema}

Question: {question}
SQL Query:"""
prompt = ChatPromptTemplate.from_template(template)

def initGeminiLLM():
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.5, max_retries=3)
    return llm

llm = initGeminiLLM()

user_question = 'which artists are top 5 most popular?'

sql_chain = (
    prompt
    | llm
    | StrOutputParser()
)


res = sql_chain.invoke({"question": user_question, "schema": get_schema(db)})
print(res)

res2 = [ele for ele in res.split("\n") if "```" not in ele]
queryToRun = '\n'.join(res2)
queryToRun


def run_query(query):
    return db.run(query)
run_query(query=queryToRun)

print(schema)