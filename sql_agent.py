import os
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_community.utilities import SQLDatabase
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from langchain.vectorstores import FAISS   
from pydantic import BaseModel, AfterValidator, Field, ValidationError
from langchain_core.output_parsers import StrOutputParser
import instructor
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import pandas as pd
import sqlite3
from typing import List
import streamlit as st

st.set_page_config(
    page_title="SQL Devin",
    page_icon="⚛️",
)


client,llm,conversation_history = None, None, None

if "llm" not in st.session_state:
    st.error("LLM NOT IN STATE! Go to Welcome and reload!")
else:
    llm=st.session_state['llm']
    client = st.session_state['client']

if "conversation_history" not in st.session_state:
    st.error("CONVERSATION HISTORY NOT IN STATE! Go to Welcome and reload!")
else:
    conversation_history = st.session_state["conversation_history"]

# TODO: classify query whether it tries to update/delete/drop/create any data

# avoiding this to make SQL devin
# class QueryClassifyResponse(BaseModel):
#     query: str
#     isValidQuery: bool = Field(description="False if query syntactically incorrect or modifies tables or database")
#     errorMessage: str = Field("Error message given by assistant when user question not related to querying data or tries to modify data in tables")

# def classifyQuery(query:str):
#     classify_template = """Consider the following table schema and classify whether the query is syntactically correct and can run on the mentioned tables considering their schema and data types. Make sure the query does not modify data by creating, inserting, updating, deleting or dropping any table data.
#     The query must not have triggers or change any permissions
#     Views can be created, modified and deleted.

#     Give True if query is valid and False otherwise.

#     Schema:
#     {schema}

#     Query: {query}

#     Answer:"""
#     classify_prompt = ChatPromptTemplate.from_template(template)
    
    

def queryRewrite(question:str):
    promptTemplate = """
    Rewrite the following user question to be more precise and suitable for generating a SQL query: 
    User Question:
    '{question}'
    
    Ensure the rewritten question is structured and clear enough to generate a SQL query.
    """
    prompt = PromptTemplate(template=promptTemplate, input_variables=["question"])
    
    rewrite_chain = (
        prompt |
        llm |
        StrOutputParser()
    )
    return rewrite_chain.invoke(question).strip()

def explainQuery(question:str, query:str):
    promptTemplate = """
    Given the following user question and SQL query, provide a detailed explanation of how the SQL query addresses the question. Be sure to describe the purpose of each part of the SQL query, how the data is being retrieved or manipulated, and how the query aligns with the user's intent. Use simple, clear language that breaks down the SQL logic.

    User Question:
    "{question}"

    SQL Query:
    "{query}"
    """
    prompt = PromptTemplate(template=promptTemplate, input_variables=["question", "query"])
    
    query_explain_chain = (
        prompt |
        llm |
        StrOutputParser()
    )
    return query_explain_chain.invoke({"question": question, "query": query}).strip()

class LLMResponse(BaseModel):
    query: str =Field("SQL query which is syntactically correct to run on SQL databases without any headers or comments")
    isValidResponse: bool = Field(description="False when the user question not related to querying data from SQL database or tables, True otherwise.")
    errorMessage: str = Field("Error message given by assistant  when user question not related to querying data or tries to modify data in tables")

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

def initSqliteConn(dbName ="mydb.db"):
    try:
        print("connecting to DB...")
        conn = sqlite3.connect(database=dbName, check_same_thread=False)
        print("Connection established with db:", dbName)
        return conn
    except Exception as e:
        print("Cannot establish connection to DB\nError:", str(e))
        return None

def get_schema(db):
    schema = db.get_table_info()
    return schema

schema = get_schema(db)
print(schema)


def generateFirstAnswer(db, user_question = "give info of all tables in the database"):
    schema = get_schema(db=db)
    template = """Given the following table schemas and example row data, generate an SQL query to answer the user's question. Ensure the query is correctly structured according to SQL syntax and that it is relevant to the provided tables and columns. The generated query will be validated for syntax and database relevance.


    Table Schemas with example row data:
    {schema}

    Question: {question}

    Answer:"""
    prompt = ChatPromptTemplate.from_template(template)

    # print(prompt.format(schema=schema, question=user_question))

    validatorResponse: LLMResponse = client.chat.completions.create(
    response_model=LLMResponse,
    messages=[
        {"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question))}
    ]
    )
    return validatorResponse

# TODO: max retries state code required
def generateAnswerAfterError(db, errorMessage:str, user_question:str = "give info of all tables in the database"):
    schema = get_schema(db=db)
    template = """Given the following table schemas and error message from previously generated SQL query, generate a corrected SQL query to answer the user's question. Ensure the new query avoids the issues indicated by the error message and aligns with the provided table structure.


    Table Schemas with example row data:
    {schema}

    Question: {question}
    
    Error Message from Previous Query:
    {errorMessage}

    Answer:"""
    prompt = ChatPromptTemplate.from_template(template)

    # print(prompt.format(schema=schema, question=user_question))

    validatorResponse: LLMResponse = client.chat.completions.create(
    response_model=LLMResponse,
    messages=[
        {"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question), errorMessage=errorMessage)}
    ]
    )
    return validatorResponse




def runQueryDf(query="select yo from bro"):
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        return str(e)
    return df
    
# df = runQueryDf(validatorResponse.query)
# df
conn  = initSqliteConn()

cursor = conn.cursor()
import sqlite3

# Step 1: Connect to the SQLite database (use ':memory:' for an in-memory DB)
conn = sqlite3.connect('./mydb.db')

# Step 2: Create a cursor object
cursor = conn.cursor()

# Step 3: Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

cursor.execute("drop table varun;")
tables = cursor.fetchall()
tables
# Step 4: Function to format schema for LLM
def format_schema_for_llm(table_name, schema):
    formatted_schema = f"Schema for table '{table_name}':\n"
    for column in schema:
        col_name = column[1]
        col_type = column[2]
        not_null = "not nullable" if column[3] else "nullable"
        default_val = f"with default value {column[4]}" if column[4] is not None else "without a default value"
        primary_key = "primary key" if column[5] else "not a primary key"

        if column[5]:
            formatted_schema+=f"Column '{col_name}' is of type {col_type}, and is {primary_key}.\n"
        else:
            formatted_schema+=f"Column '{col_name}' is of type {col_type}\n"
    
    return formatted_schema

# Step 5: Get the schema for each table and format it for LLM context
res = []
for table_name in tables:
    table = table_name[0]
    cursor.execute(f"PRAGMA table_info({table});")
    schema = cursor.fetchall()
    
    # Format the schema for LLM
    formatted_schema = format_schema_for_llm(table, schema)
    # print(formatted_schema)
    res.append(formatted_schema)

print("\n".join(res))
res

# Step 6: Close the connection
conn.close()



runQueryDf()
# add result to messages as query_status

# TODO: if the user question is invalid then just give back response to user giving the error message. If query is invalid then add that to messages array to show the user what is the error message by sql server => use that as context with previous data and generate query again (Retries max_retries=3) If retries are over then simply show the last error message and allow user to enter, till then keep running the code


conn = sqlite3.connect(database="mydb.db", check_same_thread=False)

pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
