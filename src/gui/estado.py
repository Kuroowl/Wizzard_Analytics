from src.core.arquivo import Arquivo


class EstadoApp:
    """
    Estado global da execução, adaptado para múltiplos arquivos.

    Cada arquivo aberto vira um objeto Arquivo (src/core/arquivo.py),
    que já guarda seu próprio df, canais, figura e preferências de
    exibição. EstadoApp só guarda a COLEÇÃO de arquivos abertos e o
    que é necessariamente global entre eles:

      - canais_selecionados: quais canais (de qualquer arquivo) estão
        marcados pra entrar no gráfico ATUAL. É global (não por
        arquivo) porque a feature de combinar canais de arquivos
        diferentes num mesmo gráfico depende disso.
      - coluna_x: nome padrão da coluna usada como eixo X.
    """

    def __init__(self):
        self.arquivos: dict[str, Arquivo] = {}
        self.canais_selecionados = set()
        self.coluna_x = "Tempo_decorrido_s"

    def adicionar_arquivo(self, nome_arquivo, df, avisos=None, info=None):
        """
        Adiciona um novo arquivo ao estado.

        'avisos' e 'info' vêm do carregador (src/core/extractor.py via
        helpers.carregar_dados_de_upload) e alimentam o rodapé da GUI:
          - avisos: lista de strings (cabeçalho/coluna ajustados, NaN
            encontrado, etc.) — mostrada na caixinha de alerta.
          - info: dict com 'encoding', 'delimitador', 'n_linhas',
            'n_colunas' — mostrado como texto fixo do rodapé.
        """
        info = info or {}
        self.arquivos[nome_arquivo] = Arquivo(
            nome=nome_arquivo,
            df_original=df.copy(),
            df_editado=df.copy(),
            avisos=list(avisos) if avisos else [],
            info=info,
            # Canais não numéricos (texto/booleano/não conversível) já
            # detectados pelo extractor nascem ocultos por padrão — ver
            # Arquivo.__post_init__ em src/core/arquivo.py.
            colunas_ocultas_iniciais=info.get('colunas_nao_numericas', []),
        )

    def remover_arquivo(self, nome_arquivo):
        """Remove o arquivo e limpa os canais dele da seleção global."""
        if nome_arquivo in self.arquivos:
            del self.arquivos[nome_arquivo]
            self.canais_selecionados = {c for c in self.canais_selecionados if c[0] != nome_arquivo}

    def alternar_selecao_canal(self, nome_arquivo, coluna):
        """Marca ou desmarca um canal para plotagem."""
        par = (nome_arquivo, coluna)
        if par in self.canais_selecionados:
            self.canais_selecionados.remove(par)
        else:
            self.canais_selecionados.add(par)

    def obter_colunas(self, nome_arquivo):
        """Retorna as colunas visíveis de um arquivo específico."""
        arquivo = self.arquivos.get(nome_arquivo)
        return arquivo.colunas_visiveis() if arquivo else []

    def algum_arquivo_com_grafico(self):
        """True se pelo menos um arquivo aberto já tem um gráfico gerado."""
        return any(arquivo.grafico_gerado for arquivo in self.arquivos.values())
