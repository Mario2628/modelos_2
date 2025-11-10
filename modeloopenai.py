from groq import Groq
from dotenv import load_dotenv
import os

# Cargar variables de entorno (GROQ_API_KEY)
load_dotenv()

class ModeloOpenAI:
    def __init__(self):
        # El cliente puede construirse una vez o en cada llamada; aquí lo creamos al usarlo
        pass

    def modeloSimple(self, texto: str) -> str:
        """
        Recibe 'texto' desde la interfaz gráfica, llama al modelo Groq
        y devuelve la respuesta como string. También hace print() por compatibilidad.
        """
        if not isinstance(texto, str) or not texto.strip():
            resp_text = "⚠️ Debes proporcionar un texto para el prompt."
            print(resp_text)
            return resp_text

        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            resp_text = "⚠️ Falta GROQ_API_KEY en .env"
            print(resp_text)
            return resp_text

        try:
            cliente = Groq(api_key=api_key)
            respuesta = cliente.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": texto}],
            )
            contenido = respuesta.choices[0].message.content
            print(contenido)  # compatibilidad
            return contenido
        except Exception as e:
            err = f"❌ Error al llamar Groq: {e}"
            print(err)
            return err
