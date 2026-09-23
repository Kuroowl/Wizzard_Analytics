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

As informações permanentes são pedidas pelos callbacks via
'obter_estado_rodape'. O feedback temporário tem UM único responsável:
o callback 'apresentar_feedback' (registrar_callbacks_rodape, abaixo) —
os outros callbacks só emitem um 'Feedback' (src/gui/feedback.py) no
seu próprio canal e nunca tocam em 'rodape-status', no timer ou na
mensagem seguinte.
"""
from typing import NamedTuple

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from src.gui.feedback import (
    Feedback, ORIGENS_FEEDBACK, TIPO_STORE_FEEDBACK, id_feedback,
)


# Tempo (ms) que uma mensagem "temporária" do mago fica visível antes de
# desaparecer sozinha — ver 'rodape-timer-mensagem' e o callback
# 'apresentar_feedback' logo abaixo.
DURACAO_MENSAGEM_TEMPORARIA_MS = 3500

# Nasce temporária e sem 'depois': some sozinha nos primeiros segundos.
FEEDBACK_INICIAL = Feedback.instrucao('Carregue um arquivo para começar...', temporaria=True)

CLASSE_STATUS = 'rodape-status'


# ============================================================================
# Feedback temporário (mensagem do mago) — apresentação
# ============================================================================

def formatar_fala_do_mago(texto):
    """Único lugar que conhece o formato da fala: 🧙‍♂️: " ... "."""
    return f'🧙‍♂️: " {texto} "' if texto else ''


def classe_status(tipo=None):
    """
    Classe do '#rodape-status' por tipo de feedback ('feedback-sucesso',
    'feedback-erro', ...). Ainda sem regra CSS própria — é o gancho pra
    diferenciar visualmente os tipos quando quiser (status_menu.css).
    """
    return f'{CLASSE_STATUS} feedback-{tipo}' if tipo else CLASSE_STATUS


def _saidas_para(feedback):
    """
    Traduz um Feedback nos 5 Outputs do apresentador:
    (status.children, status.className, timer.disabled,
     timer.n_intervals, mensagem-seguinte.data).
    """
    if feedback is None:
        # Temporária expirou sem 'depois': a mensagem simplesmente some.
        return '', classe_status(), True, no_update, None
    if feedback.texto is None:
        # Feedback.manter(): texto fica, só a troca agendada é cancelada.
        return no_update, no_update, True, no_update, None

    texto = formatar_fala_do_mago(feedback.texto)
    classe = classe_status(feedback.tipo)
    if feedback.temporaria:
        # (Re)arma o timer: n_intervals=0 + disabled=False; o que vem
        # depois fica guardado em 'rodape-mensagem-seguinte'.
        seguinte = feedback.depois.to_plotly_json() if feedback.depois else None
        return texto, classe, False, 0, seguinte
    # Persistente: desarma o timer pra nenhuma troca antiga sobrescrever.
    return texto, classe, True, no_update, None


def _feedback_mais_recente(disparos):
    """
    Entre os canais de feedback que dispararam nesta rodada, devolve o
    emitido por último (maior 'seq'). Normalmente é um só.
    """
    candidatos = []
    for disparo in disparos:
        if TIPO_STORE_FEEDBACK not in disparo.get('prop_id', ''):
            continue
        feedback = Feedback.de_dict(disparo.get('value'))
        if feedback is not None:
            candidatos.append(feedback)
    return max(candidatos, key=lambda f: f.seq) if candidatos else None


def registrar_callbacks_rodape(app):
    """Registra o ÚNICO callback que escreve a mensagem do mago."""

    @app.callback(
        Output('rodape-status', 'children'),
        Output('rodape-status', 'className'),
        Output('rodape-timer-mensagem', 'disabled'),
        Output('rodape-timer-mensagem', 'n_intervals'),
        Output('rodape-mensagem-seguinte', 'data'),
        Input({'type': TIPO_STORE_FEEDBACK, 'origem': ALL}, 'data'),
        Input('rodape-timer-mensagem', 'n_intervals'),
        State('rodape-mensagem-seguinte', 'data'),
        prevent_initial_call=True,
    )
    def apresentar_feedback(_feedbacks, n_intervals, seguinte):
        """
        Dono de 'rodape-status', do timer e da mensagem seguinte.

        - Algum callback emitiu um Feedback -> mostra (e arma/desarma o
          timer conforme ele seja temporário ou persistente).
        - O timer expirou -> mostra o 'depois' guardado (que pode ele
          mesmo ser temporário, encadeando) ou apaga a mensagem.

        Feedback novo tem prioridade sobre expiração na mesma rodada.
        """
        feedback = _feedback_mais_recente(ctx.triggered)
        if feedback is not None:
            return _saidas_para(feedback)

        if ctx.triggered_id == 'rodape-timer-mensagem':
            if not n_intervals:
                raise PreventUpdate
            return _saidas_para(Feedback.de_dict(seguinte))

        raise PreventUpdate


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
                html.Span(id='rodape-status',
                          className=classe_status(FEEDBACK_INICIAL.tipo),
                          children=formatar_fala_do_mago(FEEDBACK_INICIAL.texto)),
            ]),

            # --- Máquina da mensagem temporária do mago ---
            # Só 'apresentar_feedback' escreve nestes três. 'rodape-
            # mensagem-seguinte' guarda o Feedback (dict) que deve aparecer
            # QUANDO a mensagem atual expirar (None = simplesmente some).
            # 'rodape-timer-mensagem' já nasce ativo (disabled=False) pra
            # fazer a mensagem inicial acima desaparecer sozinha nos
            # primeiros segundos, sem precisar de nenhuma ação do usuário.
            dcc.Store(id='rodape-mensagem-seguinte', data=None),
            dcc.Interval(
                id='rodape-timer-mensagem',
                interval=DURACAO_MENSAGEM_TEMPORARIA_MS,
                n_intervals=0,
                max_intervals=1,
                disabled=False,
            ),

            # --- Canais de feedback: um Store por callback escritor ---
            # (ver src/gui/feedback.py). Todos escutados por
            # 'apresentar_feedback' via padrão coringa.
            *[dcc.Store(id=id_feedback(origem)) for origem in ORIGENS_FEEDBACK],
        ]),

        # --- Seção vinculada ao edit menu (painel-direito) ---
        # Vazio por enquanto — reservada pra quando as edições forem
        # implementadas; hoje só acompanha a largura do painel acima.
        html.Div(id='rodape-secao-edit', className='rodape-secao rodape-secao-edit'),
    ])
