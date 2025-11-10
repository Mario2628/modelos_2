#pip uninstall -y langchain langchain-core langchain-community langchain-google-genai
#pip cache purge
#pip install langchain==0.2.17 langchain-core==0.2.43 langchain-community==0.2.17 langchain-google-genai==1.0.7 faiss-cpu pypdf python-dotenv
#pip install sentence-transformers

import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# --- Cargar API Key de Gemini (solo para el modelo generativo) ---
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# --- 1. Cargar documento ---
pdf_path = "documentos/fuente.pdf"
loader = PyPDFLoader(pdf_path)
pages = loader.load()
print(f"Documento cargado con {len(pages)} páginas")

# --- 2. Dividir texto ---
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
docs = splitter.split_documents(pages)
print(f"Texto dividido en {len(docs)} fragmentos")

# --- 3. Crear embeddings locales ---
print("Generando embeddings locales con HuggingFace (esto puede tardar unos segundos la primera vez)...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Crear o cargar índice FAISS (para no recalcular embeddings cada vez)
INDEX_PATH = "faiss_local_index"

if os.path.exists(INDEX_PATH):
    print("Cargando índice FAISS existente...")
    vectorstore = FAISS.load_local(INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
else:
    print("Creando índice FAISS nuevo...")
    vectorstore = FAISS.from_documents(docs, embedding=embeddings)
    vectorstore.save_local(INDEX_PATH)

retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# --- 4. Modelo LLM (Gemini solo para generación, no embeddings) ---
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)

# --- 5. Prompt ---
template = """
Usa el siguiente contexto para responder la pregunta del usuario.
Si no hay suficiente información, responde: "No tengo información suficiente en el documento."

Contexto:
{context}

Pregunta:
{question}
"""
prompt = ChatPromptTemplate.from_template(template)

# --- 6. Construir el RAG Chain moderno ---
rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
)

# --- 7. Función para preguntar ---
def preguntar(pregunta: str):
    print(f"\n Pregunta: {pregunta}")
    respuesta = rag_chain.invoke(pregunta)
    print("Respuesta:", respuesta.content.strip())

# --- Ejemplo de uso ---
if __name__ == "__main__":
    preguntar("¿De qué trata el documento?")
    preguntar("¿Qué conclusiones se mencionan?")
