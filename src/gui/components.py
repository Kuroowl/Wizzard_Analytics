from dash import html, get_asset_url


def icone(nome_arquivo, tamanho=14):
    """
    Ícone via CSS mask-image: o SVG define só a FORMA, a COR vem do CSS
    (classe .toolbar-icone / :hover em estilo.css). Assim o hover muda a cor
    do ícone só trocando uma variável CSS, sem precisar de um arquivo
    colorido pra cada estado.

    Uso: icone('abrir.svg') dentro de um html.Button/dcc.Upload com classe
    'toolbar-botao' ou 'toolbar-upload' — a cor e o hover já vêm de graça.

    Requisito do arquivo: os .svg em src/gui/assets/icones/ precisam ser uma
    forma SÓLIDA PREENCHIDA (fill="#000", sem stroke colorido) — a técnica
    de máscara usa a silhueta/opacidade do desenho; a cor de dentro do
    arquivo é ignorada.
    """
    caminho = get_asset_url(f'icones/{nome_arquivo}')
    return html.Span(className='toolbar-icone', style={
        'width': f'{tamanho}px', 'height': f'{tamanho}px',
        'WebkitMaskImage': f"url({caminho})", 'maskImage': f"url({caminho})",
    })
