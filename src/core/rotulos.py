import re
import unicodedata


class GerenciadorRotulos:
    """
    Mantém o rótulo de exibição de cada coluna separado do nome interno
    usado pelo resto do pipeline (leitor, operações, ajustes, gráfico).

    Por quê: quando o usuário clica na legenda/título/eixo e renomeia algo
    na interface, isso NUNCA deveria tocar no DataFrame diretamente —
    fórmulas já calculadas (combinar_colunas, derivada_coluna, etc.)
    referenciam o nome interno por string, e continuam válidas mesmo depois
    de qualquer rename. Desfazer também fica trivial: é só reverter o
    rótulo, não precisa desfazer nenhum cálculo.

    Fluxo típico numa interface:
        gerenciador = GerenciadorRotulos(df.columns)
        # usuário clica na legenda "P1" e digita "Pressão de Entrada"
        gerenciador.renomear('P1', 'Pressão de Entrada')
        # o gráfico usa gerenciador.rotulo_atual('P1') pra desenhar a legenda
        # ao exportar:
        df_para_exportar = gerenciador.exportar(df)
    """

    def __init__(self, colunas):
        self._rotulos = {nome: nome for nome in colunas}
        self._historico = []  # pilha de (nome_interno, rotulo_anterior), pra desfazer

    def rotulo_atual(self, nome_interno):
        """O que a interface deve mostrar (na legenda, no eixo, etc.) pra essa coluna."""
        if nome_interno not in self._rotulos:
            raise KeyError(f"Coluna interna '{nome_interno}' não é conhecida por este gerenciador.")
        return self._rotulos[nome_interno]

    def nome_interno(self, rotulo):
        """
        Busca reversa: usada quando o evento de clique na legenda te dá o
        TEXTO exibido, e você precisa descobrir qual coluna de verdade
        (nome interno) isso representa, pra saber o que passar pras funções
        de cálculo.
        """
        for interno, atual in self._rotulos.items():
            if atual == rotulo:
                return interno
        raise KeyError(f"Nenhuma coluna está usando o rótulo '{rotulo}' no momento.")

    def renomear(self, nome_interno, novo_rotulo):
        """
        Muda o rótulo de exibição de uma coluna. Não colide com outro
        rótulo já em uso (mesmo entre nome interno e rótulo de exibição) e
        não aceita rótulo vazio.
        """
        if nome_interno not in self._rotulos:
            raise KeyError(f"Coluna interna '{nome_interno}' não é conhecida por este gerenciador.")

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
                f"O rótulo '{novo_rotulo}' já está em uso pela coluna '{colisao}'. "
                "Escolha um rótulo diferente."
            )

        rotulo_anterior = self._rotulos[nome_interno]
        if rotulo_anterior == novo_rotulo:
            return  # nada mudou, não empilha no histórico

        self._historico.append((nome_interno, rotulo_anterior))
        self._rotulos[nome_interno] = novo_rotulo

    def desfazer(self):
        """Reverte o último rename. Retorna False se não havia nada pra desfazer."""
        if not self._historico:
            return False
        nome_interno, rotulo_anterior = self._historico.pop()
        self._rotulos[nome_interno] = rotulo_anterior
        return True

    def registrar_coluna(self, nome_interno, rotulo_inicial=None):
        """
        Registra uma coluna nova no gerenciador (ex: uma coluna criada
        depois por combinar_colunas ou derivada_coluna, já com o
        GerenciadorRotulos existente). Se a coluna já estiver registrada,
        não faz nada — não sobrescreve um rótulo que o usuário já editou.
        """
        if nome_interno in self._rotulos:
            return
        self._rotulos[nome_interno] = rotulo_inicial if rotulo_inicial else nome_interno

    def mapeamento_atual(self):
        """Cópia do dict {nome_interno: rotulo_atual} — útil pra popular a UI toda de uma vez."""
        return dict(self._rotulos)

    def exportar(self, df):
        """
        Devolve uma CÓPIA do df com as colunas renomeadas para os rótulos
        atuais — isso é o que deve ir pro arquivo exportado, refletindo
        exatamente o que o usuário está vendo na tela no momento.
        """
        desconhecidas = [c for c in df.columns if c not in self._rotulos]
        if desconhecidas:
            raise KeyError(
                f"O DataFrame tem coluna(s) que este gerenciador não conhece: "
                f"{desconhecidas}. Registre-as antes de exportar (com registrar_coluna)."
            )
        return df.rename(columns=self._rotulos)


def sanitizar_rotulo_para_nome_coluna(rotulo):
    """
    Conversão simples de um rótulo 'bonito' (com símbolos, subscritos,
    acentos, espaços — ex: 'Pressão P₁ (bar)') para um nome seguro de usar
    como cabeçalho em formatos mais restritivos, ou quando algum código
    precisar acessar a coluna por atributo (df.coluna).

    NÃO é aplicada automaticamente em GerenciadorRotulos.exportar() — a
    maioria dos formatos (CSV, Excel) aceita Unicode numa boa. Use isso só
    se/quando um formato específico de exportação exigir.
    """
    texto = unicodedata.normalize('NFKD', rotulo)
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^0-9a-zA-Z_]+', '_', texto).strip('_')
    return texto or 'coluna'


if __name__ == '__main__':
    import pandas as pd

    df = pd.DataFrame({'P1': [1, 2, 3], 'P2': [4, 5, 6]})

    print("--- fluxo básico: renomear e ver rótulo atual ---")
    g = GerenciadorRotulos(df.columns)
    print("rótulo inicial de P1:", g.rotulo_atual('P1'))
    g.renomear('P1', 'Pressão de Entrada')
    print("rótulo depois do rename:", g.rotulo_atual('P1'))

    print("\n--- busca reversa: clique na legenda te dá o rótulo, não o nome interno ---")
    print("nome interno de 'Pressão de Entrada':", g.nome_interno('Pressão de Entrada'))

    print("\n--- coluna derivada continua funcionando após o rename (ponto 2) ---")
    df['media_P1_P2'] = (df['P1'] + df['P2']) / 2  # simulando combinar_colunas
    g.registrar_coluna('media_P1_P2')
    print("média calculada com nome interno 'P1', sem se importar com o rótulo:")
    print(df[['P1', 'P2', 'media_P1_P2']])

    print("\n--- colisão de rótulo: deve dar erro claro ---")
    try:
        g.renomear('P2', 'Pressão de Entrada')  # mesmo rótulo que P1 já usa
    except ValueError as e:
        print(f"ValueError capturado corretamente: {e}")

    print("\n--- desfazer (ponto 4): reverte só o rótulo, sem tocar em cálculo nenhum ---")
    print("antes de desfazer:", g.rotulo_atual('P1'))
    g.desfazer()
    print("depois de desfazer:", g.rotulo_atual('P1'))
    print("desfazer de novo (nada no histórico):", g.desfazer())

    print("\n--- exportar: usa o rótulo ATUAL como cabeçalho ---")
    g.renomear('P1', 'Pressão P₁ (bar)')
    df_exportado = g.exportar(df)
    print(df_exportado)

    print("\n--- sanitizar_rotulo_para_nome_coluna (ponto 3) ---")
    print(sanitizar_rotulo_para_nome_coluna('Pressão P₁ (bar)'))
    print(sanitizar_rotulo_para_nome_coluna('ΔT (°C)'))

    print("\n--- erro esperado: exportar com coluna não registrada ---")
    df['coluna_nao_registrada'] = [7, 8, 9]
    try:
        g.exportar(df)
    except KeyError as e:
        print(f"KeyError capturado corretamente: {e}")