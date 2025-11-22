from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema.output_parser import StrOutputParser
from dotenv import load_dotenv
import os
import logging

# Silenciar logs
os.environ["GRPC_VERBOSITY"] = "NONE"
os.environ["GRPC_CPP_VERBOSITY"] = "NONE"
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("grpc").setLevel(logging.ERROR)

# Cargar la API Key
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Modelo
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

# Prompt
prompt = PromptTemplate.from_template(
    "Resume el siguiente texto en una oración clara y concisa:\n\n{input}"
)

# Parser para obtener texto limpio
parser = StrOutputParser()

# Encadenamiento moderno (RunnableSequence)
chain = prompt | llm | parser


def run_chain(texto: str) -> str:
    """
    Devuelve un resumen en una sola oración del texto dado.
    """
    return chain.invoke(texto)


if __name__ == "__main__":
    demo = "La inteligencia artificial está transformando la educación a nivel global..."
    print(run_chain(demo))
