from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

class ModeloHistorial:
    def __init__(self):
        # API key desde .env
        self.cliente = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
        self.model = "llama-3.1-8b-instant"

        # Máximo de TURNOS (pares user/assistant) a conservar -> 4
        self.MAX_HISTORIAL_LENGTH = 4

    def modelohistorial(self, historial=None):
        """
        Usa una lista 'historial' mutable que nos pasa la UI.
        Al finalizar cada turno recorta a los últimos 4 pares (8 msgs) + system.
        """
        if historial is None:
            historial = [{"role": "system", "content": "Eres un asistente útil y amable."}]

        print("Chatbot iniciado. Escribe 'Salir' para terminar la conversación.\n")

        while True:
            pregunta = input("Tu: ")

            if pregunta.lower() == 'salir':
                print("Chatbot terminado.")
                break

            # Añadir mensaje de usuario
            historial.append({"role": "user", "content": pregunta})

            try:
                # Llamada a Groq
                respuesta = self.cliente.chat.completions.create(
                    model=self.model,
                    messages=historial
                )
                respuesta_chatbot = respuesta.choices[0].message.content

                print("Chatbot: " + respuesta_chatbot + "\n")

                # Añadir mensaje del asistente
                historial.append({"role": "assistant", "content": respuesta_chatbot})

                # ---- Recorte a 4 pares (user/assistant) + system ----
                conv = [m for m in historial if m.get("role") in ("user", "assistant")]
                if len(conv) > self.MAX_HISTORIAL_LENGTH * 2:
                    conv = conv[-self.MAX_HISTORIAL_LENGTH * 2:]
                    base = [m for m in historial if m.get("role") == "system"]
                    historial[:] = base + conv

            except Exception as e:
                print(f"Ocurrió un error al comunicarse con el API de Groq: {e}")
                # Deshacer el último append del usuario si hubo fallo
                if historial and historial[-1].get("role") == "user":
                    historial.pop()
