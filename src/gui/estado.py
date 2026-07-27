from src.core.rotulos import GerenciadorRotulos


class EstadoApp:
    """
    Estado global da execução adaptado para múltiplos arquivos.
    Gerencia quais arquivos estão abertos, seus DataFrames, rótulos e canais selecionados.
    """
    #def __init__(self):
        # Dicionário estruturado:
        # {
        #   "ensaio_01.csv": { "df": DataFrame, "gerenciador": GerenciadorRotulos },
        #   "ensaio_02.txt": { "df": DataFrame, "gerenciador": GerenciadorRotulos }
        # }
    #    self.arquivos = {}
    # Guarda quais canais o usuário marcou globalmente para plotar no formato (nome_arquivo, nome_coluna)
        # self.canais_selecionados = set()
        # self.coluna_x = "Tempo_decorrido_s"  # Padrão universal do seu leitor
        # self.grafico_gerado = False  # vira True quando um gráfico de verdade é plotado
     
    def __init__(self):
        self.arquivos = {}
        self.canais_selecionados = set()
        self.coluna_x = "Tempo_decorrido_s"
        self.grafico_gerado = False  # vira True quando um gráfico de verdade é plotado
        self.canais_selecionados = set()

        
    #def adicionar_arquivo(self, nome_arquivo, df):
    #    """Adiciona um novo arquivo ao estado."""
    #    self.arquivos[nome_arquivo] = {
    #        "df": df,
    #        "gerenciador": GerenciadorRotulos(df.columns)
    #    }

    def adicionar_arquivo(self, nome_arquivo, df):
        """Adiciona um novo arquivo guardando também o estado visual do gráfico dele."""
        self.arquivos[nome_arquivo] = {
            "df": df,
            "gerenciador": GerenciadorRotulos(df.columns),
            "figura": None,          # Armazena o objeto Figure do Plotly
            "grafico_gerado": False  # Flag individual por arquivo
        }


    #def remover_arquivo(self, nome_arquivo):
    #    """Remove o arquivo e limpa as seleções dele."""
    #    if nome_arquivo in self.arquivos:
    #        del self.arquivos[nome_arquivo]
    #        # Limpa os canais selecionados que pertenciam a esse arquivo
    #        self.canais_selecionados = {c for c in self.canais_selecionados if c[0] != nome_arquivo}
    #        if not self.arquivos:
                # sem nenhum arquivo aberto, qualquer gráfico gerado antes perde o sentido
    #            self.grafico_gerado = False

    def remover_arquivo(self, nome_arquivo):
        """Remove o arquivo e limpa os canais."""
        if nome_arquivo in self.arquivos:
            del self.arquivos[nome_arquivo]
            self.canais_selecionados = {c for c in self.canais_selecionados if c[0] != nome_arquivo}



    #def alternar_selecao_canal(self, nome_arquivo, coluna):
    #    """Marca ou desmarca um canal para plotagem."""
    #    par = (nome_arquivo, coluna)
    #    if par in self.canais_selecionados:
    #        self.canais_selecionados.remove(par)
    #    else:
    #        self.canais_selecionados.add(par)

    def alternar_selecao_canal(self, nome_arquivo, coluna):
        """Marca ou desmarca um canal para plotagem."""
        par = (nome_arquivo, coluna)
        if par in self.canais_selecionados:
            self.canais_selecionados.remove(par)
        else:
            self.canais_selecionados.add(par)

    #def obter_colunas(self, nome_arquivo):
    #    """Retorna a lista de colunas de um arquivo específico."""
    #    if nome_arquivo in self.arquivos:
    #        return list(self.arquivos[nome_arquivo]["df"].columns)
    #    return []

    def obter_colunas(self, nome_arquivo):
        """Retorna a lista de colunas de um arquivo específico."""
        if nome_arquivo in self.arquivos:
            return list(self.arquivos[nome_arquivo]["df"].columns)
        return []