# 🧙‍♂️ Wizard Analytics

O **Wizard Analytics** é uma ferramenta em Python (Dash + Plotly) para extração, processamento e visualização de dados de arquivos brutos em formatos `TXT` e `CSV`.

## 🚀 Funcionalidades

* **Leitura inteligente:** arquivos `TXT`/`CSV` com detecção automática de encoding, delimitador, separador decimal e cabeçalho. O que foi ajustado na leitura aparece como aviso no rodapé (⚠).
* **Vários arquivos ao mesmo tempo:** cada arquivo abre numa aba própria.
* **Gráfico de série temporal:** clique nas colunas da barra lateral para escolher o eixo X e as curvas do eixo Y; renomeie (✏️) ou exclua (🗑) canais.
* **Aparar / Excluir dados:** marque dois pontos no gráfico e mantenha só o trecho entre eles (aparar) ou remova esse trecho (excluir). Durante a seleção o botão fica aceso: clique nele de novo, aperte **Esc** ou use **Cancelar** para desistir.
* **Nova Análise:** calculadora de canais. Monte uma expressão com colunas, números, operadores e funções (`sin`, `√`, derivada, integral, média...) e crie uma coluna nova ou sobrescreva uma existente. A barra de cálculo aparece em cima do gráfico, que continua funcionando normalmente.
* **Painel de edição:** cor, espessura, estilo e marcador de cada curva; títulos, fontes e limites dos eixos; ticks; grade e cor de fundo.
* **Mensagens do mago 🧙‍♂️:** o rodapé mostra o resultado de cada ação e a próxima instrução.
* **Em desenvolvimento:** Nova Amostragem, fundir arquivos, salvar gráfico e exportar dados.

## ▶️ Como executar

Requer Python 3.10+.

```bash
pip install dash pandas numpy plotly scipy
python main.py
```

Depois abra <http://127.0.0.1:8050> no navegador. Rode a partir da raiz do repositório (os imports usam `src.`).

## 🏛️ Arquitetura

O código é dividido pela pergunta que cada parte responde:

| Pergunta | Camada | Exemplos |
|---|---|---|
| **Como isso aparece?** | `src/gui/` | `renderizar_painel_edicao()`, `layout.py` |
| **O que acontece quando o usuário clica?** | `src/callbacks/` | `iniciar_selecao_corte()`, `criar_canal_calculado_calculadora()` |
| **Como o dado é processado?** | `src/core/` | `aparar_dados()`, `avaliar_expressao_calculadora()` |
| **Qual mensagem o usuário recebe?** | `src/gui/feedback.py` + `src/gui/rodape.py` | `Feedback.sucesso("Canal criado.")` |

```text
 USUÁRIO ──► GUI (layout, renderizadores) ──► CALLBACKS (orquestração) ──► CORE (dados, cálculos)
                          ▲                             │
                          └──── Feedback ──► rodapé ◄───┘
```

Um callback deve só **traduzir** "o usuário clicou nisso" em "execute esta operação" (no `core`) e depois "mostre o resultado" (renderizadores + `Feedback`). Cálculo e regra de dados não moram no callback.

## 📁 Estrutura do Projeto

