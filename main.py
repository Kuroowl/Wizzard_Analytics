from src.core.extractor import carregar_dados
from src.core.operations.math import media_e_desvio_colunas
from src.core.rotulos import GerenciadorRotulos
from src.gui.app import criar_app


CAMINHO_ARQUIVO = 'fieldlogger_data.txt'  # troque pelo caminho real do seu ensaio
COLUNAS_PARA_MEDIA = ['C1-PRS04', 'C3-PRS03', 'C4-PRS01']
COLUNA_X = 'Tempo_decorrido_s'
COLUNAS_Y = ['media_pressoes', 'desvio_pressoes']


def main():
    # 1. extractor: lê e limpa o arquivo bruto
    df = carregar_dados(CAMINHO_ARQUIVO)

    # 2. operations: aplica os cálculos desejados sobre o dado carregado
    df = media_e_desvio_colunas(
        df, COLUNAS_PARA_MEDIA,
        nome_media='media_pressoes', nome_desvio='desvio_pressoes',
    )

    # 3. gerenciador de rótulos, já ciente de todas as colunas (originais + calculadas)
    gerenciador = GerenciadorRotulos(df.columns)

    # 4. gui: monta o app com o estado pronto e sobe o servidor
    app = criar_app(df, COLUNA_X, COLUNAS_Y, gerenciador)
    app.run(debug=True)


if __name__ == '__main__':
    main()