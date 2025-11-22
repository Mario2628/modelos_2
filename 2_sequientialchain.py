from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import logging

# Silenciar logs
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("grpc").setLevel(logging.ERROR)

# Cargar API Key
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Modelo
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

# Prompts
prompt_resumen = PromptTemplate.from_template("Resume el siguiente texto: {input}")
prompt_traduccion_en = PromptTemplate.from_template("Tradúcelo al inglés: {input}")

# Encadenar los pasos usando el nuevo estilo RunnableSequence
chain_resumen = prompt_resumen | llm
chain_traduccion_en = prompt_traduccion_en | llm

# Crear la cadena secuencial simple (resumen → traducción al inglés)
chain_final = chain_resumen | chain_traduccion_en


def resumir(texto: str) -> str:
    """
    Devuelve un resumen del texto en español.
    """
    resultado = chain_resumen.invoke(texto)
    contenido = getattr(resultado, "content", str(resultado))
    return contenido.strip()


def traducir(texto: str, idioma: str) -> str:
    """
    Traduce el texto dado al idioma indicado.
    (Este se usará desde la interfaz gráfica con el combo de idiomas.)
    """
    prompt_multi = PromptTemplate.from_template(
        "Traduce el siguiente texto al {idioma}:\n\n{texto}"
    )
    chain_multi = prompt_multi | llm
    resultado = chain_multi.invoke({"idioma": idioma, "texto": texto})
    contenido = getattr(resultado, "content", str(resultado))
    return contenido.strip()


def run_chain(texto: str) -> str:
    """
    Flujo original del ejercicio:
    resume el texto y lo traduce al inglés.
    """
    resultado = chain_final.invoke(texto)
    contenido = getattr(resultado, "content", str(resultado))
    return contenido.strip()


if __name__ == "__main__":
    demo = "La inteligencia artificial está transformando la educación..."
    print(run_chain(demo))
