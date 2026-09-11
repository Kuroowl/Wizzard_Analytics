import re
import unicodedata

# GerenciadorRotulos foi removido daqui: sua responsabilidade (rótulo +
# histórico de rename por coluna) agora é da classe Canal, dentro de
# src/core/arquivo.py — porque o rótulo de uma coluna e seu ciclo de
# vida (original/calculado, visível/oculto/excluído) são parte da MESMA
# entidade, não duas estruturas soltas que precisavam ser sincronizadas
# manualmente.


def sanitizar_rotulo_para_nome_coluna(rotulo):
    texto = unicodedata.normalize('NFKD', str(rotulo))
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^0-9a-zA-Z_]+', '_', texto).strip('_')
    return texto or 'coluna'


# --- Texto livre com LaTeX/MathText (título do gráfico, título dos
# eixos, nome de colunas na legenda) ------------------------------
#
# Não é uma classe 'TextManager' à parte (o app inteiro é function-
# based, não OO — ver plotter.py/calculadora.py) — 'sanitizar_rotulo_
# para_nome_coluna' acima já cobre o papel de 'sanitize()' (produz um
# nome_interno seguro pro DataFrame a partir do que o usuário digitou,
# incluindo sintaxe LaTeX — '\','{','}' já viram '_' hoje, mesmo sem
# 'saber' que é LaTeX). 'is_math'/'renderizar_texto_grafico' abaixo
# são os dois que faltavam: detectar se um texto é LaTeX, e preparar
# ele pro Plotly renderizar de verdade.
#
# ESCOPO ATUAL (decisão explícita): só dentro do GRÁFICO (título,
# título dos eixos, nome das curvas na legenda — ver dcc.Graph(
# mathjax=True) em renderizadores.py e o uso de renderizar_texto_
# grafico em plotter.py). A lista 'Dados do arquivo:', os botões da
# calculadora, o dropdown 'Dado:' no painel de edição — são HTML puro,
# sem MathJax nenhum ligado ali; o rótulo aparece cru nesses lugares
# (ex: 'P_{12}' literal, sem virar subscrito) — fora de escopo por
# enquanto, pode ser um próximo passo separado.
#
# LIMITAÇÃO DO PRÓPRIO PLOTLY (não é algo que dá pra contornar em
# Python): quando o MathJax encontra '$...$' num campo de texto, TUDO
# que estiver FORA dos delimitadores é ignorado — não dá pra misturar
# texto normal e LaTeX no MESMO campo (ex: 'ΔP (kPa)' com só o 'ΔP'
# em LaTeX perderia o '(kPa)' na hora de desenhar). Por isso
# 'renderizar_texto_grafico' embrulha o texto INTEIRO ou não embrulha
# nada — nunca uma mistura.

_PADRAO_LATEX = re.compile(r'\\[a-zA-Z]+|[_^]\{')


def is_math(texto):
    """
    Heurística: este texto parece conter sintaxe LaTeX/MathText?

    Dispara em duas situações, escolhidas de propósito pra NÃO
    confundir nomes de coluna comuns (ex: 'Tempo_decorrido_s',
    'pressure_12', que têm underscore mas não são LaTeX nenhum) com
    matemática de verdade:
      1. Um comando LaTeX (barra invertida + letras: '\\delta',
         '\\Delta', '\\frac', '\\infty'...) — barra invertida
         praticamente nunca aparece em texto/nome de coluna comum,
         então é um sinal forte e seguro.
      2. Sub/sobrescrito com CHAVES explícitas ('_{' ou '^{', ex:
         'P_{12}') — deliberadamente NÃO dispara em '_' ou '^' soltos
         seguidos de letra/número sem chave (isso pegaria QUALQUER
         nome de coluna com underscore, o que seria um falso positivo
         em massa). Um '_x' sem chave só vira matemática aqui se vier
         acompanhado de um comando (regra 1), como em 'T_\\infty'.

    Também reconhece um texto que o próprio usuário já embrulhou em
    '$...$' manualmente — nesse caso é matemática por definição, sem
    precisar bater nenhum dos padrões acima.
    """
    if not texto:
        return False
    texto = str(texto)
    if texto.startswith('$') and texto.endswith('$') and len(texto) > 1:
        return True
    return bool(_PADRAO_LATEX.search(texto))


