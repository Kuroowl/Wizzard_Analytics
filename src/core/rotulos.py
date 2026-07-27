import re
import unicodedata


class GerenciadorRotulos:
    """
    Versão Resiliente do GerenciadorRotulos.
    Previne travamentos na interface registrando automaticamente colunas
    novas (como Tempo_decorrido_s ou colunas calculadas) em vez de lançar KeyError.
    """

    def __init__(self, colunas):
        self._rotulos = {str(nome): str(nome) for nome in colunas}
        self._historico = []

    def rotulo_atual(self, nome_interno):
        """
        Retorna o rótulo visual. Se a coluna não existir, registra-a
        automaticamente com o próprio nome para evitar travar a UI.
        """
        if nome_interno not in self._rotulos:
            # AUTO-REGISTRO SILENCIOSO: Evita estourar KeyError na interface
            self._rotulos[nome_interno] = str(nome_interno)
        return self._rotulos[nome_interno]

    def nome_interno(self, rotulo):
        """
        Busca reversa. Se o rótulo não for encontrado, assume que
        o rótulo é o próprio nome interno em vez de travar o callback.
        """
        for interno, atual in self._rotulos.items():
            if atual == rotulo:
                return interno
        
        # Fallback seguro: se não achar mapeamento, retorna o próprio rótulo
        return rotulo

    def renomear(self, nome_interno, novo_rotulo):
        if nome_interno not in self._rotulos:
            self.registrar_coluna(nome_interno)

        novo_rotulo = novo_rotulo.strip()
        if not novo_rotulo:
            raise ValueError("O novo rótulo não pode ser vazio.")

        colisao = next(
            (interno for interno, atual in self._rotulos.items()
             if atual == novo_rotulo and interno != nome_interno),
            None
        )
        if colisao:
            raise ValueError(
                f"O rótulo '{novo_rotulo}' já está em uso pela coluna '{colisao}'."
            )

        rotulo_anterior = self._rotulos[nome_interno]
        if rotulo_anterior == novo_rotulo:
            return

        self._historico.append((nome_interno, rotulo_anterior))
        self._rotulos[nome_interno] = novo_rotulo

    def desfazer(self):
        if not self._historico:
            return False
        nome_interno, rotulo_anterior = self._historico.pop()
        self._rotulos[nome_interno] = rotulo_anterior
        return True

    def registrar_coluna(self, nome_interno, rotulo_inicial=None):
        if nome_interno in self._rotulos:
            return
        self._rotulos[nome_interno] = str(rotulo_inicial) if rotulo_inicial else str(nome_interno)

    def mapeamento_atual(self):
        return dict(self._rotulos)

    def exportar(self, df):
        """
        Exporta o DataFrame. Registra qualquer coluna faltante no momento da exportação.
        """
        for col in df.columns:
            if col not in self._rotulos:
                self.registrar_coluna(col)
        
        return df.rename(columns=self._rotulos)


def sanitizar_rotulo_para_nome_coluna(rotulo):
    texto = unicodedata.normalize('NFKD', str(rotulo))
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^0-9a-zA-Z_]+', '_', texto).strip('_')
    return texto or 'coluna'