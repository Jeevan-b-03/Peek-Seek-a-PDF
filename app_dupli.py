#With features of auto clear history, keyword trigerred questions-Keyword:"nee vena sandaiku va"

import streamlit as st
import os
import time

# userprompt
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

# vectorDB
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.ollama import OllamaEmbeddings

# llms
from langchain_community.llms import Ollama
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.manager import CallbackManager

# pdf loader
from langchain_community.document_loaders import PyPDFLoader

# pdf processing
from langchain.text_splitter import RecursiveCharacterTextSplitter

# retrieval
from langchain.chains import RetrievalQA

# Clear the pdfFiles folder at session start
pdf_folder = 'pdfFiles'
if os.path.exists(pdf_folder):
    for file in os.listdir(pdf_folder):
        os.remove(os.path.join(pdf_folder, file))
else:
    os.makedirs(pdf_folder)

if not os.path.exists('vectorDB'):
    os.makedirs('vectorDB')

if 'template' not in st.session_state:
    st.session_state.template = """You are a knowledgeable chatbot, here to help with questions of the user. Your tone should be professional and informative.

    Context: {context}
    History: {history}

    User: {question}
    Chatbot:"""

if 'prompt' not in st.session_state:
    st.session_state.prompt = PromptTemplate(
        input_variables=["history", "context", "question"],
        template=st.session_state.template,
    )

if 'memory' not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="history",
        return_messages=True,
        input_key="question",
    )

if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = Chroma(persist_directory='vectorDB',
                                          embedding_function=OllamaEmbeddings(base_url='http://localhost:11434',
                                          model="llama3")
                                          )

if 'llm' not in st.session_state:
    st.session_state.llm = Ollama(base_url="http://localhost:11434",
                                  model="llama3",
                                  verbose=True,
                                  callback_manager=CallbackManager(
                                      [StreamingStdOutCallbackHandler()]),
                                  )

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

st.title("Peek&Seek-a-pdf")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["message"])

if uploaded_file is not None:
    st.text("File uploaded successfully")
    file_path = os.path.join(pdf_folder, uploaded_file.name)
    if not os.path.exists(file_path):
        with st.status("Saving file..."):
            bytes_data = uploaded_file.read()
            with open(file_path, 'wb') as f:
                f.write(bytes_data)

            loader = PyPDFLoader(file_path)
            data = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=200,
                length_function=len
            )

            all_splits = text_splitter.split_documents(data)

            st.session_state.vectorstore = Chroma.from_documents(
                documents=all_splits,
                embedding=OllamaEmbeddings(model="llama3")
            )

            st.session_state.vectorstore.persist()

    st.session_state.retriever = st.session_state.vectorstore.as_retriever()

    if 'qa_chain' not in st.session_state:
        st.session_state.qa_chain = RetrievalQA.from_chain_type(
            llm=st.session_state.llm,
            chain_type='stuff',
            retriever=st.session_state.retriever,
            verbose=True,
            chain_type_kwargs={
                "verbose": True,
                "prompt": st.session_state.prompt,
                "memory": st.session_state.memory,
            }
        )

if 'qa_chain' in st.session_state and 'retriever' in st.session_state:
    if user_input := st.chat_input("You:", key="user_input"):
        user_message = {"role": "user", "message": user_input}
        st.session_state.chat_history.append(user_message)
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Assistant is typing..."):
                if user_input.strip().lower() == "nee vena sandaiku va":
                    analysis_prompt = """Analyze the provided document and generate a set of insightful questions that a user might ask based on the content. The questions should help extract key information from the document."""
                    response = st.session_state.qa_chain(analysis_prompt)
                    response = response['result']
                else:
                    response = st.session_state.qa_chain(user_input)
                    response = response['result']

            message_placeholder = st.empty()
            full_response = ""
            for chunk in response.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)

        chatbot_message = {"role": "assistant", "message": response}
        st.session_state.chat_history.append(chatbot_message)
else:
    st.write("Please upload a PDF file to start the chatbot")
