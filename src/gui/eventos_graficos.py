"""
Interpreta os eventos que o dcc.Graph do Dash devolve quando o usuário edita
o gráfico (título, rótulo de eixo, texto da legenda). São funções PURAS —
recebem o payload bruto e devolvem só o que mudou, sem tocar em nada — pra
poderem ser testadas sem precisar abrir um navegador de verdade.

IMPORTANTE: o formato exato desses payloads é pouco documentado e pode
variar por versão do Plotly. As implementações abaixo seguem o formato
conhecido/documentado; ao rodar o protótipo de verdade num navegador, vale
conferir no 'log de eventos' se bate — se não bater, é só ajustar as chaves
aqui, o resto do pipeline (rotulos.py, plotter.py) não muda.
"""


def extrair_edicao_titulo(relayout_data):
    """Detecta edição do título geral do gráfico. Retorna o texto novo ou None."""
    if not relayout_data:
        return None
    return relayout_data.get('title.text')


def extrair_edicao_eixo(relayout_data, eixo='xaxis'):
    """Detecta edição do rótulo de um eixo ('xaxis' ou 'yaxis'). Retorna o texto novo ou None."""
    if not relayout_data:
        return None
    return relayout_data.get(f'{eixo}.title.text')


def extrair_edicao_legenda(restyle_data):
    """
    Detecta edição do nome (legenda) de uma trace. O restyleData do Plotly
    vem como uma lista: [dict_de_mudancas, [indices_das_traces_afetadas]].

    Retorna (indice_trace, nome_novo) ou None se não for uma edição de nome
    (restyleData também dispara por outras mudanças, tipo visibilidade).
    """
    if not restyle_data or len(restyle_data) < 2:
        return None

    mudancas, indices = restyle_data[0], restyle_data[1]
    if 'name' not in mudancas:
        return None

    novo_nome = mudancas['name'][0]
    indice_trace = indices[0]
    return indice_trace, novo_nome


if __name__ == '__main__':
    # Exemplos com o formato DOCUMENTADO do Plotly — sem precisar de navegador.
    # Ao rodar o app.py de verdade, comparar com o log de eventos real.

    print("--- edição de título ---")
    exemplo_titulo = {'title.text': 'Ensaio MESO Q300'}
    print(extrair_edicao_titulo(exemplo_titulo))

    print("\n--- edição de rótulo do eixo X ---")
    exemplo_eixo = {'xaxis.title.text': 'Tempo decorrido (s)'}
    print(extrair_edicao_eixo(exemplo_eixo, 'xaxis'))

    print("\n--- relayout que NÃO é edição de rótulo (ex: zoom) ---")
    exemplo_zoom = {'xaxis.range[0]': 1.2, 'xaxis.range[1]': 5.8}
    print("título:", extrair_edicao_titulo(exemplo_zoom))
    print("eixo x:", extrair_edicao_eixo(exemplo_zoom, 'xaxis'))

    print("\n--- edição de legenda (nome da trace 0) ---")
    exemplo_legenda = [{'name': ['Pressão de Entrada']}, [0]]
    print(extrair_edicao_legenda(exemplo_legenda))

    print("\n--- restyleData que NÃO é edição de nome (ex: toggle de visibilidade) ---")
    exemplo_visibilidade = [{'visible': ['legendonly']}, [1]]
    print(extrair_edicao_legenda(exemplo_visibilidade))