import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.load import loads, dumps
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from pydantic import BaseModel, AfterValidator, Field, ValidationError
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import traceback

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

# TODO: Implement using conversation history or Memory for using potentially previous chats for reference (AVG priority)
if "conversation_history" not in st.session_state:
    st.error("CONVERSATION HISTORY NOT IN STATE! Go to Welcome and reload!")
else:
    conversation_history = st.session_state["conversation_history"]

if "db_client" not in st.session_state:
    st.error("DB Client NOT IN STATE! Go to Welcome and reload!")
else:
    db_client = st.session_state["db_client"]


class LLMResponse(BaseModel):
    query: str = Field("SQL query which is syntactically correct to run on SQL databases without any headers or comments")
    isValidResponse: bool = Field(description="False when the user question not related to querying data from SQL database or tables or tables or fields don't exist as questioned, True otherwise.")
    shouldRunQuery: bool = Field(description="Set to True if user wants results from database/table or gives query to run. False if user only wants the query to be generated or query to be explained. Set to False if can't determine whether user wants to get results from database/table.")
    errorMessage: str = Field("Error message given by assistant  when user question not related to querying data or tries to modify data in tables")

class QuestionClassificationResponse(BaseModel):
    question: str = Field("User question to be classified")
    isValidQuestion: bool = Field(description="False if question not related to querying data from SQL database or tables, True otherwise.")
    shouldRunQuery: bool = Field(description="Set to True if user wants results from database/table or gives query to run. False if user only wants the query to be generated or query to be explained. Set to False if can't determine whether user wants to get results from database/table.")
    errorMessage: str = Field("Error message given by assistant when user question not related to querying data or tries to modify data in tables")

def classifyQuesValidity(question:str):
    template = """
    Consider the following question and classify whether the question is related to querying data from SQL databases or tables. Make sure the question does not modify data by creating, inserting, updating, deleting or dropping any table data. The question must not have triggers or change any permissions.
    
    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)
    
    try:
        validatorResponse: QuestionClassificationResponse = client.chat.completions.create(
        response_model=QuestionClassificationResponse,
        messages=[{"role": "user", "content": prompt.format(question=question)}],
        max_retries=1    
        )
        return validatorResponse
    except Exception as e:
        print("initial prompt:", prompt.format(question=question))
        return QuestionClassificationResponse(
            question=question,
            isValidQuestion=False,
            shouldRunQuery=False,
            errorMessage="Unable to classsify the question with followig error-\n"+str(e)
        )
class MarkdownResponse:
    def __init__(self, containsDataframe: bool, responseMessage:str, dataframe=None, df_explanation=None) -> None:
        self.containsDatafame = containsDataframe
        self.dataframe = dataframe
        self.responseMessage = responseMessage
        self.df_explanation = df_explanation
    

def explainDataframeOutput(dataframe: pd.DataFrame, question:str) -> str:
    """
    Generates a detailed explanation of the data contained in the given dataframe.

    Parameters:
    dataframe (pd.DataFrame): The dataframe to be explained.

    Returns:
    str: A detailed explanation of the dataframe's contents.
    """
    promptTemplate = """

        I have the following SQL query result and I would like an explanation of the output:

        SQL query result:
        {dataframe}
        
        Refer to initial user question to understand the context of the query and the expected output
        Question:
        {question}
        
        Can you explain the meaning of this output, including the data columns and how they relate to the query? Please also provide insight into how the results are derived and any patterns or trends you observe in the data.
        """
    prompt = PromptTemplate(template=promptTemplate, input_variables=["dataframe", "question"])
        
    explain_chain = (
            prompt |
            llm |
            StrOutputParser()
        )
    return explain_chain.invoke({"dataframe": dataframe.to_string(), "question":question}).strip()
    

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
    Given the following user question and SQL query, provide an explanation of how the SQL query addresses the question. Be sure to describe the purpose of each part of the SQL query, how the data is being retrieved or manipulated, and how the query aligns with the user's intent. Use simple, clear language that breaks down the SQL logic.

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

def get_schema(db_client):
    """
    Get table schema as context for LLM to consider while answering user queries
    """
    cursor = db_client.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    res = []
    for table_name in tables:
        table = table_name[0]
        cursor.execute(f"PRAGMA table_info({table});")
        schema = cursor.fetchall()
        
        # Format the schema for LLM
        formatted_schema = format_schema_for_llm(table, schema)
        # print(formatted_schema)
        res.append(formatted_schema)

    return "\n".join(res)

def runQueryDf(query:str):
    try:
        df = pd.read_sql_query(query, db_client)
    except Exception as e:
        return str(e)
    return df

def generateFirstAnswer(conversation_history, db_client, user_question = "give info of all tables in the database"):     
    print("question:", user_question)
    schema = get_schema(db_client=db_client)
    template = """Given the following Sqlite table schemas and example row data, generate an SQL query to answer the user's question. Ensure the query is correctly structured according to SQL syntax and that it is relevant to the provided tables and columns. The generated query will be validated for syntax and database relevance.


    Table Schemas with example row data:
    {schema}

    Initial Question: {initial_question}
    Rewritten Question: {rewritten_question}

    Answer:"""
    prompt = ChatPromptTemplate.from_template(template)

    # print(prompt.format(schema=schema, question=user_question))

    # conversation_history.append({"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question))})
    try:
        validatorResponse: LLMResponse = client.chat.completions.create(
        response_model=LLMResponse,
        messages=[{"role": "user", "content": prompt.format(schema=schema, initial_question=user_question, rewritten_question=queryRewrite(question=user_question))}],
        max_retries=3    
        )
        return validatorResponse
    except Exception as e:
        print("initial prompt:", prompt.format(schema=schema, initial_question=user_question, rewritten_question=queryRewrite(question=user_question)))
        return LLMResponse(
            errorMessage=str(e),
            isValidResponse=False,
            shouldRunQuery=False,
            query="NO QUERY GENERATED"
        )

# Will modify when implementing retries later
# def generateAnswerAfterError(conversation_history, db_client, errorMessage:str, user_question:str = "give info of all tables in the database"):
#     schema = get_schema(db_client=db_client)
#     template = """Given the following table schemas and error message from previously generated SQL query, generate a corrected SQL query to answer the user's question. Ensure the new query avoids the issues indicated by the error message and aligns with the provided table structure.


