import os
import re
import json
from dotenv import load_dotenv

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from PyPDF2 import PdfReader

import google.generativeai as genai
from groq import Groq


class Load_ventana_cuestionario(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Intentar cargar el .ui desde las rutas más comunes sin cambiar tu estructura
        loaded = False
        for ui_path in ("interfaces/ventana_cuestionario.ui", "ventana_cuestionario.ui"):
            try:
                uic.loadUi(ui_path, self)
                loaded = True
                break
            except Exception:
                continue
        if not loaded:
            # Si falla, lanza el error normal para que se vea claro en consola
            uic.loadUi("ventana_cuestionario.ui", self)

        # --- Estado interno ---
        self.pdf_path = None
        self.source_text = ""
        # Preguntas en texto para mostrar en los QLabel
        self.preguntas = []
        # Estructura detallada de opción múltiple
        self.preguntas_mc = []  # lista de dicts: {"pregunta": str, "opciones": [...], "correcta": "A"}
        # Respuestas correctas (letra A-D) para cada pregunta
        self.respuestas_correctas = []

        # --- Cargar claves desde .env ---
        load_dotenv()
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

        # --- Configurar modelos ---
        self._configurar_modelos()

        # --- Conexiones de botones ---
        self._conectar_signals()

        # Ajustar instrucciones para opción múltiple (solo texto, no cambia el .ui)
        if hasattr(self, "lblInstrucciones"):
            self.lblInstrucciones.setText(
                "Responde las 5 preguntas eligiendo una opción (A, B, C o D). "
                "Puedes escribir solo la letra o la letra con una breve explicación."
            )

    # ------------------------------------------------------------------
    # Configuración de modelos IA
    # ------------------------------------------------------------------
    def _configurar_modelos(self):
        self.gemini_model = None
        self.groq_client = None

        if self.google_api_key:
            try:
                genai.configure(api_key=self.google_api_key)
                # Puedes cambiar el modelo si quieres (gemini-1.5-flash, etc.)
                self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
            except Exception as e:
                print("Error configurando Gemini:", e)
                self.gemini_model = None

        if self.groq_api_key:
            try:
                self.groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                print("Error configurando Groq:", e)
                self.groq_client = None

    # ------------------------------------------------------------------
    # Conexión de señales
    # ------------------------------------------------------------------
    def _conectar_signals(self):
        # Navegación entre páginas
        self.btnIrCarga.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(0))
        self.btnIrEvaluacion.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(1))
        self.btnIrResultado.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))

        # PDF y preguntas
        self.btnSeleccionarPDF.clicked.connect(self.seleccionar_pdf)
        self.btnGenerarPreguntas.clicked.connect(self.generar_preguntas_desde_pdf)

        # Calificación
        self.btnCalificar.clicked.connect(self.calificar_respuestas)

    # ------------------------------------------------------------------
    # Manejo de PDF
    # ------------------------------------------------------------------
    def seleccionar_pdf(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar PDF",
            "",
            "Archivos PDF (*.pdf)"
        )
        if ruta:
            self.pdf_path = ruta
            self.lineEditPDF.setText(ruta)
            self.textEstado.clear()
            self.textEstado.append("PDF seleccionado correctamente.")

    def _leer_texto_pdf(self, ruta: str) -> str:
        """Lee el texto del PDF y limita el tamaño para el prompt."""
        try:
            reader = PdfReader(ruta)
            texto = ""
            for page in reader.pages:
                pag_text = page.extract_text() or ""
                texto += pag_text + "\n"
                # Limitar tamaño para no saturar el modelo
                if len(texto) > 16000:
                    break
            return texto
        except Exception as e:
            self.textEstado.append(f"Error leyendo el PDF: {e}")
            return ""

    # ------------------------------------------------------------------
    # Generar preguntas usando IA (opción múltiple)
    # ------------------------------------------------------------------
    def generar_preguntas_desde_pdf(self):
        if not self.pdf_path:
            QMessageBox.warning(self, "Sin PDF", "Primero selecciona un archivo PDF.")
            return

        self.textEstado.clear()
        self.textEstado.append("Leyendo PDF...")
        self.source_text = self._leer_texto_pdf(self.pdf_path)

        if not self.source_text.strip():
            self.textEstado.append("No se pudo extraer texto del PDF.")
            return

        self.textEstado.append(
            "Generando 5 preguntas de opción múltiple (4 opciones) con Gemini "
            "(si falla, se usará Groq)..."
        )

        preguntas_mc = self._generar_preguntas(self.source_text)

        if not preguntas_mc or len(preguntas_mc) != 5:
            self.textEstado.append("No se pudieron generar 5 preguntas de opción múltiple válidas.")
            return

        self.preguntas_mc = preguntas_mc
        self.preguntas = []
        self.respuestas_correctas = []

        # Convertir a texto para mostrar en los QLabel y guardar correctas
        for item in self.preguntas_mc:
            pregunta = item.get("pregunta", "").strip()
            opciones = item.get("opciones", [])
            correcta = item.get("correcta", "").strip().upper()[:1]

            # Asegurarnos de que haya 4 opciones
            while len(opciones) < 4:
                opciones.append("Opción faltante")
            opciones = opciones[:4]

            texto_label = (
                f"{pregunta}\n"
                f"A) {opciones[0]}\n"
                f"B) {opciones[1]}\n"
                f"C) {opciones[2]}\n"
                f"D) {opciones[3]}"
            )

            self.preguntas.append(texto_label)
            self.respuestas_correctas.append(correcta if correcta in ("A", "B", "C", "D") else "")

        self._mostrar_preguntas_en_ui()
        self.textEstado.append("Preguntas de opción múltiple generadas correctamente.")
        self.stackedWidget.setCurrentIndex(1)  # Pasar a pestaña de evaluación

    def _generar_preguntas(self, texto: str):
        texto_corto = texto[:6000]  # recorte para prompt

        prompt = f"""
Eres un profesor de Inteligencia Artificial.

A partir del siguiente contenido, genera EXACTAMENTE 5 preguntas de evaluación
de OPCIÓN MÚLTIPLE en español, de nivel intermedio-avanzado (tipo universitario).

Cada pregunta debe tener:
- Un enunciado claro sobre el tema.
- EXACTAMENTE 4 opciones de respuesta (A, B, C, D).
- Indicar cuál opción es la correcta.

DEVUELVE la salida EXCLUSIVAMENTE como un JSON VÁLIDO con esta estructura:

[
  {{
    "pregunta": "texto de la pregunta 1",
    "opciones": ["opción A", "opción B", "opción C", "opción D"],
    "correcta": "A"
  }},
  {{
    "pregunta": "texto de la pregunta 2",
    "opciones": ["opción A", "opción B", "opción C", "opción D"],
    "correcta": "C"
  }},
  ...
]

Requisitos:
- Deben ser exactamente 5 elementos en la lista.
- No agregues texto antes ni después del JSON.
- No uses comentarios ni explicaciones.

TEXTO BASE:
\"\"\"{texto_corto}\"\"\"
"""

        # 1) Intentar con Gemini
        preguntas = self._generar_preguntas_con_gemini(prompt)
        if preguntas and len(preguntas) == 5:
            self.textEstado.append("Preguntas generadas con Gemini.")
            return preguntas

        # 2) Fallback con Groq
        preguntas = self._generar_preguntas_con_groq(prompt)
        if preguntas and len(preguntas) == 5:
            self.textEstado.append("Preguntas generadas con Groq.")
            return preguntas

        return None

    def _parsear_preguntas_mc_de_texto(self, texto: str):
        """
        Intenta interpretar el texto devuelto por el modelo como JSON
        con la estructura de opción múltiple.
        """
        texto = texto.strip()
        # En algunos casos, el modelo puede envolver el JSON en ```json ... ```
        texto = re.sub(r"^```json", "", texto, flags=re.IGNORECASE).strip()
        texto = re.sub(r"```$", "", texto).strip()

        try:
            data = json.loads(texto)
        except Exception as e:
            self.textEstado.append(f"No se pudo parsear el JSON de preguntas: {e}")
            return None

        if not isinstance(data, list):
            self.textEstado.append("El JSON de preguntas no es una lista.")
            return None

        preguntas_validas = []
        for item in data:
            if not isinstance(item, dict):
                continue
            pregunta = item.get("pregunta")
            opciones = item.get("opciones")
            correcta = item.get("correcta")

            if not pregunta or not isinstance(opciones, list) or len(opciones) < 2:
                continue
            if not isinstance(correcta, str) or correcta.upper()[:1] not in ("A", "B", "C", "D"):
                # Aún si no viene la correcta, podemos seguir, pero marcamos cadena vacía
                correcta = ""

            preguntas_validas.append(
                {
                    "pregunta": str(pregunta),
                    "opciones": [str(o) for o in opciones],
                    "correcta": correcta.upper()[:1],
                }
            )

        if len(preguntas_validas) < 5:
            self.textEstado.append(
                f"Solo se obtuvieron {len(preguntas_validas)} preguntas válidas en el JSON."
            )
            return None

        # Nos quedamos con las primeras 5
        return preguntas_validas[:5]

    def _generar_preguntas_con_gemini(self, prompt: str):
        if not self.gemini_model:
            return None
        try:
            resp = self.gemini_model.generate_content(prompt)
            texto_resp = (resp.text or "").strip()
            if not texto_resp:
                return None
            return self._parsear_preguntas_mc_de_texto(texto_resp)
        except Exception as e:
            self.textEstado.append(f"Error con Gemini: {e}")
            return None

    def _generar_preguntas_con_groq(self, prompt: str):
        if not self.groq_client:
            return None
        try:
            resp = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un profesor de IA que genera preguntas de examen de opción múltiple en español.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            texto_resp = resp.choices[0].message.content.strip()
            if not texto_resp:
                return None
            return self._parsear_preguntas_mc_de_texto(texto_resp)
        except Exception as e:
            self.textEstado.append(f"Error con Groq: {e}")
            return None

    def _mostrar_preguntas_en_ui(self):
        labels = [
            self.lblPregunta1,
            self.lblPregunta2,
            self.lblPregunta3,
            self.lblPregunta4,
            self.lblPregunta5,
        ]
        for i in range(5):
            labels[i].setText(self.preguntas[i])

    # ------------------------------------------------------------------
    # Calificación con IA (usando opción múltiple)
    # ------------------------------------------------------------------
    def calificar_respuestas(self):
        if not self.preguntas or len(self.preguntas) != 5:
            QMessageBox.warning(self, "Sin preguntas", "Primero genera las preguntas con IA.")
            return

        respuestas = [
            self.txtRespuesta1.toPlainText().strip(),
            self.txtRespuesta2.toPlainText().strip(),
            self.txtRespuesta3.toPlainText().strip(),
            self.txtRespuesta4.toPlainText().strip(),
            self.txtRespuesta5.toPlainText().strip(),
        ]

        if not any(respuestas):
            QMessageBox.warning(
                self, "Sin respuestas", "Escribe al menos alguna respuesta antes de calificar."
            )
            return

        # 🔹 Calculamos el puntaje SOLO en función de cuántas letras correctas coincidieron
        score = self._calcular_puntaje(respuestas)

        texto_corto = (self.source_text or "")[:8000]
        prompt = self._construir_prompt_calificacion(texto_corto, self.preguntas, respuestas)

        self.textEstado.append("Calificando respuestas con Gemini (si falla, Groq)...")

        # 1) Intentar con Gemini
        feedback = self._calificar_con_gemini(prompt)
        origen = "Gemini"

        if not feedback:
            # 2) Fallback Groq
            feedback = self._calificar_con_groq(prompt)
            origen = "Groq"

        if not feedback:
            QMessageBox.warning(self, "Error", "No se pudo obtener calificación de la IA.")
            return

        self.textEstado.append(f"Calificación generada con {origen}.")
        self.textFeedback.setPlainText(feedback)

        # 🔹 Usamos SIEMPRE nuestro score (0,20,40,60,80,100)
        self.progressPuntaje.setValue(score)
        self.lblPuntaje.setText(f"Puntaje: {score}/100")

        # Ir a pestaña de resultados
        self.stackedWidget.setCurrentIndex(2)

    def _calcular_puntaje(self, respuestas):
        """
        Calcula el puntaje con base en respuestas_correctas y las respuestas del estudiante.
        - 0 correctas -> 0
        - 1 correcta  -> 20
        - ...
        - 5 correctas -> 100
        """
        correctas = 0
        num_preguntas = min(5, len(respuestas), len(self.respuestas_correctas))

        for i in range(num_preguntas):
            correcta = (self.respuestas_correctas[i] or "").strip().upper()[:1]
            if correcta not in ("A", "B", "C", "D"):
                continue

            resp_texto = respuestas[i].strip().upper()
            # Buscar la primera letra A-D que aparezca en la respuesta
            m = re.search(r"[ABCD]", resp_texto)
            if not m:
                continue

            respuesta_letra = m.group(0)
            if respuesta_letra == correcta:
                correctas += 1

        # Cada pregunta vale 20 puntos
        return correctas * 20

    def _construir_prompt_calificacion(self, texto_tema, preguntas, respuestas):
        """
        Construye el prompt para que la IA dé retroalimentación de un cuestionario
        de opción múltiple. El puntaje numérico lo calculamos nosotros aparte.
        """
        bloque_pyr = []
        for i in range(5):
            pregunta_texto = preguntas[i]
            resp_estudiante = respuestas[i] or "(sin respuesta)"
            correcta = ""
            if i < len(self.respuestas_correctas):
                correcta = self.respuestas_correctas[i] or ""
            bloque_pyr.append(
                f"Pregunta {i+1}:\n"
                f"{pregunta_texto}\n"
                f"Opción correcta (según el examen): {correcta if correcta else '(no especificada)'}\n"
                f"Respuesta del estudiante: {resp_estudiante}"
            )
        bloque_pyr = "\n\n".join(bloque_pyr)

        prompt = f"""
Eres un profesor universitario de Inteligencia Artificial.

Tienes el siguiente TEXTO BASE (resumen del contenido del PDF):

\"\"\"{texto_tema}\"\"\"

Debes evaluar las siguientes respuestas del estudiante a 5 preguntas de OPCIÓN MÚLTIPLE.
Cada pregunta incluye sus 4 opciones (A, B, C, D). Para cada una se indica, cuando está disponible,
cuál es la opción correcta según el examen, y también la respuesta del estudiante
(que será una letra A, B, C o D, y en algunos casos una pequeña explicación).

Información de las preguntas y respuestas:

{bloque_pyr}

Instrucciones de evaluación:
- Indica para cada pregunta si la respuesta del estudiante es correcta o incorrecta y explica brevemente por qué.
- Explica brevemente qué tan bien comprendió el tema en general.
- Da una conclusión final.

IMPORTANTE:
- NO des un puntaje numérico global (no escribas 'Puntaje: X/100').
- Solo ofrece retroalimentación cualitativa por pregunta y una breve conclusión.

No incluyas nada fuera de este formato.
"""
        return prompt

    def _calificar_con_gemini(self, prompt: str):
        if not self.gemini_model:
            return None
        try:
            resp = self.gemini_model.generate_content(prompt)
            return (resp.text or "").strip()
        except Exception as e:
            self.textEstado.append(f"Error al calificar con Gemini: {e}")
            return None

    def _calificar_con_groq(self, prompt: str):
        if not self.groq_client:
            return None
        try:
            resp = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un profesor de IA que evalúa respuestas de estudiantes en español.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            self.textEstado.append(f"Error al calificar con Groq: {e}")
            return None

    def _extraer_puntaje(self, texto: str) -> int:
        """
        (Ya no se usa, pero lo dejo por si quieres reutilizarlo en el futuro).
        Busca algo como 'Puntaje: 85/100' o 'Puntaje 85' o '85/100'.
        Si no encuentra nada, devuelve 0.
        """
        m = re.search(r"(\d{1,3})\s*/\s*100", texto)
        if not m:
            m = re.search(r"[Pp]untaje[^0-9]*(\d{1,3})", texto)
        if not m:
            m = re.search(r"\b(\d{1,3})\b", texto)

        if not m:
            return 0

        try:
            score = int(m.group(1))
            if score < 0:
                score = 0
            if score > 100:
                score = 100
            return score
        except ValueError:
            return 0


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ventana = Load_ventana_cuestionario()
    ventana.show()
    sys.exit(app.exec_())
