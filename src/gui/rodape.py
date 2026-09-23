"""
Rodapé do Wizzard — DONO da apresentação do rodapé.

Tudo que decide COMO o rodapé aparece mora aqui: a árvore de
componentes (montar_rodape), os renderizadores das informações
permanentes (info do arquivo, badge/popup de avisos) e a constante do
temporizador da mensagem do mago.

Os callbacks NÃO devem montar essas peças na mão: eles pedem o estado
pronto via 'obter_estado_rodape(estado, aba_ativa)' e só repassam os
valores pros Outputs.

Conceitualmente o rodapé tem DOIS tipos de informação, que não devem
ser tratados como a mesma coisa:

    Rodapé
    ├── Informações permanentes   -> derivadas do EstadoApp + aba ativa
    │   ├── info do arquivo (ln / col / encoding)
    │   └── avisos (badge + popup)
    │
    └── Feedback temporário       -> mensagem do mago ('rodape-status')
        ├── sucesso / aviso / erro / instrução
        └── temporizador + mensagem seguinte

Por enquanto (Etapa 1) só as informações permanentes foram
centralizadas aqui. O feedback temporário ainda é escrito diretamente
por cada callback em 'rodape-status' — a Etapa 2 introduz o contrato
'Feedback' pra que um único responsável cuide disso.
"""
from typing import NamedTuple

from dash import dcc, html


# Tempo (ms) que uma mensagem "temporária" do mago fica visível antes de
# desaparecer sozinha — ver 'rodape-timer-mensagem' e o callback
# 'expirar_mensagem_temporaria' em callbacks.py.
DURACAO_MENSAGEM_TEMPORARIA_MS = 3500

MENSAGEM_INICIAL = '🧙‍♂️: " Carregue um arquivo para começar... "'


# ============================================================================
# Informações permanentes
# ============================================================================

def _avisos_da_aba(estado, aba_ativa):
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    return arquivo.avisos if arquivo else []


def renderizar_info_rodape(estado, aba_ativa):
    """
    Texto fixo da esquerda do rodapé: 'ln N  col N  [encoding]' da aba
    ativa. Sem arquivo/aba selecionada, mostra um placeholder neutro.
    """
    arquivo = estado.arquivos.get(aba_ativa) if aba_ativa else None
    info = arquivo.info if arquivo else {}

    if not info:
        # ln (5) | col (5) | encoding (10)
        return 'ln ()   col ()    [          ]'

    # Extrai os valores convertendo para string
    n_linhas = str(info.get('n_linhas', '—'))
    n_colunas = str(info.get('n_colunas', '—'))
    encoding = str(info.get('encoding', '—'))

    # <5  -> alinha à esquerda em um espaço reservado de 5 caracteres
    # <10 -> alinha à esquerda em um espaço reservado de 10 caracteres
    return f'ln {n_linhas:<5} col {n_colunas:<5} [{encoding:<10}]'


def renderizar_badge_alerta(estado, aba_ativa):
    """Texto do botão de alerta do rodapé: '⚠ (N)', N = nº de avisos da aba ativa."""
    return f'⚠ ({len(_avisos_da_aba(estado, aba_ativa))})'


def classe_badge_alerta(estado, aba_ativa):
    """
    Classe CSS do botão de alerta: destaca (âmbar) quando a aba ativa tem
    pelo menos 1 aviso pendente, neutro quando não tem nenhum.
    """
    if _avisos_da_aba(estado, aba_ativa):
        return 'rodape-alerta-badge com-avisos'
    return 'rodape-alerta-badge'


def renderizar_popup_alerta(estado, aba_ativa):
    """
    Conteúdo da subjanela (hide/show) que aparece ao clicar no alerta do
    rodapé — lista cada aviso de sanitização gerado no carregamento do
    arquivo da aba ativa (cabeçalho ajustado, linhas descartadas, NaN
    encontrado, amostragem do gráfico, etc.).
    """
    avisos = _avisos_da_aba(estado, aba_ativa)
    if not avisos:
        return [html.Div('Nenhum aviso.', className='rodape-popup-vazio')]
    return [html.Div(aviso, className='rodape-popup-item') for aviso in avisos]


