from groq import Groq
from dotenv import load_dotenv
import os

class ModeloHistorial:
    def __init__(self):
        # Cargar la API key desde .env una sola vez
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("❌ No se encontró GROQ_API_KEY en el archivo .env")

        # Crear el cliente con la API key segura
        self.cliente = Groq(api_key=api_key)

        # El historial se guarda como atributo de la clase
        self.historial = [{"role": "system", "content": "Eres un asistente útil y amigable"}]

    def modeloHistorial(self):
        print("Chatbot iniciado. Escribe 'salir' para terminar la conversación.\n")

        while True:
            pregunta = input("Tú: ")

            if pregunta.lower() == 'salir':
                print("Chatbot terminado.")
                break

            # Agregar la pregunta del usuario al historial
            self.historial.append({"role": "user", "content": pregunta})

            # Llamada al API de Groq
            respuesta = self.cliente.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self.historial
            )

            # Obtener la respuesta del chatbot
            respuesta_chatbot = respuesta.choices[0].message.content
            print("Chatbot: " + respuesta_chatbot + "\n")

            # Agregar la respuesta al historial
            self.historial.append({"role": "assistant", "content": respuesta_chatbot})
