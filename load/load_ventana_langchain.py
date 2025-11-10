# load/load_ventana_langchain.py
# ------------------------------------------------------
# Ventana para ejecutar tus ejercicios LangChain.
# 1: input de "tema" y "template" (se pasan al script por variables de entorno).
# 2,3,4,5,8: play-only (ejecutar y ver salida).
# 6 y 7: deja tus widgets/implementación como ya la tengas.
# ------------------------------------------------------

import os
import sys
import traceback
import subprocess
from pathlib import Path

from PyQt5 import uic, QtCore
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QListWidget, QTextEdit, QLabel, QWidget,
    QVBoxLayout, QPushButton, QMessageBox, QLineEdit, QSplitter
)

def err(parent, msg): QMessageBox.critical(parent, "Error", msg)
def warn(parent, msg): QMessageBox.warning(parent, "Aviso", msg)

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
                0, lambda: splitter.setSizes([int(self.width()*0.25), int(self.width()*0.75)])
            )

        # Rutas
        self.project_root = Path(os.getcwd())
        self.scripts_dir = self.project_root  # scripts en raíz del proyecto

        # Descripciones (breves)
        self.items = [
            ("1_llmchain.py",               "Ejemplo de PromptTemplate con entrada personalizada."),
            ("2_sequientialchain.py",       "Resumen → Traducción (SequentialChain)."),
            ("3_simplesequientialchain.py", "Pipeline encadenado directo."),
            ("4_parseo.py",                 "Resumen en una oración (parser)."),
            ("5_varios_pasos.py",           "Resumen→Traducción con parser."),
            ("6_memoria.py",                "Conversación con memoria (5 turnos)."),
            ("7_persistencia.py",           "Memoria persistente (JSON)."),
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

    # ------------ util ------------
    def _clear_panel(self):
        while self.panelLayout.count():
            it = self.panelLayout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

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

    # ---------- Panel genérico (2,3,4,5,8) ----------
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

    # ---------- Selector de ejercicio ----------
    def _on_select(self, row: int):
        row = max(0, min(row, len(self.items) - 1))
        name, desc = self.items[row]

        if name == "1_llmchain.py":
            self._build_llmchain1_panel(name, desc)
        elif name in {"6_memoria.py", "7_persistencia.py"}:
            # Aquí puedes insertar tus widgets interactivos existentes si ya los tienes.
            # Para mantener este archivo genérico y corto, mostramos un aviso simple.
            self._clear_panel()
            self.lblTitulo.setText(name)
            self.txtDesc.setPlainText(desc)
            box = QTextEdit()
            box.setReadOnly(True)
            box.setPlainText(
                "Este ejercicio es interactivo en tu proyecto.\n"
                "Inserta aquí el widget personalizado que ya tengas implementado."
            )
            self.panelLayout.addWidget(box)
        else:
            self._build_play_panel(name, desc)
