from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import logging

# Silenciar logs ruidosos (opcional)
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("grpc").setLevel(logging.ERROR)

# Cargar .env
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

# === Novedad: leer desde la GUI el tema y el template ===
tema_usuario = os.getenv("PROMPT_TEMA", "").strip()
plantilla = os.getenv("PROMPT_TEMPLATE", "").strip()

# Defaults por si la GUI no envía algo
if not tema_usuario:
    tema_usuario = "el aprendizaje automático"

if not plantilla:
    plantilla = "Explícale a un estudiante universitario el tema {tema}."

# Seguridad: si el template no contiene {tema}, usamos el default (para evitar fallo)
if "{tema}" not in plantilla:
    plantilla = "Explícale a un estudiante universitario el tema {tema}."

# LLM (Gemini)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7
)

# PromptTemplate con el texto que vino de la GUI
prompt = PromptTemplate(
    input_variables=["tema"],
    template=plantilla
)

# Cadena (estilo Runnable)
chain = prompt | llm

# Ejecutar
respuesta = chain.invoke({"tema": tema_usuario})
print(respuesta.content)
