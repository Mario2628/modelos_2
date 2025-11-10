# ======================================================
# load_ventana_modelos_basicos.py
# ------------------------------------------------------
# Este archivo SOLO conecta la interfaz con tus 3 programas:
#   1) modeloopenai.py           -> Pestaña "Prompt"
#   2) modelo_historial_groq.py  -> Pestaña "Memoria"
#   3) modelohistorial_2.py      -> Pestaña "Chat (límite 4)"
# No contiene lógica de modelos; únicamente:
#   - Carga la UI
#   - Conecta botones
#   - Pasa el texto de entrada a tus .py
#   - Captura 'print()' de tus .py (Memoria/Chat) y lo muestra en QTextEdit
#   - Simula 'input()' (usuario y luego 'salir') para Memoria/Chat
# ======================================================

from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtCore import QPropertyAnimation

# Utilidades para capturar salida e inyectar input() a TUS .py
import io, builtins
from contextlib import redirect_stdout

# ======= IMPORTS DE TUS TRES PROGRAMAS (.py) =======
# 1) Prompt: usa modeloopenai.py (Groq)  -> pestaña "Prompt"
from modeloopenai import ModeloOpenAI

# 2) Memoria (historial sin límite): usa modelo_historial_groq.py -> pestaña "Memoria"
from modelo_historial_groq import ModeloHistorial as ModeloHistorialMem

# 3) Chat limitado a 4 pares: usa modelohistorial_2.py -> pestaña "Chat"
from modelohistorial_2 import ModeloHistorial as ModeloHistorialTop5