```text
Wizzard_Analytics/
│
├── main.py                        # PONTO DE ENTRADA: cria o EstadoApp e sobe o app
│
└── src/
    ├── gui/                       # 1. INTERFACE: como as coisas aparecem
    │   ├── app.py                 # Monta o app Dash (layout + callbacks + scripts)
    │   ├── callbacks.py           # Índice: registra todos os módulos de src/callbacks/
    │   ├── layout.py              # Árvore de componentes da página
    │   ├── renderizadores.py      # Funções puras que constroem o HTML (abas, canais, painel, calculadora...)
    │   ├── rodape.py              # Dono do rodapé: info do arquivo, avisos e a mensagem do mago
    │   ├── feedback.py            # Contrato Feedback: o que o mago deve dizer (sucesso/aviso/erro/instrução)
    │   ├── estado.py              # EstadoApp: arquivos abertos na sessão
    │   ├── components.py          # Ícones
    │   ├── eventos_graficos.py    # Leitura de edições feitas direto no gráfico (título, eixo, legenda)
    │   ├── scripts_js.py          # JavaScript da página (divisores, clique no gráfico, Esc, barras de progresso)
    │   └── assets/
    │       ├── estilo.css
    │       ├── icones/
    │       └── menus/
    │           ├── central_menu.css   # Área central (gráfico e barra de cálculo)
    │           ├── edit_menu.css      # Painel de edição (direita) e teclado da calculadora
    │           ├── file_menu.css      # Barra lateral (abas e colunas)
    │           ├── icon_menu.css      # Toolbar de ícones
    │           ├── status_menu.css    # Rodapé
    │           └── top_menu.css       # Menu superior (Arquivo, Editar, Ajuda)
    │
    ├── callbacks/                 # 2. ORQUESTRAÇÃO: o que acontece quando o usuário interage
    │   ├── _comum.py              # Helpers compartilhados (filtro anti-clique-fantasma, estados da toolbar)
    │   ├── arquivos.py            # Upload de arquivos
    │   ├── abas.py                # Trocar/fechar aba
    │   ├── grafico.py             # Plotar Seleção / fechar gráfico
    │   ├── canais.py              # Eixos X/Y, excluir e renomear canais
    │   ├── corte.py               # Aparar/Excluir dados (seleção, confirmar, cancelar, Esc)
    │   ├── nova_analise.py        # Modo Nova Análise e calculadora de canais
    │   ├── nova_amostragem.py     # Nova Amostragem (em definição)
    │   └── edicao.py              # Painel de edição (curva, eixos, ticks, outros)
    │
    ├── core/                      # 3. LÓGICA: dados e cálculos, sem nada de Dash
    │   ├── arquivo.py             # Arquivo, Canal e preferências de gráfico
    │   ├── extractor.py           # Leitura e limpeza de TXT/CSV
    │   ├── rotulos.py             # Rótulo exibido -> nome interno de coluna
    │   ├── operations/
    │   │   ├── calculadora.py     # Avaliação de expressões da Nova Análise
    │   │   ├── sampling.py        # Aparar, excluir e amostrar dados
    │   │   ├── math.py            # Operações entre colunas, derivada, integral, ajustes
    │   │   ├── stats.py           # Estatísticas, histograma, correlação, outliers
    │   │   ├── other.py           # Ajustes de curva
    │   │   └── filters.py         # Filtros (ainda vazio)
    │   └── plotting/
    │       └── plotter.py         # Construção da figura Plotly e aplicação das preferências
    │
    └── utils/
        └── helpers.py             # Upload do Dash -> arquivo temporário -> extractor
```

## 🧩 Convenções

### Adicionar callbacks

Cada área tem um módulo em `src/callbacks/` com uma função de registro:

```python
# src/callbacks/nova_amostragem.py
def registrar_callbacks_nova_amostragem(app, estado):

    @app.callback(...)
    def aplicar_media_movel(...):
        resultado = media_movel(df, ...)   # o cálculo mora em src/core/
        ...
```

e é chamado uma vez no índice (`src/gui/callbacks.py`).

### Falar com o usuário (mensagem do mago)

Nenhum callback escreve em `rodape-status`. Ele emite um `Feedback` no **seu próprio canal**, e o rodapé cuida de formatar, temporizar e trocar a mensagem:

```python
from src.gui.feedback import Feedback, saida_feedback

@app.callback(
    ...,
    saida_feedback('amostragem'),   # registre 'amostragem' em ORIGENS_FEEDBACK (feedback.py)
    ...
)
def aplicar_media_movel(...):
    ...
    return ..., Feedback.sucesso(f'Média móvel aplicada. {n} pontos gerados.'), ...
```

* Tipos: `info`, `sucesso`, `aviso`, `erro`, `instrucao`.
* Mensagem temporária seguida de uma instrução: `Feedback.sucesso('Arquivo carregado!', depois=Feedback.instrucao('Escolha uma opção de gráfico...'))`.
* Cada origem tem um único escritor: se dois callbacks usarem a mesma origem, o Dash acusa o erro ao iniciar.

### Botões dentro de listas redesenhadas

Botões que nascem dentro de listas reconstruídas por callbacks (canais, abas, teclado da calculadora) disparam "cliques fantasma" quando a lista é redesenhada. Callbacks que escutam esses botões usam `_processar_cliques_padrao` (`src/callbacks/_comum.py`), que só aceita cliques reais.

## 🗺️ Rework em andamento (branch `rework`)

1. ✅ Rodapé e `Feedback`: um único responsável pela mensagem do mago.
2. 🔄 Separar o antigo `callbacks.py` em `src/callbacks/`. Falta mover o índice para `src/callbacks/__init__.py`.
3. ⏳ Limpar cada módulo: callback só orquestra, lógica vai para o `core`.
4. ⏳ Nova Amostragem (downsample, média móvel, ajuste polinomial).
5. ⏳ Revisar arquitetura: `allow_duplicate`, `EstadoApp`, renderização excessiva, cache do gráfico.
