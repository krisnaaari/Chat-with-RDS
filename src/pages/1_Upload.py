from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
import streamlit as st
import os
import tempfile
import codecs
import re


def init_database_from_file(file_path: str) -> SQLDatabase:
    return SQLDatabase.from_uri(f"sqlite:///{file_path}")


def clean_mysql_to_sqlite(sql_script: str) -> str:
    # Remove MySQL-specific character set, collation, and engine directives
    sql_script = re.sub(r" CHARACTER SET \w+", "", sql_script)
    sql_script = re.sub(r" COLLATE=\w+", "", sql_script)
    sql_script = re.sub(r" ENGINE=\w+", "", sql_script)
    sql_script = re.sub(r" DEFAULT CHARSET=\w+", "", sql_script)
    sql_script = re.sub(r" AUTO_INCREMENT", "", sql_script)

    # Remove MySQL-specific key and constraint definitions
    sql_script = re.sub(r" KEY `\w+` \(`\w+`\),", "", sql_script)
    sql_script = re.sub(r" CONSTRAINT `\w+` FOREIGN KEY \(`\w+`\) REFERENCES `\w+` \(`\w+`\),?", "", sql_script)

    # Replace int with INTEGER for SQLite
    sql_script = re.sub(r" int ", " INTEGER ", sql_script, flags=re.IGNORECASE)

    return sql_script


def execute_sql_script(db: SQLDatabase, script_path: str):
    with codecs.open(script_path, 'r', encoding='utf-8') as file:
        script = file.read()
    clean_script = clean_mysql_to_sqlite(script)
    statements = clean_script.split(';')
    for statement in statements:
        if statement.strip():
            db.run(statement.strip())



def get_sql_chain(db):
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.

    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}

    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.

    For example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
    Question: Name 10 artists
    SQL Query: SELECT Name FROM Artist LIMIT 10;

    Your turn:

    Question: {question}
    SQL Query:
    """

    # prompt = ChatPromptTemplate.from_template(template)
    #
    # # llm = ChatOpenAI(model="gpt-4-0125-preview")
    # llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
    #
    # def get_schema(_):
    #     return db.get_table_info()
    #
    # return (
    #         RunnablePassthrough.assign(schema=get_schema)
    #         | prompt
    #         | llm
    #         | StrOutputParser()
    # )
    return ""


def get_response(user_query: str, db: SQLDatabase, chat_history: list):
    sql_chain = get_sql_chain(db)

    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}"""

    # prompt = ChatPromptTemplate.from_template(template)
    #
    # # llm = ChatOpenAI(model="gpt-4-0125-preview")
    # llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
    #
    # chain = (
    #         RunnablePassthrough.assign(query=sql_chain).assign(
    #             schema=lambda _: db.get_table_info(),
    #             response=lambda vars: db.run(vars["query"]),
    #         )
    #         | prompt
    #         | llm
    #         | StrOutputParser()
    # )
    #
    # return chain.invoke({
    #     "question": user_query,
    #     "chat_history": chat_history,
    # })
    return ""


if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        AIMessage(content="Hello! I'm a SQL assistant. Ask me anything about your database."),
    ]

#load_dotenv()

st.set_page_config(page_title="Chat with Database", page_icon=":speech_balloon:")

st.title("Chat with Database")

with st.sidebar:
    st.subheader("Upload Database File")
    st.write(
        "Upload the file and start chatting.")

    uploaded_file = st.file_uploader("Choose a .db or .sql file", type=["db", "sql"])

    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name

        if uploaded_file.name.endswith(".db"):
            st.session_state.db = init_database_from_file(temp_file_path)
            st.success("Database file uploaded and connected!")
        elif uploaded_file.name.endswith(".sql"):
            if "db" not in st.session_state:
                st.session_state.db = init_database_from_file(":memory:")
            execute_sql_script(st.session_state.db, temp_file_path)
            st.success("SQL script executed and in-memory database created!")

for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message("AI"):
            st.markdown(message.content)
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(message.content)

user_query = st.chat_input("Type a message...")
if user_query is not None and user_query.strip() != "":
    st.session_state.chat_history.append(HumanMessage(content=user_query))

    with st.chat_message("Human"):
        st.markdown(user_query)

    with st.chat_message("AI"):
        response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(response)

    st.session_state.chat_history.append(AIMessage(content=response))
