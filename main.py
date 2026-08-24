from src.gui.app import criar_app
from src.gui.estado import EstadoApp


def main():
    estado = EstadoApp()  # vazio: o df chega via upload na própria interface
    app = criar_app(estado)
    # threaded=True: sem isso, o servidor de desenvolvimento do Dash atende
    # UM pedido por vez — então, enquanto um arquivo grande está sendo
    # carregado/processado, qualquer outra ação na interface (trocar de
    # aba, fechar aba, marcar canal) fica na fila e a página parece
    # "travada" até o processamento anterior terminar.
    app.run(debug=True, threaded=True)


if __name__ == '__main__':
    main()  