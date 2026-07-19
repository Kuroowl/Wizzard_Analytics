from src.core.rotulos import GerenciadorRotulos


class EstadoApp:
    """
    Estado da execução atual: o df carregado, o gerenciador de rótulos, e
    qual coluna está no eixo X / quais estão no eixo Y no momento.

    Deliberadamente GLOBAL e sem isolamento por sessão — combinado que essa
    aplicação nunca tem mais de uma pessoa usando ao mesmo tempo, então não
    há necessidade da complexidade de estado por sessão. Nada aqui é
    persistido em disco; se o processo reiniciar, tudo se perde (por
    design: nenhum arquivo/log é salvo no servidor).
    """

    def __init__(self):
        self.df = None
        self.gerenciador = None
        self.coluna_x = None
        self.colunas_y = []

    def carregado(self):
        return self.df is not None

    def carregar(self, df, coluna_x_padrao=None, colunas_y_padrao=None):
        self.df = df
        self.gerenciador = GerenciadorRotulos(df.columns)
        self.coluna_x = coluna_x_padrao
        self.colunas_y = list(colunas_y_padrao) if colunas_y_padrao else []

    def atualizar_df(self, df_novo):
        """
        Substitui o df por uma versão processada (resultado de uma operação
        de sampling/filters/math), registrando eventuais colunas novas que
        ainda não estavam no gerenciador.
        """
        self.df = df_novo
        for coluna in df_novo.columns:
            self.gerenciador.registrar_coluna(coluna)