class Load_ventana_modelos_basicos(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        
        # --------------------------------------------
        # Cargar la INTERFAZ tal cual tu .ui
        # --------------------------------------------
        uic.loadUi("interfaces/ventana_modelos_basicos.ui", self)

        # --------------------------------------------
        # Conectar cada pestaña con su .py correspondiente
        # --------------------------------------------
        self._wire_prompt()   # -> modeloopenai.py (Prompt)
        self._wire_memoria()  # -> modelo_historial_groq.py (Memoria)
        self._wire_chat()     # -> modelohistorial_2.py (Chat límite 4)

        # === A partir de aquí es la misma estructura de tu load base ===
        # eliminar barra y de titulo - opacidad
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setWindowOpacity(1)

        # Cerrar y mover ventana
        self.boton_cerrar.clicked.connect(lambda: self.close())
        self.frame_superior.mouseMoveEvent = self.mover_ventana

        # Menú lateral
        self.boton_menu.clicked.connect(self.mover_menu)

        # Botones para cambiar de página
        self.boton_prompt.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.page_prompt))
        self.boton_memoria.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.page_memoria))
        self.boton_chat.clicked.connect(lambda: self.stackedWidget.setCurrentWidget(self.page_chat))
       
    # ---------------- Ventana / Menú (igual que tu base) ----------------
    def mousePressEvent(self, event):
        self.clickPosition = event.globalPos()

    def mover_ventana(self, event):
        if not self.isMaximized():			
            if event.buttons() == QtCore.Qt.LeftButton:
                self.move(self.pos() + event.globalPos() - self.clickPosition)
                self.clickPosition = event.globalPos()
                event.accept()
        if event.globalPos().y() <= 20:
            self.showMaximized()
        else:
            self.showNormal()
    
    def mover_menu(self):
        width = self.frame_lateral.width()
        normal = 0
        if width == 0:
            extender = 200
            self.boton_menu.setText("Menú")
        else:
            extender = normal
            self.boton_menu.setText("")
                
        self.animacion = QtCore.QPropertyAnimation(self.frame_lateral, b'minimumWidth')
        self.animacion.setDuration(300)
        self.animacion.setStartValue(width)
        self.animacion.setEndValue(extender)
        self.animacion.setEasingCurve(QtCore.QEasingCurve.InOutQuart)
        self.animacion.start()
            
        self.animacionb = QPropertyAnimation(self.boton_menu, b'minimumWidth')
        self.animacionb.setStartValue(width)
        self.animacionb.setEndValue(extender)
        self.animacionb.setEasingCurve(QtCore.QEasingCurve.InOutQuart)
        self.animacionb.start()

    # ======================================================
    #                 PESTAÑA 1: PROMPT
    #   -> llama a TU archivo  modeloopenai.py (ModeloOpenAI)
    #   -> método: modeloSimple(texto_desde_UI)
    #   -> imprime en: output_response
    # ======================================================
    def _wire_prompt(self):
        self.input_prompt  = self.findChild(QtWidgets.QLineEdit,  "input_prompt")
        self.boton_enviar  = self.findChild(QtWidgets.QPushButton,"boton_enviar")
        self.output_resp   = self.findChild(QtWidgets.QTextEdit,  "output_response")

        # Instancia de tu clase del archivo .py (no se modifica)
        self.modelo_prompt = ModeloOpenAI()

        if self.boton_enviar:
            self.boton_enviar.clicked.connect(self._on_prompt_click)

    def _on_prompt_click(self):
        """
        Llama a TU modelo del archivo modeloopenai.py, pasándole el texto
        que el usuario escribió en la interfaz. Muestra el resultado.
        (modeloopenai.ModeloOpenAI.modeloSimple(texto) debe devolver str)
        """
        texto = (self.input_prompt.text() if self.input_prompt else "").strip()
        if not texto:
            self._set_text(self.output_resp, "⚠️ Escribe el prompt.")
            return

        try:
            salida = self.modelo_prompt.modeloSimple(texto)
            self._set_text(self.output_resp, salida)
        except Exception as e:
            self._set_text(self.output_resp, f"❌ Error: {e}")

    # ======================================================
    #                 PESTAÑA 2: MEMORIA
    #   -> llama a TU archivo  modelo_historial_groq.py (ModeloHistorial)
    #   -> método: modeloHistorial()
    #   -> le pasamos UNA entrada de usuario y luego 'salir'
    #   -> muestra el historial en: output_response_2
    # ======================================================
    def _wire_memoria(self):
        self.input_prompt_2    = self.findChild(QtWidgets.QLineEdit,  "input_prompt_2")
        self.boton_enviar_2    = self.findChild(QtWidgets.QPushButton,"boton_enviar_2")
        self.output_response_2 = self.findChild(QtWidgets.QTextEdit,  "output_response_2")

        # Instancia de tu clase del archivo .py (sin modificar)
        self.modelo_historial_full = ModeloHistorialMem()

        if self.boton_enviar_2:
            self.boton_enviar_2.clicked.connect(self._on_memoria_click)

    def _on_memoria_click(self):
        """
        Ejecuta TU método modeloHistorial() que usa input()/print().
        Simulamos input() con:
           - lo que el usuario escribió en input_prompt_2
           - 'salir' para cerrar el loop
        y capturamos lo que imprime para renderizarlo en la interfaz.
        """
        entrada = (self.input_prompt_2.text() if self.input_prompt_2 else "").strip()
        if not entrada:
            self._set_text(self.output_response_2, "⚠️ Escribe un mensaje.")
            return

        respuestas = [entrada, "salir"]

        def fake_input(prompt=""):
            return respuestas.pop(0) if respuestas else "salir"

        buf = io.StringIO()
        real_input = builtins.input
        try:
            builtins.input = fake_input
            with redirect_stdout(buf):
                # Llama a TU método del .py (no lo modificamos)
                self.modelo_historial_full.modeloHistorial()
        except Exception as e:
            self._set_text(self.output_response_2, f"❌ Error: {e}")
            return
        finally:
            builtins.input = real_input

        # Muestra el historial que TU clase lleva internamente (self.historial)
        texto_hist = self._historial_to_text(self.modelo_historial_full.historial)
        self._set_text(self.output_response_2, texto_hist)

        # Limpia el input de la pestaña Memoria
        if self.input_prompt_2:
            self.input_prompt_2.clear()

    # ======================================================
    #                 PESTAÑA 3: CHAT (límite 4)
    #   -> llama a TU archivo  modelohistorial_2.py (ModeloHistorial)
    #   -> método: modelohistorial(historial=list_mutable)
    #   -> mantiene un historial propio en la UI (self.historial_top5 -> ahora top4)
    #   -> muestra en: output_response_3
    # ======================================================
    def _wire_chat(self):
        self.input_prompt_3    = self.findChild(QtWidgets.QLineEdit,  "input_prompt_3")
        self.boton_enviar_3    = self.findChild(QtWidgets.QPushButton,"boton_enviar_3")
        self.output_response_3 = self.findChild(QtWidgets.QTextEdit,  "output_response_3")

        # Instancia del archivo NUEVO (límite 4 turnos)
        self.modelo_historial_top5 = ModeloHistorialTop5()

        # Historial PERSISTENTE en la UI que se pasa a tu método cada vez
        self.historial_top5 = [{"role": "system", "content": "Eres un asistente útil y amable."}]

        if self.boton_enviar_3:
            self.boton_enviar_3.clicked.connect(self._on_chat_click)

    def _on_chat_click(self):
        """
        Ejecuta TU método modelohistorial(historial=...) que usa input()/print().
        - Le pasamos self.historial_top5 (lista mutable) para que la actualice.
        - Simulamos input() con el texto del usuario y luego 'salir'.
        - Tu .py ya limita a 4 pares; aquí solo renderizamos el resultado.
        """
        entrada = (self.input_prompt_3.text() if self.input_prompt_3 else "").strip()
        if not entrada:
            self._set_text(self.output_response_3, "⚠️ Escribe un mensaje.")
            return

        respuestas = [entrada, "salir"]

        def fake_input(prompt=""):
            return respuestas.pop(0) if respuestas else "salir"

        buf = io.StringIO()
        real_input = builtins.input
        try:
            builtins.input = fake_input
            with redirect_stdout(buf):
                # Llama a TU método del .py nuevo, pasándole el historial de la UI
                self.modelo_historial_top5.modelohistorial(historial=self.historial_top5)
        except Exception as e:
            self._set_text(self.output_response_3, f"❌ Error: {e}")
            return
        finally:
            builtins.input = real_input

        # (Tu .py ya recorta a 4 pares; aquí solo mostramos)
        texto_hist = self._historial_to_text(self.historial_top5)
        self._set_text(self.output_response_3, texto_hist)

        # Limpia el input de la pestaña Chat
        if self.input_prompt_3:
            self.input_prompt_3.clear()

    # --------------------- Utilidades UI ---------------------
    def _set_text(self, widget, text: str):
        if not widget:
            return
        if hasattr(widget, "setPlainText"):
            widget.setPlainText(str(text))
        elif hasattr(widget, "setText"):
            widget.setText(str(text))

    def _historial_to_text(self, historial):
        """
        Convierte una lista de mensajes [{'role','content'}] a texto legible
        (omite el 'system' para que el panel se vea limpio).
        """
        lineas = []
        for m in historial:
            if m.get("role") == "system":
                continue
            tag = "👤" if m.get("role") == "user" else "🤖"
            lineas.append(f"{tag} {m.get('content','')}")
        return "\n".join(lineas).strip()