#     Table Schemas with example row data:
#     {schema}

#     Question: {question}
    
#     Error Message from Previous Query:
#     {errorMessage}

#     Answer:"""
#     prompt = ChatPromptTemplate.from_template(template)

#     # print(prompt.format(schema=schema, question=user_question))
#     conversation_history.append( )
#     validatorResponse: LLMResponse = client.chat.completions.create(
#     response_model=LLMResponse,
#     messages=[{"role": "user", "content": prompt.format(schema=schema, question=queryRewrite(question=user_question), errorMessage=errorMessage)}]
#     )
#     return validatorResponse

# TODO: implement chat history use/memory use later(prefer chat history first)
# TODO: implement max retries later
# def getMaxRetriesResponse(conversation_history, db_client, errorMessage, question, max_retries=3):
#     response = generateAnswerAfterError(conversation_history=conversation_history, db_client=db_client, errorMessage=errorMessage,user_question=question)
#     if response.isValidResponse == False:
#         # TODO: show the error message
#         st.write(response.errorMessage)
#     elif response.isValidResponse and response.shouldRunQuery==False:
#         st.write(f"Generated Query: {response.query}")
#         st.write("Explanation:\n")
#         st.write(explainQuery(question=question, query=response.query))
#     else:
#         while max_retries:
#             max_retries-=1
#             # this can fail
#             try:
#                 df = pd.read_sql_query(response.query, db_client)
#                 st.write(f"Generated Query: {response.query}")
#                 st.write(df)
#                 st.write("Explanation:\n")
#                 st.write(explainQuery(question=question, query=response.query))
#             except Exception as e:
#                 errorMessage = str(e)
#                 st.error(f"Error Generated:\n{errorMessage}")