class EstadoRodape(NamedTuple):
    """
    As informações PERMANENTES do rodapé, sempre na mesma ordem dos
    Outputs: ('rodape-info-arquivo', 'children'), ('rodape-alerta-badge',
    'children'), ('rodape-alerta-badge', 'className'),
    ('rodape-alerta-popup', 'children').

    Por ser NamedTuple dá pra usar das duas formas:
      - '*obter_estado_rodape(...)'  -> espalha os 4 valores no return
      - 'r = obter_estado_rodape(...); r.badge_texto' -> pega só o que precisa
    """
    info: object
    badge_texto: str
    badge_classe: str
    popup: list


def obter_estado_rodape(estado, aba_ativa):
    """
    Única porta de entrada dos callbacks pras informações permanentes do
    rodapé (antigo '_valores_rodape' de callbacks.py).
    """
    return EstadoRodape(
        info=renderizar_info_rodape(estado, aba_ativa),
        badge_texto=renderizar_badge_alerta(estado, aba_ativa),
        badge_classe=classe_badge_alerta(estado, aba_ativa),
        popup=renderizar_popup_alerta(estado, aba_ativa),
    )


# ============================================================================
# Layout
# ============================================================================

def montar_rodape(estado):
    """
    Rodapé: 3 seções cujas larguras acompanham a do painel acima delas
    (sidebar / centro / painel-direito) — ver 'habilitarDivisor' em
    scripts_js.py. A vinculação é só de tamanho (puramente visual), não
    de conteúdo.
    """
    inicial = obter_estado_rodape(estado, None)

    return html.Div(className='rodape', children=[

        # --- Seção vinculada ao file menu (sidebar) ---
        html.Div(id='rodape-secao-arquivo', className='rodape-secao rodape-secao-arquivo', children=[
            html.Span(id='rodape-info-arquivo', className='rodape-info',
                      children=inicial.info),

            # Sem separador de texto ' | ' aqui: o alerta agora é
            # empurrado pra ponta direita da seção via
            # 'justify-content: space-between' (ver .rodape-secao-
            # -arquivo em status_menu.css) e a própria borda direita
            # da seção já faz o papel visual do '|' no fim da linha.
            html.Div(id='rodape-alerta-wrapper', className='rodape-alerta-wrapper', children=[
                html.Div(id='rodape-alerta-popup', className='rodape-alerta-popup',
                         children=inicial.popup),
                html.Button(id='rodape-alerta-badge', className=inicial.badge_classe,
                            children=inicial.badge_texto, n_clicks=0),
            ]),
        ]),

        # --- Seção vinculada ao menu central (mensagem do mago) ---
        html.Div(id='rodape-secao-central', className='rodape-secao rodape-secao-central', children=[
            # Camada de fundo do preenchimento de carregamento: ocupa a
            # seção inteira (não só o texto da mensagem), assim mesmo uma
            # mensagem curta como "oi" preenche visualmente a barra toda.
            # A largura é controlada via JS em iniciarBarraCarregamentoRodape().
            html.Div(id='rodape-progresso-central', className='rodape-progresso-central'),

            html.Div(className='rodape-central-conteudo', children=[
                html.Span(id='rodape-status', children=MENSAGEM_INICIAL),
            ]),

            # --- Máquina da mensagem temporária do mago ---
            # 'rodape-mensagem-seguinte' guarda o que deve aparecer QUANDO a
            # mensagem atual expirar (string vazia = simplesmente some).
            # 'rodape-timer-mensagem' já nasce ativo (disabled=False) pra
            # fazer a mensagem inicial acima desaparecer sozinha nos
            # primeiros segundos, sem precisar de nenhuma ação do usuário.
            dcc.Store(id='rodape-mensagem-seguinte', data=''),
            dcc.Interval(
                id='rodape-timer-mensagem',
                interval=DURACAO_MENSAGEM_TEMPORARIA_MS,
                n_intervals=0,
                max_intervals=1,
                disabled=False,
            ),
        ]),

        # --- Seção vinculada ao edit menu (painel-direito) ---
        # Vazio por enquanto — reservada pra quando as edições forem
        # implementadas; hoje só acompanha a largura do painel acima.
        html.Div(id='rodape-secao-edit', className='rodape-secao rodape-secao-edit'),
    ])
