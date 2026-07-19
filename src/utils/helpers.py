import base64
import os
import tempfile

from src.core.extractor import carregar_dados


def carregar_dados_de_upload(content_string, nome_arquivo):
    """
    Recebe o conteúdo de um arquivo vindo do dcc.Upload do Dash (string
    'data:<mediatype>;base64,<dados>') e devolve o DataFrame carregado.

    O extractor.carregar_dados espera um CAMINHO de arquivo em disco (ele
    reabre o arquivo várias vezes: uma pra detectar encoding, outra pra
    achar o cabeçalho, etc.) — então gravamos num arquivo TEMPORÁRIO só
    pelo tempo do processamento e apagamos logo em seguida. Nada fica
    salvo no servidor além da duração desta chamada.
    """
    try:
        _, dados_codificados = content_string.split(',', 1)
    except ValueError:
        raise ValueError("Formato de upload inesperado (esperava 'data:...;base64,...').")

    conteudo_bytes = base64.b64decode(dados_codificados)

    sufixo = os.path.splitext(nome_arquivo)[1] or '.txt'
    arquivo_temp = tempfile.NamedTemporaryFile(suffix=sufixo, delete=False)
    try:
        arquivo_temp.write(conteudo_bytes)
        arquivo_temp.close()
        df = carregar_dados(arquivo_temp.name)
        return df
    finally:
        os.remove(arquivo_temp.name)  # apaga o temporário, sempre — mesmo se der erro no meio
