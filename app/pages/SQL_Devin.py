import streamlit as st
from langchain.vectorstores import FAISS    
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.load import loads, dumps
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from pydantic import BaseModel, AfterValidator, Field, ValidationError
from langchain_core.prompts import ChatPromptTemplate


st.set_page_config(
    page_title="SQL Devin",
    page_icon="⚛️",
)


client,llm,conversation_history, db_client = None, None, None, None

if "llm" not in st.session_state:
    st.error("LLM NOT IN STATE! Go to Welcome and reload!")
else:
    llm=st.session_state['llm']
    client = st.session_state['client']

if "conversation_history" not in st.session_state:
    st.error("CONVERSATION HISTORY NOT IN STATE! Go to Welcome and reload!")
else:
    conversation_history = st.session_state["conversation_history"]

if "db_client" not in st.session_state:
    st.error("DB Client NOT IN STATE! Go to Welcome and reload!")
else:
    db_client = st.session_state["db_client"]


class LLMResponse(BaseModel):
    query: str =Field("SQL query which is syntactically correct to run on SQL databases without any headers or comments")
    isValidResponse: bool = Field(description="False when the user question not related to querying data from SQL database or tables, True otherwise.")
    errorMessage: str = Field("Error message given by assistant  when user question not related to querying data or tries to modify data in tables")


def queryRewrite(question:str)->str:
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

def explainQuery(question:str, query:str)->str:
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

def get_schema(db):
    schema = db.get_table_info()
    return schema

def generateFirstAnswer(conversation_history, db_client, user_question = "give info of all tables in the database"):
    schema = get_schema(db=db_client)
    template = """Given the following table schemas and example row data, generate an SQL query to answer the user's question. Ensure the query is correctly structured according to SQL syntax and that it is relevant to the provided tables and columns. The generated query will be validated for syntax and database relevance.


    Table Schemas with example row data:
    {schema}

    Question: {question}

    Answer:"""
    prompt = ChatPromptTemplate.from_template(template)

    # print(prompt.format(schema=schema, question=user_question))

    conversation_history.append({"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question))})

    validatorResponse: LLMResponse = client.chat.completions.create(
    response_model=LLMResponse,
    messages=conversation_history
    )
    return validatorResponse

def generateAnswerAfterError(conversation_history, db, errorMessage:str, user_question:str = "give info of all tables in the database"):
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
    conversation_history.append( {"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question), errorMessage=errorMessage)})
    validatorResponse: LLMResponse = client.chat.completions.create(
    response_model=LLMResponse,
    messages=conversation_history
    )
    return validatorResponse

def getLLMResponse(question:str):
    validatedResponse = generateFirstAnswer(conversation_history=conversation_history, db_client=db_client, user_question=question)
    if validatedResponse.isValidResponse:
        return validatedResponse.query
    else:
        return validatedResponse.errorMessage



# st.title("🤖 Welcome to the Personal Blog Chatbot! 🌐")
# Short Intro Section
st.title("SQL Devin 🛠")
st.markdown("""
### Welcome to SQL Devin
**SQL Devin** allows you to interact with databases and tables using **natural language**! 
No need to remember SQL syntax—just describe what you want, and SQL Devin will generate the appropriate query for you. 
You can create, delete, insert, update, drop, and more with simple natural language input.

If a query fails, don't worry—SQL Devin will automatically analyze the error and regenerate the query for you, fixing any issues.

**Example queries**:
- "Create a new table called Employees with columns Name, Age, and Department."
- "Insert a record into Employees where Name is 'John Doe', Age is 30, and Department is 'Sales'."
- "Show all employees in the HR department."
""")
# # Initialize chat history
# if "fusion_messages" not in st.session_state:
#     st.session_state.fusion_messages = []

# # Display chat messages from history on app rerun
# for message in st.session_state.fusion_messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # Accept user input
# if prompt := st.chat_input("What is up?"):
#     # Add user message to chat history
#     st.session_state.fusion_messages.append({"role": "user", "content": prompt})
#     # Display user message in chat message container
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     # Display assistant response in chat message container
#     with st.chat_message("assistant"):
#         if len(st.session_state.fusion_messages):
#             response = getFusionLLMResponse(question=st.session_state.fusion_messages[-1]["content"], llm=llm, retriever=vstore.as_retriever())
#             answer = None
#             if response["isValidResponse"]==False:
#                 answer = response["errorMessage"]
#             else:
#                 answer = response['answer'] + "\n\nSource: " + ", ".join(x for x in response['sources'])
#             st.write(answer)
#     st.session_state.fusion_messages.append({"role": "assistant", "content": answer})