def renderizar_texto_grafico(texto):
    """
    Prepara um texto (título do gráfico, título de eixo, rótulo de
    coluna) pro Plotly renderizar como LaTeX quando fizer sentido —
    RENDERER da arquitetura TextManager -> TextParser -> Renderer.

    Diferente da v1 (que classificava o texto INTEIRO como "é tudo
    matemática" ou "não é nada"): o Plotly troca de comportamento na
    hora que encontra QUALQUER '$...$' — tudo que estiver fora dos
    delimitadores é descartado (bug conhecido/documentado do próprio
    Plotly.js, não algo que dava pra contornar então). Um texto como
    'differential pressure, \\Delta P_{12}' virava TUDO matemática
    (a vírgula/espaço/palavras comuns iam pro modo matemático junto,
    resultado ilegível) — pedido explícito pra corrigir: fragmentar,
    não tratar como bloco único.

    Agora '_fragmentar_texto' (abaixo) quebra o texto em pedaços
    comuns e matemáticos, e cada pedaço COMUM vira um bloco '\\text
    {...}' DENTRO de uma única expressão matemática — differente de
    tentar vários pares de '$...$' soltos (que é exatamente o que o
    Plotly não suporta bem, ver docstring de _fragmentar_texto): como
    tudo fica dentro de UM SÓ par de '$...$', o Plotly nunca perde
    texto nenhum, e '\\text{}' é o comando padrão do LaTeX pra
    escrever texto comum (fonte reta, não itálico de variável) DENTRO
    do modo matemático — é assim que o resultado final ainda parece
    "texto normal, com uma fórmula no meio", que é o que o usuário via
    numa ferramenta LaTeX de verdade.

    Sem NENHUM pedaço reconhecido como matemática, devolve o texto
    ORIGINAL sem tocar em nada (nem embrulha em '$...$' à toa).
    """
    if not texto:
        return texto
    texto = str(texto)
    if texto.startswith('$') and texto.endswith('$') and len(texto) > 1:
        return texto

    partes = _fragmentar_texto(texto)
    if not any(tipo == 'math' for tipo, _ in partes):
        return texto

    pedacos_finais = []
    for tipo, pedaco in partes:
        if tipo == 'math':
            pedacos_finais.append(pedaco)
        else:
            # Escapa só '{'/'}' (os únicos caracteres que quebrariam o
            # balanceamento do '\text{...}' se aparecessem soltos num
            # trecho comum) — o resto do texto comum passa intacto.
            pedaco_seguro = pedaco.replace('{', r'\{').replace('}', r'\}')
            pedacos_finais.append('\\text{' + pedaco_seguro + '}')
    return '$' + ''.join(pedacos_finais) + '$'


_SEPARADOR_CLAUSULA = re.compile(r'([,;]\s*)')


def _fragmentar_texto(texto):
    """
    TextParser da arquitetura TextManager -> TextParser -> Renderer:
    quebra 'texto' numa lista de (tipo, pedaço) — tipo 'math' ou
    'plain' — SEM decidir isso pro texto inteiro de uma vez.

    Corta nas VÍRGULAS/PONTOS-E-VÍRGULA (não em cada espaço/palavra):
    uma expressão como '\\Delta P_{12}' — ou até só '\\Delta P', um
    dos exemplos originais — tem VÁRIAS palavras que precisam ficar
    JUNTAS no mesmo bloco matemático; cortar em todo espaço quebraria
    isso ao meio (o '\\Delta' sozinho reconhecido como matemática, o
    'P' sozinho — sem comando LaTeX nem chave — caindo como texto
    comum por engano). A vírgula, em compensação, é o separador
    natural que o próprio usuário já usa pra separar "descrição
    solta" de "fórmula" (ex: 'differential pressure, \\Delta P_{12}',
    caso relatado) — cada trecho ENTRE vírgulas é classificado como
    UM BLOCO com 'is_math()', não palavra por palavra.

    Pedaços ADJACENTES do MESMO tipo são unidos num só (preservando a
    vírgula/espaço original entre eles) — evita fragmentar à toa uma
    frase inteiramente comum, ou uma fórmula com vírgula interna.
    """
    brutos = _SEPARADOR_CLAUSULA.split(texto)
    # 'brutos' alterna: cláusula, separador (',' ou ';' + espaços
    # seguintes, capturados JUNTOS pelo grupo), cláusula, separador...
    # — índices pares são cláusulas, ímpares são separadores.
    partes = []
    tipo_atual = None
    buffer = ''
    for indice, pedaco in enumerate(brutos):
        if not pedaco:
            continue
        if indice % 2 == 1:
            # Separador — sempre cola no bloco ANTERIOR (não abre um
            # bloco novo sozinho, e não decide tipo nenhum).
            buffer += pedaco
            continue
        tipo = 'math' if is_math(pedaco) else 'plain'
        if tipo != tipo_atual:
            if buffer:
                partes.append((tipo_atual, buffer))
            buffer = pedaco
            tipo_atual = tipo
        else:
            buffer += pedaco
    if buffer:
        partes.append((tipo_atual, buffer))
    return partes