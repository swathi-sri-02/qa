import os
import streamlit as st
import nltk
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import create_retrieval_chain
from transformers import pipeline
from dotenv import load_dotenv

# Ensure NLTK package is downloaded
nltk.download('punkt')

# Directories
UPLOAD_FOLDER = "pdf"
DB_FOLDER = "db"

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)

# Load models and setup
folder_path = "db"
pdf_folder_path = "pdf"
os.makedirs(folder_path, exist_ok=True)
os.makedirs(pdf_folder_path, exist_ok=True)

# Load environment variables
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
cached_llm = ChatGroq(groq_api_key=groq_api_key, model="Gemma-7b-It")
embedding = GoogleGenerativeAIEmbeddings(api_key=google_api_key, model="models/embedding-001")
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50, length_function=len)

raw_prompt = PromptTemplate.from_template(""" 
    <s>
        You are a highly knowledgeable technical assistant skilled at extracting and analyzing information from documents. Your primary task is to provide accurate answers using information present in the uploaded PDFs. 
        - If the exact information is not directly available, make reasonable inferences based on related content or synonymous terms.
        - Treat similar or related questions as synonymous (e.g., "applying for ISO" and "applying for ISO certification").
        - Your answers should be clear and concise, without any unnecessary formatting like newlines.
        - You should understand the content of the pdf and answer the questions correctly. Answers must be present in the pdf.
        - If the question is more general, behave like a chatbot (e.g., "Hi", "Hello", "How are you").
    </s>
    [INST] {input} 
            Context: {context}
            Answer: 
    [/INST]
""")

def process_ask_pdf(query):
    index_path = os.path.join(folder_path, "index.faiss")
    if not os.path.exists(index_path):
        return "Error: FAISS index file does not exist. Please upload PDF files first to create the index."
    
    vector_store = FAISS.load_local(folder_path, embedding, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_type="similarity_score_threshold", search_kwargs={"k": 5, "score_threshold": 0.1})  # Lowered the threshold
    document_chain = create_stuff_documents_chain(cached_llm, raw_prompt)
    chain = create_retrieval_chain(retriever, document_chain)
    result = chain.invoke({"input": query})
    return result["answer"]

def process_pdf(files):
    all_chunks = []
    file_names = []
    for file in files:
        file_name = file.name
        file_names.append(file_name)
        save_file = os.path.join(pdf_folder_path, file_name)
        with open(save_file, "wb") as f:
            f.write(file.getbuffer())
        loader = PDFPlumberLoader(save_file)
        docs = loader.load_and_split()
        chunks = text_splitter.split_documents(docs)
        all_chunks.extend(chunks)
    vector_store = FAISS.from_documents(documents=all_chunks, embedding=embedding)
    vector_store.save_local(folder_path)
    return {"status": "Successfully Uploaded", "filenames": file_names, "total_docs": len(all_chunks)}

def process_ask(question):
    index_path = os.path.join(folder_path, "index.faiss")
    if not os.path.exists(index_path):
        return "Error: FAISS index file does not exist. Please upload PDF files first to create the index."
    
    vector_store = FAISS.load_local(folder_path, embedding, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_type="similarity_score_threshold", search_kwargs={"k": 5, "score_threshold": 0.1})  # Lowered the threshold
    document_chain = create_stuff_documents_chain(cached_llm, raw_prompt)
    chain = create_retrieval_chain(retriever, document_chain)
    result = chain.invoke({"input": question})
    return result["answer"]

def main():
    st.title('Chatbot')
    option = st.sidebar.selectbox('Choose an option:', ('Home', 'Ask PDF', 'Upload PDF'))

    if option == 'Home':
        st.write('Welcome to the Chatbot')

    elif option == 'Ask PDF':
        if 'conversation' not in st.session_state:
            st.session_state.conversation = []

        if 'query' not in st.session_state:
            st.session_state.query = ""

        query = st.text_input('Enter your question for PDF:', value=st.session_state.query, key='query_input', on_change=lambda: st.session_state.update(query=st.session_state.query_input))

        if st.button('Ask') or query:
            response = process_ask_pdf(st.session_state.query)
            st.session_state.conversation.insert(0, {"question": st.session_state.query, "answer": response})
            st.session_state.query = ""  # Clear the input field
            st.query_params.clear()  # Refresh the page with empty query param

        if st.session_state.conversation:
            st.write("### Conversation")
            for chat in st.session_state.conversation:
                st.write(f"**Question:** {chat['question']}")
                st.write(f"**Answer:** {chat['answer']}")
                st.write("_____________________________________________________________________________________________________________________")

    elif option == 'Upload PDF':
        st.write('Upload your PDF file(s) here:')
        uploaded_files = st.file_uploader('Choose PDF files', type=['pdf'], accept_multiple_files=True)
        if st.button('Upload'):
            response = process_pdf(uploaded_files)
            st.write(response)

if __name__ == '__main__':
    main()
