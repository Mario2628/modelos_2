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

# Prompts (usar {input}, no {texto})
prompt_resumen = PromptTemplate.from_template("Resume el siguiente texto: {input}")
prompt_traduccion = PromptTemplate.from_template("Tradúcelo al inglés: {input}")

# Encadenamiento moderno con Runnables (sin LLMChain)
chain = prompt_resumen | llm | prompt_traduccion | llm

# Ejecutar pasando directamente texto (no diccionario)
resultado = chain.invoke("La inteligencia artificial está transformando la educación...")

# Obtener texto limpio
texto_final = resultado.content if hasattr(resultado, "content") else str(resultado)

print(texto_final.strip())