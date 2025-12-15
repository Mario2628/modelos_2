from PyQt5 import QtWidgets, uic
from load.load_ventana_modelos_basicos import Load_ventana_modelos_basicos
from load.load_ventana_langchain import Load_ventana_langchain  # ← ya lo tenías
from load.load_ventana_cuestionario import Load_ventana_cuestionario  # ← nuevo import

class Load_ventana_principal(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("interfaces/Ventana_principal.ui", self)
        self.showMaximized()

        # Conexiones que ya tenías
        self.actionBasicos.triggered.connect(self.abrirVentanaBasicos)
        self.actionLangchain.triggered.connect(self.abrirVentanaLangchain)
        self.actionSalir.triggered.connect(self.cerrarVentana)

        # 🔹 NUEVO: atributo para guardar la ventana del cuestionario
        self.ventana_cuestionario = None

        # 🔹 NUEVO: conectar el menú "Cuestionario"
        self.actionCuestionario.triggered.connect(self.abrir_cuestionario)

    def abrirVentanaBasicos(self):
        self.basicos = Load_ventana_modelos_basicos()
        self.basicos.exec_()

    def abrirVentanaLangchain(self):
        self.langchain = Load_ventana_langchain()
        self.langchain.exec_()  # el QDialog abre maximizado

    def abrir_cuestionario(self):
        if self.ventana_cuestionario is None:
            self.ventana_cuestionario = Load_ventana_cuestionario(self)
        self.ventana_cuestionario.show()
        self.ventana_cuestionario.raise_()
        self.ventana_cuestionario.activateWindow()

    def cerrarVentana(self):
        self.close()