def getAssistantResponse(message):
    return {"role": "assistant", "content": message}

def getLLMResponse(question:str):
    
    # classify question
    classificationResponse = classifyQuesValidity(question=question)
    shouldRunQuery = classificationResponse.shouldRunQuery
    print("should run query:",classificationResponse.shouldRunQuery)
    
    if classificationResponse.isValidQuestion == False:
        return getAssistantResponse(MarkdownResponse(containsDataframe=False, responseMessage=classificationResponse.errorMessage))
        
    validatedResponse = generateFirstAnswer(conversation_history=conversation_history, db_client=db_client, user_question=question)
    print(validatedResponse.__dict__)
    sql_query = validatedResponse.query
    markdown_response = None
    if validatedResponse.isValidResponse == False:
        # TODO: show the error message
        error_message = f"""
        ### Invalid Question
        
        {validatedResponse.errorMessage}
        """
        markdown_response = MarkdownResponse(containsDataframe=False, responseMessage=error_message.strip())
        print(markdown_response)
    elif validatedResponse.isValidResponse and (shouldRunQuery == False):
        explanation:str = explainQuery(question=question, query=sql_query) # TODO: explain only when query works        
        resp = f"""
        Generated Query: `{sql_query}`
        
        ### Explanation:
        {explanation}
        """
        markdown_response = MarkdownResponse(containsDataframe=False, responseMessage=resp.strip())
    else:
        try:
            df = pd.read_sql_query(sql_query, db_client)
            explanation:str = explainQuery(question=question, query=sql_query) 
            df_explanation:str = explainDataframeOutput(dataframe=df, question=question) # TODO: explain only when query works
            # query run successfully, return the explanation and results)
                        
            resp = f"""
            ### Output Explanation:
            {df_explanation}
            
            Generated Query: `{sql_query}`
            """
            markdown_response = MarkdownResponse(containsDataframe=True, responseMessage=resp.strip(), dataframe=df, df_explanation=df_explanation)
        except Exception as e:
        # TODO: generate answer again considering error
            resp = f"""
            Generated Query: `{sql_query}`
            
            Error while running the query:
            {str(e)}
            """
            markdown_response = MarkdownResponse(containsDataframe=False, responseMessage=resp.strip())
        print("md response:",markdown_response.__dict__)                
    return getAssistantResponse(markdown_response)



# st.title("🤖 Welcome to the Personal Blog Chatbot! 🌐")
# Short Intro Section
st.title("SQL Devin 🛠️")
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
# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:    
    if message["role"] == "user":
        with st.chat_message("user"):
            st.write(message["content"])
    else:
        with st.chat_message("assistant"):
            obj: MarkdownResponse = message["content"]
            print("obj print:",obj.__dict__)
            if obj.containsDatafame:
                    st.write(f"**Result**:\n")
                    st.dataframe(obj.dataframe)                
                    st.write(obj.responseMessage)
            else:
                st.write(obj.responseMessage)
        # df_bool, df, response

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.write(prompt)

    # Call method to store ans in convo history to show later
    # TODO: add logic for error messages and retries here
    with st.chat_message("assistant"):
        if len(st.session_state.messages):
            try:
                response = getLLMResponse(question=st.session_state.messages[-1]["content"]) # added to end of list
                st.session_state.messages.append(response)
                print("messages:", st.session_state.messages)
                obj: MarkdownResponse = st.session_state.messages[-1]["content"]
                print(obj)
                print("obj:",obj.__dict__)
                if obj.containsDatafame:
                    st.write(f"**Result**:\n")
                    st.dataframe(obj.dataframe)
                    st.write(obj.responseMessage)
                else:
                    st.write(obj.responseMessage)
            except Exception as e:
                st.write("ERROR! Cannot run code due to: ", str(e))
                print(traceback.format_exc())
            # st.write(response)
    # st.session_state.messages.append({"role": "assistant", "content": response})
    # TODO: replace printing of messages with srtoring in session state if the above fails
    
    
# TODO: try max retries logic after basic app works and add it as integration