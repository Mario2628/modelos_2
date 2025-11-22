# 8_memoria.py
# RAG con PDF y FAISS usando embeddings numéricos sencillos,
# sin sentence-transformers / torch ni embeddings de Gemini.
# Compatible con la GUI:
#   - inicializar_indice(pdf_path)
#   - preguntar(pregunta)

import os
from typing import List

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.embeddings import Embeddings

# -------------------------------------------------------------------
# 1. Configuración de Gemini (solo para el LLM de generación de texto)
# -------------------------------------------------------------------
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)

# -------------------------------------------------------------------
# 2. Embeddings súper simples (3 números) -> NO usan torch ni APIs
# -------------------------------------------------------------------
# Vector = [n_palabras, longitud_media_palabra, n_caracteres]

class SimpleEmbeddings(Embeddings):
    def _embed_one(self, text: str) -> List[float]:
        if text is None:
            text = ""
        text = str(text)
        words = [w for w in text.split() if w.strip()]
        n_words = float(len(words))
        n_chars = float(len(text))
        avg_len = float(sum(len(w) for w in words) / len(words)) if words else 0.0
        # Devolvemos un vector de 3 dimensiones
        return [n_words, avg_len, n_chars]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)

    def __call__(self, text: str) -> List[float]:
        """
        FAISS a veces trata el 'embedding' como una función.
        Hacemos la clase callable para que, si la llama así,
        delegue en embed_query().
        """
        return self.embed_query(text)


embeddings = SimpleEmbeddings()

# -------------------------------------------------------------------
# 3. Prompt del RAG (igual lógica que el original)
# -------------------------------------------------------------------
template = """
Usa el siguiente contexto para responder la pregunta del usuario.
Si no hay suficiente información, responde: "No tengo información suficiente en el documento."

Contexto:
{context}

Pregunta:
{question}
"""
prompt = ChatPromptTemplate.from_template(template)

# -------------------------------------------------------------------
# 4. Estado global (último índice cargado)
# -------------------------------------------------------------------
_rag_chain = None
_pdf_actual = None


def _construir_rag_chain(pdf_path: str) -> str:
    """
    Carga el PDF, genera los fragmentos, construye FAISS y prepara la cadena RAG.
    Devuelve un texto de resumen para mostrar en la interfaz.
    """
    global _rag_chain, _pdf_actual

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

    # 1. Cargar PDF
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    num_paginas = len(pages)

    # 2. Dividir en chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = splitter.split_documents(pages)
    num_docs = len(docs)

    # 3. Crear vectorstore FAISS con nuestros SimpleEmbeddings
    vectorstore = FAISS.from_documents(docs, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # 4. Construir la cadena RAG
    _rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
    )
    _pdf_actual = pdf_path

    return (
        f"Documento cargado correctamente:\n"
        f"  Archivo: {os.path.basename(pdf_path)}\n"
        f"  Páginas: {num_paginas}\n"
        f"  Fragmentos: {num_docs}"
    )


# -------------------------------------------------------------------
# 5. Funciones que usa la interfaz
# -------------------------------------------------------------------

def inicializar_indice(pdf_path: str) -> str:
    """
    La GUI llama a esta función cuando pulsas 'Seleccionar PDF...'.
    """
    return _construir_rag_chain(pdf_path)


# Alias opcional por si lo quieres usar desde consola
def cargar_pdf(pdf_path: str) -> str:
    return _construir_rag_chain(pdf_path)


def preguntar(pregunta: str) -> str:
    """
    La GUI llama a esta función al pulsar 'Ejecutar' / 'Preguntar'.

    - Si antes ya se llamó a inicializar_indice(), usa ese PDF.
    - Si no, intenta usar documentos/fuente.pdf como valor por defecto.
    """
    global _rag_chain, _pdf_actual

    if _rag_chain is None:
        pdf_defecto = os.path.join("documentos", "fuente.pdf")
        if not os.path.isfile(pdf_defecto):
            raise RuntimeError(
                "No hay ningún índice cargado.\n"
                "Primero selecciona un PDF en la interfaz, "
                "o crea el archivo 'documentos/fuente.pdf'."
            )
        _construir_rag_chain(pdf_defecto)

    respuesta = _rag_chain.invoke(pregunta)
    contenido = getattr(respuesta, "content", str(respuesta))
    return contenido.strip()


# -------------------------------------------------------------------
# 6. Prueba rápida desde consola (opcional)
# -------------------------------------------------------------------
if __name__ == "__main__":
    ruta = os.path.join("documentos", "fuente.pdf")
    print(inicializar_indice(ruta))
    print()
    print("Pregunta: ¿De qué trata el documento?")
    print("Respuesta:", preguntar("¿De qué trata el documento?"))
