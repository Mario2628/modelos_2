from PyQt5 import QtWidgets
import sys
from load.load_ventana_principal import Load_ventana_principal

def main():
    app = QtWidgets.QApplication(sys.argv)
    ventana = Load_ventana_principal() 
    ventana.show()
    sys.exit(app.exec_())

if __name__== "__main__":
    main()