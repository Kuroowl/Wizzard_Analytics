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
    embrulha em '$...$' SE 'is_math(texto)' for verdadeiro, e só
    funciona de fato se o componente Graph tiver sido criado com
    'mathjax=True' (ver renderizadores.py). Texto comum (sem sintaxe
    LaTeX detectada) passa direto, sem nenhuma mudança — é assim que
    o texto ORIGINAL fica preservado (não existe conversão permanente
    pra Unicode nem pra nenhuma outra forma: o que está guardado em
    'Canal.rotulo'/'PreferenciasTexto.texto' continua sendo
    exatamente o que o usuário digitou; só na hora de montar a figura
    é que decidimos como apresentar).

    Não faz nada se o texto já vier embrulhado em '$...$' (o usuário
    delimitou na mão) — embrulhar de novo quebraria a sintaxe.
    """
    if not texto:
        return texto
    texto = str(texto)
    if texto.startswith('$') and texto.endswith('$') and len(texto) > 1:
        return texto
    if is_math(texto):
        return f'${texto}$'
    return texto