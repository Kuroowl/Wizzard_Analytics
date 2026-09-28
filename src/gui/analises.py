"""
Como as análises que viraram canal (botão Add da Nova Amostragem) aparecem
no menu da esquerda: a seção 'Análises do arquivo:' (abaixo de 'Dados do
arquivo:') e as linhas delas dentro da caixa Y: quando estão no gráfico.

Cada uma é um par (x', y') com X próprio: só entra no Y com o mesmo X de
onde veio. Mesma aparência e mesmos gestos das linhas de canal: clicar no
nome põe no Y (ou tira, na caixa Y:), lápis renomeia, lixeira exclui.
"""
from dash import dcc, html

from src.core.operations.amostragem import OPERACOES


def _dica(arquivo, canal):
    partes = [f"Análise (x', y') com {len(canal.serie)} pontos · X = '{arquivo.rotulo(canal.eixo_x)}'."]
    if canal.vinculado and canal.no_origem in arquivo.arvore:
        no = arquivo.arvore.no(canal.no_origem)
        partes.append(f"Vem de '{no.nome}' ({OPERACOES[no.operacao].rotulo}) e acompanha o Recalcular dela.")
    else:
        partes.append('Desvinculada: a análise de origem foi excluída.')
    if arquivo.canal_derivado_desatualizado(canal.nome):
        partes.append('⚠ A origem mudou: recalcule a análise na Nova Amostragem.')
    return '\n'.join(partes)


def linha_analise(arquivo, aba_ativa, nome, id_type_rotulo, dica_clique, em_edicao=None, eixo_x_atual=None):
    """
    UMA linha de análise-canal. 'id_type_rotulo': 'linha-analise' (lista:
    clicar põe no Y) ou 'remover-analise-eixo' (caixa Y: clicar tira).
    'eixo_x_atual': na caixa Y:, se o X do gráfico não for o dela, a linha
    fica apagada (ela não está sendo desenhada).
    """
    canal = arquivo.canal_derivado(nome)
    editando = bool(em_edicao) and em_edicao.get('arquivo') == aba_ativa and em_edicao.get('canal') == nome
    fora_do_x = eixo_x_atual is not None and eixo_x_atual != canal.eixo_x
    classes = 'coluna-item analise' + (' editando' if editando else '') + (' fora-do-x' if fora_do_x else '')
    dica = _dica(arquivo, canal)
    if fora_do_x:
        dica = f"Não desenhada: o X do gráfico não é '{arquivo.rotulo(canal.eixo_x)}'.\n" + dica

    if editando:
        rotulo = dcc.Input(
            id={'type': 'input-editar-analise', 'arquivo': aba_ativa, 'canal': nome},
            type='text', value=canal.rotulo, autoFocus=True, debounce=False,
            className='canal-rotulo-input', maxLength=80,
        )
    else:
        rotulo = html.Button(
            [html.Span('◆', className='canal-analise-marcador'), canal.rotulo,
             html.Span(' ⚠', className='canal-analise-alerta') if arquivo.canal_derivado_desatualizado(nome) else None],
            id={'type': id_type_rotulo, 'arquivo': aba_ativa, 'canal': nome},
            className='canal-rotulo canal-rotulo-btn', title=f'{dica_clique}\n{dica}', n_clicks=0,
        )
    return html.Div(className=classes, children=[
        rotulo,
        html.Button('✏️', id={'type': 'botao-editar-analise', 'arquivo': aba_ativa, 'canal': nome},
                    className='canal-editar-btn', title=f"Renomear '{canal.rotulo}'", n_clicks=0),
        html.Button('🗑', id={'type': 'botao-excluir-analise', 'arquivo': aba_ativa, 'canal': nome},
                    className='canal-lixeira-btn',
                    title=f"Tirar '{canal.rotulo}' de Análises do arquivo (a análise continua na árvore)",
                    n_clicks=0),
    ])


def renderizar_analises_da_aba_ativa(estado, aba_ativa, em_edicao=None):
    """
    Conteúdo de '#lista-analises-aba': título 'Análises do arquivo:' + as
    análises que viraram canal e NÃO estão no Y (as do Y aparecem na caixa
    Y:, como as colunas). Sem nenhuma análise, a seção inteira some.
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    if arquivo is None or not arquivo.canais_derivados:
        return []
    fora_do_y = [n for n in arquivo.canais_derivados if n not in arquivo.eixos_y_derivados]
    if fora_do_y:
        conteudo = html.Div(className='canais-cartao', children=[
            linha_analise(arquivo, aba_ativa, nome, 'linha-analise',
                          'Clique para pôr no eixo Y (precisa do mesmo X de onde veio).', em_edicao)
            for nome in fora_do_y
        ])
    else:
        conteudo = html.Div('todas estão no gráfico', className='analises-vazio')
    return [html.Div('Análises do arquivo:', className='sidebar-secao-titulo'), conteudo]


def linhas_analises_no_y(arquivo, aba_ativa, em_edicao=None):
    """Linhas das análises que estão no Y, pra caixa Y: de renderizar_selecao_eixos."""
    return [
        linha_analise(arquivo, aba_ativa, nome, 'remover-analise-eixo',
                      'Clique para tirar do eixo Y e voltar pra lista.', em_edicao,
                      eixo_x_atual=arquivo.eixo_x_manual)
        for nome in arquivo.eixos_y_derivados if nome in arquivo.canais_derivados
    ]
