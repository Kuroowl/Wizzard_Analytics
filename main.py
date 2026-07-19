from src.gui.app import criar_app
from src.gui.estado import EstadoApp


def main():
    estado = EstadoApp()  # vazio: o df chega via upload na própria interface
    app = criar_app(estado)
    app.run(debug=True)


if __name__ == '__main__':
    main()