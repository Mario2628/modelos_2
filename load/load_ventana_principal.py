from PyQt5 import QtWidgets, uic
from load.load_ventana_modelos_basicos import Load_ventana_modelos_basicos
from load.load_ventana_langchain import Load_ventana_langchain  # ← nuevo

class Load_ventana_principal(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("interfaces/Ventana_principal.ui", self)
        self.showMaximized()

        self.actionBasicos.triggered.connect(self.abrirVentanaBasicos)
        self.actionLangchain.triggered.connect(self.abrirVentanaLangchain)
        self.actionSalir.triggered.connect(self.cerrarVentana)

    def abrirVentanaBasicos(self):
        self.basicos = Load_ventana_modelos_basicos()
        self.basicos.exec_()

    def abrirVentanaLangchain(self):
        self.langchain = Load_ventana_langchain()
        self.langchain.exec_()  # el QDialog abre maximizado

    def cerrarVentana(self):
        self.close()
