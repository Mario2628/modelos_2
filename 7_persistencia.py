import os, json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

# Archivo donde se guardará la memoria
MEMORY_FILE = "memoria.json"


# --- Funciones de persistencia ---
def guardar_memoria():
    """Guarda el historial en JSON serializando solo texto."""
    data = memory.load_memory_variables({})
    # Convertir los mensajes en texto plano
    history_text = []
    for msg in data.get("history", []):
        if hasattr(msg, "type") and hasattr(msg, "content"):
            history_text.append({"type": msg.type, "content": msg.content})
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"history": history_text}, f, ensure_ascii=False, indent=2)


def cargar_memoria():
    """Carga la memoria desde el archivo JSON si existe."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for msg in data.get("history", []):
                if msg["type"] == "human":
                    memory.chat_memory.add_user_message(msg["content"])
                elif msg["type"] == "ai":
                    memory.chat_memory.add_ai_message(msg["content"])


# --- Ejecutar con memoria persistente ---
def ejecutar_con_memoria(texto: str) -> str:
    """Ejecuta el modelo conservando memoria entre sesiones."""
    history = memory.load_memory_variables({}).get("history", [])
    chain = prompt | llm
    response = chain.invoke({"history": history, "input": texto})

    # Guardar el nuevo turno
    memory.save_context({"input": texto}, {"output": response.content})
    guardar_memoria()  # 🔄 Guarda después de cada interacción

    return response.content.strip()


# --- Configuración ---
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# Modelo
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

# Prompt con memoria
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente amable que recuerda toda la conversación anterior."),
    ("placeholder", "{history}"),
    ("human", "{input}")
])

# Crear memoria
memory = ConversationBufferMemory(return_messages=True)

# Cargar memoria previa (si existe)
cargar_memoria()


def resetear_memoria():
    """
    Borra la memoria en RAM y elimina el archivo JSON de historial.
    """
    global memory
    memory = ConversationBufferMemory(return_messages=True)
    try:
        if os.path.exists(MEMORY_FILE):
            os.remove(MEMORY_FILE)
    except OSError:
        # Si no se puede borrar, simplemente ignoramos el error
        pass


if __name__ == "__main__":
    print(ejecutar_con_memoria("¿Recuerdas cómo me llamo?"))
    print(ejecutar_con_memoria("¿Qué hablamos antes?"))
    print(ejecutar_con_memoria("¿Puedes resumir nuestra conversación?"))
