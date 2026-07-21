from dash import html, get_asset_url


def icone(nome_arquivo, tamanho=None):
    """
    Ícone via CSS mask-image: o SVG define só a FORMA, a COR e o TAMANHO vêm
    do CSS (classe .toolbar-icone em icon_menu.css). Assim o tamanho de
    todos os ícones fica controlado num lugar só (o CSS), sem precisar
    mexer em código Python pra ajustar.

    Uso: icone('abrir.svg') dentro de um html.Button/dcc.Upload com classe
    'toolbar-botao' ou 'toolbar-upload' — a cor, o hover e o tamanho já vêm
    de graça do CSS.

    Parâmetros:
        tamanho (int, opcional): só use se ESSE ícone específico precisar
            ser diferente do padrão de .toolbar-icone (sobrescreve via
            estilo inline, que sempre ganha da classe CSS). Deixe None pro
            caso comum, onde o CSS manda.

    Requisito do arquivo: os .svg em src/gui/assets/icones/ precisam ser uma
    forma SÓLIDA PREENCHIDA (fill="#000", sem stroke colorido) — a técnica
    de máscara usa a silhueta/opacidade do desenho; a cor de dentro do
    arquivo é ignorada.
    """
    caminho = get_asset_url(f'icones/{nome_arquivo}')
    estilo = {
        'WebkitMaskImage': f"url({caminho})", 'maskImage': f"url({caminho})",
    }
    if tamanho is not None:
        estilo['width'] = f'{tamanho}px'
        estilo['height'] = f'{tamanho}px'
    return html.Span(className='toolbar-icone', style=estilo)


def icone_colorido(nome_arquivo, tamanho=None):
    """
    Ícone com as CORES ORIGINAIS do arquivo preservadas — ao contrário de
    icone() (que usa mask-image e força uma cor só via CSS), este é um
    <img> comum. Funciona bem pra ícones já coloridos/com gradiente, tipo
    PNGs de verdade.

    Em troca, o hover NÃO recolore (não tem como reconstituir a cor certa
    de forma genérica) — o CSS aplica só uma leve mudança de opacidade.

    Use icone() pra ícones monocromáticos que devem seguir o tema (mudam
    de cor no hover); use icone_colorido() quando o ícone já tem a cor
    certa por si só e você quer preservá-la.
    """
    caminho = get_asset_url(f'icones/{nome_arquivo}')
    estilo = {}
    if tamanho is not None:
        estilo['width'] = f'{tamanho}px'
        estilo['height'] = f'{tamanho}px'
    return html.Img(src=caminho, className='toolbar-icone-colorido', style=estilo)