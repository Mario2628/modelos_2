# load/load_ventana_langchain.py
# ------------------------------------------------------
# Ventana para ejecutar tus ejercicios LangChain.
# 1: input de "tema" y "template" (se pasan al script por variables de entorno).
# 2,3: resumen + traducción al inglés desde la interfaz, un solo botón.
# 4,5: texto → texto simple (usando funciones del script).
# 6 y 7: chat interactivo con memoria (6: memoria en GUI, 7: memoria en el script).
# 8: RAG con PDF seleccionable.
# ------------------------------------------------------

import os
import sys
import traceback
import subprocess
from pathlib import Path
import importlib.util

from PyQt5 import uic, QtCore
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QListWidget, QTextEdit, QLabel, QWidget,
    QVBoxLayout, QPushButton, QMessageBox, QLineEdit, QSplitter,
    QComboBox, QFileDialog
)


def err(parent, msg):
    QMessageBox.critical(parent, "Error", msg)


def warn(parent, msg):
    QMessageBox.warning(parent, "Aviso", msg)


class QLabelBig(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.setStyleSheet("font-size: 16pt; font-weight: 600;")


# ---------------- Runner (ejecuta scripts en subproceso) ----------------
class ScriptRunner(QThread):
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(int)
    finished_err = pyqtSignal(str)

    def __init__(self, script_path: Path, workdir: Path, env: dict):
        super().__init__()
        self.script_path = script_path
        self.workdir = workdir
        self.env = env

    def run(self):
        try:
            if not self.script_path.exists():
                self.finished_err.emit(f"Archivo no encontrado:\n{self.script_path}")
                return

            proc = subprocess.Popen(
                [sys.executable, str(self.script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.workdir),
                env=self.env,
                bufsize=1
            )

            assert proc.stdout is not None
            for line in proc.stdout:
                self.line.emit(line.rstrip("\n"))

            assert proc.stderr is not None
            stderr_txt = proc.stderr.read().strip()
            code = proc.wait()

            if code == 0:
                if stderr_txt:
                    self.line.emit("\n[stderr]\n" + stderr_txt)
                self.finished_ok.emit(code)
            else:
                self.finished_err.emit(
                    f"El script terminó con código {code}.\n"
                    f"Ruta: {self.script_path}\n\nstderr:\n{stderr_txt}"
                )
        except Exception as e:
            self.finished_err.emit(f"{e}\n\n{traceback.format_exc()}")


# ---------------- Runner para funciones de Python (misma sesión) ----------------
class FunctionRunner(QThread):
    line = pyqtSignal(str)
    finished_ok = pyqtSignal(int)
    finished_err = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)

            # Soportar listas/tuplas como varias salidas
            if isinstance(result, (list, tuple)):
                text = "\n".join(str(x) for x in result)
            else:
                text = "" if result is None else str(result)

            if not text.strip():
                text = "[Sin salida]"

            self.line.emit(text)
            self.finished_ok.emit(0)
        except Exception as e:
            self.finished_err.emit(f"{e}\n\n{traceback.format_exc()}")


# ================== Ventana principal ==================
class Load_ventana_langchain(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("interfaces/ventana_langchain.ui", self)

        # Ventana max, sin botón de ayuda
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlags(self.windowFlags() |
                            QtCore.Qt.WindowMinMaxButtonsHint |
                            QtCore.Qt.WindowSystemMenuHint)
        self.setWindowState(QtCore.Qt.WindowMaximized)

        # Widgets del .ui
        self.list: QListWidget = self.findChild(QListWidget, "listExercises")
        self.lblTitulo: QLabel = self.findChild(QLabel, "lblTitulo")
        self.txtDesc: QTextEdit = self.findChild(QTextEdit, "txtDesc")
        self.panelContainer: QWidget = self.findChild(QWidget, "panelContainer")
        self.panelLayout: QVBoxLayout = self.panelContainer.layout()

        splitter: QSplitter = self.findChild(QSplitter, "splitter")
        if splitter:
            QtCore.QTimer.singleShot(
                0, lambda: splitter.setSizes([int(self.width() * 0.25), int(self.width() * 0.75)])
            )

        # Rutas
        self.project_root = Path(os.getcwd())
        self.scripts_dir = self.project_root  # scripts en raíz del proyecto

        # Descripciones (breves)
        self.items = [
            ("1_llmchain.py",               "Ejemplo de PromptTemplate con entrada personalizada."),
            ("2_sequientialchain.py",       "Resumen → Traducción al inglés (SequentialChain)."),
            ("3_simplesequientialchain.py", "Resumen → Traducción al inglés (pipeline directo)."),
            ("4_parseo.py",                 "Resumen en una oración (parser)."),
            ("5_varios_pasos.py",           "Resumen→Traducción con parser."),
            ("6_memoria.py",                "Conversación con memoria (3 turnos en RAM desde la GUI)."),
            ("7_persistencia.py",           "Memoria persistente (JSON, desde el script)."),
            ("8_memoria.py",                "RAG con PDF (FAISS)."),
        ]
        for n, _ in self.items:
            self.list.addItem(n)

        self.list.currentRowChanged.connect(self._on_select)
        self._on_select(0)

        # Estado de ejecución
        self.runner = None
        self.btn_play = None
        self.txt_output = None

        # Campos del ejercicio 1
        self.inp_tema = None
        self.inp_template = None
        self.btn_run_tema = None

        # Campos genéricos de paneles de texto
        self.txt_input = None
        self.btn_run_chain = None

        # Campos para paneles de chat (6 y 7)
        self.inp_chat = None
        self.btn_chat_send = None
        self.btn_chat_reset = None

        # Panel resumen/traducción (2 y 3)
        self.btn_resumir = None
        self.btn_traducir = None
        self.cmb_idioma = None
        self.txt_resumen = None
        self.txt_traduccion = None

        # Panel RAG (8)
        self.txt_pdf_path = None
        self.btn_select_pdf = None
        self.pdf_path_8 = None

        # Cache de módulos cargados dinámicamente
        self.modules_cache = {}

        # Estado de memoria para el ejercicio 6 (en GUI)
        self._mem6 = None

    # ------------ util ------------
    def _clear_panel(self):
        while self.panelLayout.count():
            it = self.panelLayout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

        # Reset referencias de widgets dinámicos
        self.txt_output = None
        self.txt_input = None
        self.btn_run_chain = None
        self.inp_chat = None
        self.btn_chat_send = None
        self.btn_chat_reset = None

        self.btn_resumir = None
        self.btn_traducir = None
        self.cmb_idioma = None
        self.txt_resumen = None
        self.txt_traduccion = None

        self.txt_pdf_path = None
        self.btn_select_pdf = None
        self.pdf_path_8 = None

    def _load_module(self, script_name: str):
        """Importa dinámicamente el archivo de ejercicio y lo cachea."""
        if script_name in self.modules_cache:
            return self.modules_cache[script_name]

        path = self.scripts_dir / script_name
        if not path.exists():
            err(self, f"No se encontró el archivo:\n{path}")
            return None

        try:
            mod_name = f"lc_{script_name.replace('.py', '').replace('-', '_').replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, str(path))
            if spec is None or spec.loader is None:
                err(self, f"No se pudo cargar el módulo desde:\n{path}")
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.modules_cache[script_name] = module
            return module
        except Exception as e:
            err(self, f"Error al importar {script_name}:\n{e}\n\n{traceback.format_exc()}")
            return None

    # ---------- Panel del ejercicio 1: Tema + Template ----------
    def _build_llmchain1_panel(self, script_name: str, desc: str):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        w = QWidget()
        v = QVBoxLayout(w)

        self.inp_tema = QLineEdit()
        self.inp_tema.setPlaceholderText("Escribe el tema para {tema} …")

        self.inp_template = QLineEdit()
        self.inp_template.setPlaceholderText("Escribe el template (debe incluir {tema})")
        self.inp_template.setText("Explícale a un estudiante universitario el tema {tema}.")

        # Botón corto
        self.btn_run_tema = QPushButton("▶ Ejecutar")

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        v.addWidget(QLabelBig("Tema:"))
        v.addWidget(self.inp_tema)
        v.addWidget(QLabelBig("Template (debe incluir {tema}):"))
        v.addWidget(self.inp_template)
        v.addWidget(self.btn_run_tema)
        v.addWidget(QLabelBig("Salida:"))
        v.addWidget(self.txt_output)

        self.panelLayout.addWidget(w)
        self.btn_run_tema.clicked.connect(lambda: self._run_script_llmchain1(script_name))

    def _run_script_llmchain1(self, script_name: str):
        if self.runner and self.runner.isRunning():
            return warn(self, "Ya hay un script ejecutándose.")

        path = self.scripts_dir / script_name
        if not path.exists():
            return err(self, f"No se encontró el archivo:\n{path}")

        tema = (self.inp_tema.text() if self.inp_tema else "").strip()
        template = (self.inp_template.text() if self.inp_template else "").strip()

        if not tema:
            return warn(self, "Escribe un tema para {tema}.")
        if not template:
            return warn(self, "Escribe un template que contenga {tema}.")
        if "{tema}" not in template:
            return warn(self, "El template debe incluir {tema}.")

        env = os.environ.copy()
        env["PROMPT_TEMA"] = tema
        env["PROMPT_TEMPLATE"] = template

        self.txt_output.clear()
        self.txt_output.append(f"[Ejecutando] {path}\n")

        self.runner = ScriptRunner(path, self.project_root, env)
        self.runner.line.connect(self.txt_output.append)
        self.runner.finished_ok.connect(lambda _: self.txt_output.append("\n[OK] Ejecución terminada."))
        self.runner.finished_err.connect(lambda m: (err(self, m), self.txt_output.append("\n[ERROR]\n" + m)))
        self.runner.start()

    # ---------- Panel genérico (1,4,5,7,8 fallback de script directo) ----------
    def _build_play_panel(self, script_name: str, desc: str):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.btn_play = QPushButton("▶ Ejecutar")
        self.btn_play.setCursor(QtCore.Qt.PointingHandCursor)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self.btn_play)
        v.addWidget(QLabelBig("Salida:"))
        v.addWidget(self.txt_output)
        self.panelLayout.addWidget(w)

        self.btn_play.clicked.connect(lambda: self._run_script(script_name))

    def _run_script(self, script_name: str):
        if self.runner and self.runner.isRunning():
            return warn(self, "Ya hay un script ejecutándose.")

        path = self.scripts_dir / script_name
        if not path.exists():
            return err(self, f"No se encontró el archivo:\n{path}")

        env = os.environ.copy()

        self.txt_output.clear()
        self.txt_output.append(f"[Ejecutando] {path}\n")

        self.runner = ScriptRunner(path, self.project_root, env)
        self.runner.line.connect(self.txt_output.append)
        self.runner.finished_ok.connect(lambda _: self.txt_output.append("\n[OK] Ejecución terminada."))
        self.runner.finished_err.connect(lambda m: (err(self, m), self.txt_output.append("\n[ERROR]\n" + m)))
        self.runner.start()

    # ---------- Panel simple texto → texto (4,5) ----------
    def _build_simple_chain_panel(self, script_name: str, desc: str,
                                  input_label: str, output_label: str,
                                  func_name: str):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("Escribe aquí el texto de entrada…")

        self.btn_run_chain = QPushButton("▶ Ejecutar")
        self.btn_run_chain.setCursor(QtCore.Qt.PointingHandCursor)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabelBig(input_label))
        v.addWidget(self.txt_input)
        v.addWidget(self.btn_run_chain)
        v.addWidget(QLabelBig(output_label))
        v.addWidget(self.txt_output)

        self.panelLayout.addWidget(w)

        self.btn_run_chain.clicked.connect(
            lambda: self._run_simple_chain(script_name, func_name)
        )

    def _run_simple_chain(self, script_name: str, func_name: str):
        if self.runner and self.runner.isRunning():
            return warn(self, "Ya hay un proceso en ejecución.")

        if not self.txt_input:
            return

        text = self.txt_input.toPlainText().strip()
        if not text:
            return warn(self, "Escribe algún texto de entrada.")

        module = self._load_module(script_name)
        if module is None:
            return

        fn = getattr(module, func_name, None)
        if not callable(fn):
            return err(self, f"El archivo {script_name} no define la función {func_name}().")

        self.txt_output.clear()
        self.txt_output.append(f"[Ejecutando] {script_name}\n")
        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(False)

        self.runner = FunctionRunner(fn, text)
        self.runner.line.connect(self.txt_output.append)
        self.runner.finished_ok.connect(lambda _: self._on_func_finished_ok())
        self.runner.finished_err.connect(lambda m: self._on_func_finished_err(m))
        self.runner.start()

    def _on_func_finished_ok(self):
        if self.txt_output:
            self.txt_output.append("\n[OK] Ejecución terminada.")
        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(True)
        self.runner = None

    def _on_func_finished_err(self, msg: str):
        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(True)
        err(self, msg)
        if self.txt_output:
            self.txt_output.append("\n[ERROR]\n" + msg)
        self.runner = None

    # ---------- Panel resumen + traducción (ejercicios 2 y 3) ----------
    def _build_resumen_traduccion_panel(self, script_name: str, desc: str):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText(
            "Escribe aquí el texto que quieras resumir y traducir al inglés…"
        )

        self.btn_run_chain = QPushButton("▶ Ejecutar")
        self.btn_run_chain.setCursor(QtCore.Qt.PointingHandCursor)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabelBig("Texto de entrada:"))
        v.addWidget(self.txt_input)
        v.addWidget(self.btn_run_chain)
        v.addWidget(QLabelBig("Salida (resumen + traducción al inglés):"))
        v.addWidget(self.txt_output)

        self.panelLayout.addWidget(w)

        self.btn_run_chain.clicked.connect(
            lambda: self._run_resumen_traduccion(script_name)
        )

    def _run_resumen_traduccion(self, script_name: str):
        if not self.txt_input:
            return

        texto = self.txt_input.toPlainText().strip()
        if not texto:
            return warn(self, "Escribe un texto de entrada.")

        try:
            from dotenv import load_dotenv
            from langchain.prompts import PromptTemplate
            from langchain_google_genai import ChatGoogleGenerativeAI

            load_dotenv()
            os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

            prompt_resumen = PromptTemplate.from_template(
                "Resume el siguiente texto: {input}"
            )
            prompt_traduccion = PromptTemplate.from_template(
                "Tradúcelo al inglés: {input}"
            )

            if script_name == "2_sequientialchain.py":
                chain_resumen = prompt_resumen | llm
                chain_traduccion = prompt_traduccion | llm
                chain_final = chain_resumen | chain_traduccion
                result = chain_final.invoke(texto)
            else:
                chain = prompt_resumen | llm | prompt_traduccion | llm
                result = chain.invoke(texto)

            texto_final = result.content if hasattr(result, "content") else str(result)
            if self.txt_output:
                self.txt_output.setPlainText(texto_final.strip())
        except Exception as e:
            err(self, f"{e}\n\n{traceback.format_exc()}")

    # ---------- Panel de chat (ejercicio 7: usa tu script) ----------
    def _build_chat_panel(self, script_name: str, desc: str,
                          func_name: str, reset_fn_name: str = None):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        self.inp_chat = QLineEdit()
        self.inp_chat.setPlaceholderText("Escribe tu mensaje para el asistente…")

        self.btn_chat_send = QPushButton("Enviar mensaje")
        self.btn_chat_send.setCursor(QtCore.Qt.PointingHandCursor)

        layout = QVBoxLayout()
        layout.addWidget(QLabelBig("Historial de conversación:"))
        layout.addWidget(self.txt_output)
        layout.addWidget(QLabelBig("Tu mensaje:"))
        layout.addWidget(self.inp_chat)
        layout.addWidget(self.btn_chat_send)

        self.btn_chat_reset = None
        if reset_fn_name:
            self.btn_chat_reset = QPushButton("🧹 Borrar memoria")
            self.btn_chat_reset.setCursor(QtCore.Qt.PointingHandCursor)
            layout.addWidget(self.btn_chat_reset)

        w = QWidget()
        w.setLayout(layout)
        self.panelLayout.addWidget(w)

        self.btn_chat_send.clicked.connect(
            lambda: self._run_chat_message(script_name, func_name)
        )
        if reset_fn_name and self.btn_chat_reset:
            self.btn_chat_reset.clicked.connect(
                lambda: self._reset_chat_memory(script_name, reset_fn_name)
            )

        self.txt_output.append("La memoria de la conversación se conserva entre mensajes.")
        if script_name == "7_persistencia.py":
            self.txt_output.append(
                "En este ejercicio además se guarda el historial en un archivo JSON (memoria persistente)."
            )

    def _run_chat_message(self, script_name: str, func_name: str):
        if self.runner and self.runner.isRunning():
            return warn(self, "Ya hay un proceso en ejecución.")

        if not self.inp_chat:
            return

        text = self.inp_chat.text().strip()
        if not text:
            return warn(self, "Escribe un mensaje.")

        module = self._load_module(script_name)
        if module is None:
            return

        fn = getattr(module, func_name, None)
        if not callable(fn):
            return err(self, f"El archivo {script_name} no define la función {func_name}().")

        if self.txt_output:
            self.txt_output.append(f"👤 Tú: {text}")

        self.inp_chat.clear()
        if self.btn_chat_send:
            self.btn_chat_send.setEnabled(False)

        self.runner = FunctionRunner(fn, text)
        self.runner.line.connect(self._append_bot_message)
        self.runner.finished_ok.connect(lambda _: self._on_chat_finished_ok())
        self.runner.finished_err.connect(lambda m: self._on_chat_finished_err(m))
        self.runner.start()

    def _append_bot_message(self, text: str):
        if self.txt_output:
            self.txt_output.append(f"🤖 Asistente: {text}")

    def _on_chat_finished_ok(self):
        if self.btn_chat_send:
            self.btn_chat_send.setEnabled(True)
        self.runner = None

    def _on_chat_finished_err(self, msg: str):
        if self.btn_chat_send:
            self.btn_chat_send.setEnabled(True)
        err(self, msg)
        if self.txt_output:
            self.txt_output.append("\n[ERROR]\n" + msg)
        self.runner = None

    def _reset_chat_memory(self, script_name: str, reset_fn_name: str):
        module = self._load_module(script_name)
        if module is None:
            return

        fn = getattr(module, reset_fn_name, None)
        if not callable(fn):
            return err(self, f"El archivo {script_name} no define la función {reset_fn_name}().")

        try:
            fn()
            if self.txt_output:
                self.txt_output.clear()
                self.txt_output.append("Memoria reiniciada.")
        except Exception as e:
            err(self, f"No se pudo reiniciar la memoria:\n{e}")

    # ---------- Ejercicio 6: chat con memoria SOLO 3 conversaciones (en GUI) ----------
    def _init_mem6(self):
        """Inicializa la memoria interna del ejercicio 6 (3 conversaciones)."""
        if self._mem6 is not None:
            return

        from dotenv import load_dotenv
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain.prompts import ChatPromptTemplate
        # *** CAMBIO IMPORTANTE SOLO AQUÍ: usamos ConversationBufferWindowMemory ***
        from langchain.memory import ConversationBufferWindowMemory

        load_dotenv()
        os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

        class MemoriaSesion:
            def __init__(self, max_items=3):
                self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
                self.prompt = ChatPromptTemplate.from_messages([
                    ("system", "Eres un asistente útil y recuerdas la conversación anterior."),
                    ("placeholder", "{history}"),
                    ("human", "{input}")
                ])
                # Solo guarda las ÚLTIMAS max_items conversaciones (pares usuario+IA)
                self.memory = ConversationBufferWindowMemory(
                    k=max_items,
                    return_messages=True
                )

            def conversar(self, texto: str) -> str:
                vars_ = self.memory.load_memory_variables({})
                history = vars_.get("history", [])
                chain = self.prompt | self.llm
                resp = chain.invoke({"history": history, "input": texto})
                self.memory.save_context({"input": texto}, {"output": resp.content})
                return resp.content.strip()

        self._mem6 = MemoriaSesion(max_items=3)

    def _build_memoria6_panel(self, script_name: str, desc: str):
        """Interfaz del ejercicio 6: igual aspecto que el chat, pero memoria en la GUI (3 turnos)."""
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        self.inp_chat = QLineEdit()
        self.inp_chat.setPlaceholderText("Escribe tu mensaje para el asistente…")

        self.btn_chat_send = QPushButton("Enviar mensaje")
        self.btn_chat_send.setCursor(QtCore.Qt.PointingHandCursor)

        self.btn_chat_reset = QPushButton("🧹 Borrar memoria")
        self.btn_chat_reset.setCursor(QtCore.Qt.PointingHandCursor)

        layout = QVBoxLayout()
        layout.addWidget(QLabelBig("Historial de conversación:"))
        layout.addWidget(self.txt_output)
        layout.addWidget(QLabelBig("Tu mensaje:"))
        layout.addWidget(self.inp_chat)
        layout.addWidget(self.btn_chat_send)
        layout.addWidget(self.btn_chat_reset)

        w = QWidget()
        w.setLayout(layout)
        self.panelLayout.addWidget(w)

        self.btn_chat_send.clicked.connect(self._run_memoria6_message)
        self.btn_chat_reset.clicked.connect(self._reset_memoria6)

        self.txt_output.append(
            "La memoria de la conversación se conserva entre mensajes, "
            "pero SOLO recuerda las últimas 3 conversaciones (pregunta-respuesta)."
        )

    def _run_memoria6_message(self):
        if self.runner and self.runner.isRunning():
            return warn(self, "Ya hay un proceso en ejecución.")

        if not self.inp_chat:
            return

        text = self.inp_chat.text().strip()
        if not text:
            return warn(self, "Escribe un mensaje.")

        self._init_mem6()

        if self.txt_output:
            self.txt_output.append(f"👤 Tú: {text}")

        self.inp_chat.clear()
        if self.btn_chat_send:
            self.btn_chat_send.setEnabled(False)

        self.runner = FunctionRunner(self._mem6.conversar, text)
        self.runner.line.connect(self._append_bot_message)
        self.runner.finished_ok.connect(lambda _: self._on_chat_finished_ok())
        self.runner.finished_err.connect(lambda m: self._on_chat_finished_err(m))
        self.runner.start()

    def _reset_memoria6(self):
        self._mem6 = None
        if self.txt_output:
            self.txt_output.clear()
            self.txt_output.append("Memoria reiniciada (se olvidaron todas las conversaciones previas).")

    # ---------- Panel RAG (ejercicio 8) ----------
    def _build_rag_panel(self, script_name: str, desc: str):
        self._clear_panel()
        self.lblTitulo.setText(script_name)
        self.txtDesc.setPlainText(desc)

        self.txt_pdf_path = QLineEdit()
        self.txt_pdf_path.setReadOnly(True)
        self.txt_pdf_path.setPlaceholderText(
            "Ningún PDF seleccionado. Se usará el PDF por defecto del script si no eliges otro."
        )

        self.btn_select_pdf = QPushButton("Seleccionar PDF…")
        self.btn_select_pdf.setCursor(QtCore.Qt.PointingHandCursor)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("Escribe aquí tu pregunta sobre el PDF…")

        self.btn_run_chain = QPushButton("▶ Ejecutar")
        self.btn_run_chain.setCursor(QtCore.Qt.PointingHandCursor)

        self.txt_output = QTextEdit()
        self.txt_output.setReadOnly(True)
        self.txt_output.setStyleSheet("font-size:14pt;")

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabelBig("PDF de contexto:"))
        v.addWidget(self.txt_pdf_path)
        v.addWidget(self.btn_select_pdf)
        v.addWidget(QLabelBig("Pregunta:"))
        v.addWidget(self.txt_input)
        v.addWidget(self.btn_run_chain)
        v.addWidget(QLabelBig("Respuesta:"))
        v.addWidget(self.txt_output)

        self.panelLayout.addWidget(w)

        self.btn_select_pdf.clicked.connect(
            lambda: self._seleccionar_pdf(script_name)
        )
        self.btn_run_chain.clicked.connect(
            lambda: self._run_rag_query(script_name)
        )

    def _seleccionar_pdf(self, script_name: str):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar PDF",
            "",
            "Archivos PDF (*.pdf)"
        )
        if not file_path:
            return

        self.pdf_path_8 = file_path
        if self.txt_pdf_path:
            self.txt_pdf_path.setText(file_path)

        module = self._load_module(script_name)
        if module is None:
            return

        inicializar = getattr(module, "inicializar_indice", None)
        if not callable(inicializar):
            return err(self, f"El archivo {script_name} no define la función inicializar_indice().")

        if self.btn_select_pdf:
            self.btn_select_pdf.setEnabled(False)
        if self.txt_output:
            self.txt_output.clear()
            self.txt_output.append("Cargando y procesando el PDF seleccionado...\n")

        self.runner = FunctionRunner(inicializar, file_path)
        self.runner.line.connect(self._on_pdf_index_message)
        self.runner.finished_ok.connect(lambda _: self._on_pdf_index_ok())
        self.runner.finished_err.connect(lambda m: self._on_pdf_index_err(m))
        self.runner.start()

    def _on_pdf_index_message(self, text: str):
        if self.txt_output and text:
            self.txt_output.append(text)

    def _on_pdf_index_ok(self):
        if self.btn_select_pdf:
            self.btn_select_pdf.setEnabled(True)
        if self.txt_output:
            self.txt_output.append("\n[OK] PDF procesado.")
        self.runner = None

    def _on_pdf_index_err(self, msg: str):
        if self.btn_select_pdf:
            self.btn_select_pdf.setEnabled(True)
        err(self, msg)
        if self.txt_output:
            self.txt_output.append("\n[ERROR]\n" + msg)
        self.runner = None

    def _run_rag_query(self, script_name: str):
        if self.runner and self.runner.isRunning():
            return warn(self, "Hay otra operación en curso.")

        if not self.txt_input:
            return

        pregunta = self.txt_input.toPlainText().strip()
        if not pregunta:
            return warn(self, "Escribe una pregunta.")

        module = self._load_module(script_name)
        if module is None:
            return

        fn = getattr(module, "preguntar", None)
        if not callable(fn):
            return err(self, f"El archivo {script_name} no define la función preguntar().")

        if self.txt_output:
            self.txt_output.clear()
            self.txt_output.append("Consultando el documento...\n")

        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(False)

        self.runner = FunctionRunner(fn, pregunta)
        self.runner.line.connect(self.txt_output.append)
        self.runner.finished_ok.connect(lambda _: self._on_rag_finished_ok())
        self.runner.finished_err.connect(lambda m: self._on_rag_finished_err(m))
        self.runner.start()

    def _on_rag_finished_ok(self):
        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(True)
        self.runner = None

    def _on_rag_finished_err(self, msg: str):
        if self.btn_run_chain:
            self.btn_run_chain.setEnabled(True)
        err(self, msg)
        if self.txt_output:
            self.txt_output.append("\n[ERROR]\n" + msg)
        self.runner = None

    # ---------- Selector de ejercicio ----------
    def _on_select(self, row: int):
        row = max(0, min(row, len(self.items) - 1))
        name, desc = self.items[row]

        if name == "1_llmchain.py":
            self._build_llmchain1_panel(name, desc)

        elif name == "2_sequientialchain.py":
            self._build_resumen_traduccion_panel(name, desc)

        elif name == "3_simplesequientialchain.py":
            self._build_resumen_traduccion_panel(name, desc)

        elif name == "4_parseo.py":
            self._build_simple_chain_panel(
                name, desc,
                "Texto a resumir:",
                "Resumen en una sola oración:",
                "run_chain",
            )

        elif name == "5_varios_pasos.py":
            self._build_simple_chain_panel(
                name, desc,
                "Texto a procesar:",
                "Salida final:",
                "run_chain",
            )

        elif name == "6_memoria.py":
            self._build_memoria6_panel(name, desc)

        elif name == "7_persistencia.py":
            self._build_chat_panel(
                name, desc,
                func_name="ejecutar_con_memoria",
                reset_fn_name="resetear_memoria",
            )

        elif name == "8_memoria.py":
            self._build_rag_panel(name, desc)

        else:
            self._build_play_panel(name, desc)
