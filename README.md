# 🧙‍♂️ Wizard Analytics

O **Wizard Analytics** é uma ferramenta em Python (Dash + Plotly) para extração, processamento e visualização de dados de arquivos brutos em formatos `TXT` e `CSV`.

## 🚀 Funcionalidades

* **Leitura inteligente:** arquivos `TXT`/`CSV` com detecção automática de encoding, delimitador, separador decimal e cabeçalho. O que foi ajustado na leitura aparece como aviso no rodapé (⚠).
* **Vários arquivos ao mesmo tempo:** cada arquivo abre numa aba própria.
* **Arquivos com poucos dados:** sem nenhuma coluna numérica (ou sem linhas), o arquivo é recusado com um aviso do mago. Com **uma única** coluna numérica, é criado o **índice** das amostras (`# índice`: 0, 1, 2…) como eixo X — clicar na coluna já manda ela pro Y, e o índice pode ser usado na Nova Análise (ex.: `índice × 0.01` para ter o tempo em segundos). O índice pode ser renomeado, mas não excluído.
* **Gráfico de série temporal:** clique nas colunas da barra lateral para escolher o eixo X e as curvas do eixo Y; renomeie (✏️) ou exclua (🗑) canais.
* **Aparar / Excluir dados:** marque dois pontos no gráfico e mantenha só o trecho entre eles (aparar) ou remova esse trecho (excluir). Durante a seleção o botão fica aceso: clique nele de novo, aperte **Esc** ou use **Cancelar** para desistir.
* **Nova Análise:** calculadora de canais. Monte uma expressão com colunas, números, operadores e funções (`sin`, `√`, derivada, integral, média...) e crie uma coluna nova ou sobrescreva uma existente. A barra de cálculo aparece em cima do gráfico, que continua funcionando normalmente. As análises de "Análises do arquivo" (x′, y′) também entram na calculadora: combinam entre si quando têm o **mesmo x′** (nunca com as colunas da tabela) e geram uma análise nova; sobrescrever o y′ ou o x′ de uma análise a **desvincula** da análise de origem.
* **Painel de edição:** cor, espessura, estilo e marcador de cada curva; títulos, fontes e limites dos eixos; ticks; grade e cor de fundo.
* **Mensagens do mago 🧙‍♂️:** o rodapé mostra o resultado de cada ação e a próxima instrução.
* **Nova Amostragem (em construção):** com um gráfico aberto, liga uma barra de operações em cima do gráfico (Downsampling, Média móvel, Polynomial Fit) e, no painel direito, a árvore de dados/análises dos canais do Y e a configuração da operação. **Preview** desenha o resultado por cima do gráfico sem registrar nada (marcadores no downsampling, linha + faixa ±σ na média móvel, linha tracejada no fit) e mostra o resumo (pontos, janelas, equação e R²). A **origem dos dados** é escolhida clicando na árvore: um canal ou uma análise já registrada (ex.: média móvel → polynomial fit). **Apply** grava o resultado na árvore, desmarca a operação e deixa a análise nova **selecionada** (a próxima operação parte dela) — a mesma análise (mesma origem, operação e parâmetros) não entra duas vezes. Em cada análise, ao passar o mouse: 👁 mostra/esconde no gráfico, ✏️ renomeia, 🗑 exclui (com as que saíram dela e os canais delas no arquivo — pede um 2º clique quando algum está no arquivo). A seção **Análise selecionada** (clicar numa análise na árvore seleciona) tem os detalhes recolhíveis, 👁 Mostrar no gráfico e **Add to file**, que transforma a análise num canal (x', y') em **Análises do arquivo:**, no menu da esquerda: clicar nela põe no eixo Y (só com o mesmo X de onde veio, com barras de erro ±σ na média móvel), ela acompanha o Recalcular da análise de origem e pode ser estilizada no painel "Iniciar edição" (◆ na caixa 'Dado'). A árvore mostra os canais do Y e também os que já têm análises (histórico), mesmo fora do Y. Sair do modo tira o preview e as análises com o olho aceso do gráfico. Se os dados de origem mudarem (corte ou calculadora), os nós ganham ⚠ com **Recalcular** (refaz a cadeia com os mesmos parâmetros; para no passo que não dá, ou pede para conferir o Δx se o X foi reescrito) ou **Manter**. Não fica ligada junto com a Nova Análise.
* **Em desenvolvimento:** fundir arquivos, salvar gráfico e exportar dados.

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
    │   ├── app.py                 # Monta o app Dash (layout + src/callbacks + scripts)
    │   ├── layout.py              # Árvore de componentes da página
    │   ├── renderizadores.py      # Funções puras que constroem o HTML (abas, canais, painel, calculadora...)
    │   ├── amostragem.py          # Barra e painel (árvore + configuração) da Nova Amostragem
    │   ├── analises.py            # 'Análises do arquivo:' (análises que viraram canal pelo Add to file)
    │   ├── rodape.py              # Dono do rodapé: info do arquivo, avisos e a mensagem do mago
    │   ├── feedback.py            # Contrato Feedback: o que o mago deve dizer (sucesso/aviso/erro/instrução)
    │   ├── estado.py              # EstadoApp: arquivos abertos na sessão
    │   ├── components.py          # Ícones
    │   ├── eventos_graficos.py    # Leitura de edições feitas direto no gráfico (título, eixo, legenda) — ainda não ligado
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
    │   ├── __init__.py            # registrar_callbacks(): registra todos os módulos abaixo
    │   ├── _comum.py              # Helpers compartilhados (filtro anti-clique-fantasma, estados da toolbar)
    │   ├── arquivos.py            # Upload de arquivos
    │   ├── abas.py                # Trocar/fechar aba
    │   ├── grafico.py             # Plotar Seleção / fechar gráfico
    │   ├── canais.py              # Eixos X/Y, excluir e renomear canais
    │   ├── corte.py               # Aparar/Excluir dados (seleção, confirmar, cancelar, Esc)
    │   ├── nova_analise.py        # Modo Nova Análise e calculadora de canais
    │   ├── nova_amostragem.py     # Nova Amostragem: modo, origem, Preview, Apply, Add to file, árvore
    │   ├── analises.py            # 'Análises do arquivo:' (pôr/tirar do Y, renomear, excluir)
    │   └── edicao.py              # Painel de edição (curva, eixos, ticks, outros)
    │
    ├── core/                      # 3. LÓGICA: dados e cálculos, sem nada de Dash
    │   ├── arquivo.py             # Arquivo, Canal e preferências; regras de leitura (recusa, índice implícito); corte; árvore de derivados
    │   ├── derivados.py           # Nova Amostragem: Serie (x/y com tamanho próprio) e árvore de proveniência
    │   ├── extractor.py           # Leitura e limpeza de TXT/CSV
    │   ├── rotulos.py             # Rótulo exibido -> nome interno de coluna
    │   ├── operations/
    │   │   ├── calculadora.py     # Avaliação de expressões da Nova Análise
    │   │   ├── sampling.py        # Aparar e excluir dados
    │   │   ├── amostragem.py      # Nova Amostragem: downsampling, média móvel, ajuste polinomial
    │   │   ├── math.py            # Operações entre colunas, derivada, integral, ajustes
    │   │   ├── stats.py           # Estatísticas, histograma, correlação, outliers
    │   │   └── filters.py         # Filtros (ainda vazio)
    │   └── plotting/
    │       └── plotter.py         # Construção da figura Plotly e aplicação das preferências
    │
    └── utils/
        └── helpers.py             # Upload do Dash -> arquivo temporário -> extractor

tests/                             # Testes do core (unittest, sem Dash)
```

### Testes

```bash
python -m unittest discover -s tests -v
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

e é chamado uma vez em `registrar_callbacks()` (`src/callbacks/__init__.py`).

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

Botões que nascem dentro de listas reconstruídas por callbacks (canais, abas, teclado da calculadora) disparam "cliques fantasma" quando a lista é redesenhada. Callbacks que escutam esses botões usam `processar_cliques_padrao` (`src/callbacks/_comum.py`), que só aceita cliques reais.

## 🗺️ Rework em andamento (branch `rework`)

1. ✅ Rodapé e `Feedback`: um único responsável pela mensagem do mago.
2. ✅ Separar o antigo `callbacks.py` (2492 linhas) em `src/callbacks/`, um módulo por área.
3. ✅ Limpeza: código morto, filtro de cliques sem Store, renderização duplicada, regra de dados movida pro `core` (canal calculado, leitura de arquivo com índice implícito).
4. ⏳ Nova Amostragem (branch `NovaAmostragem`): downsampling, média móvel e polynomial fit com Preview, árvore de derivados (Apply) e canal com X próprio (Add to file).
   * ✅ 4.1 Core: `Serie`, árvore de proveniência no `Arquivo`, operações e testes.
   * ✅ 4.2 Core: origem alterada -> ⚠ com **Recalcular** (mesma sequência e parâmetros; para no nó que falha ou cujo Δx precisa de revisão) ou **Manter**; derivado só é exibido com o mesmo X de onde veio.
   * ✅ 4.3 Modo liga/desliga (exclusivo com a Nova Análise; corte, fechar gráfico e trocar aba desligam), barra de operações e painel (árvore + configuração).
   * ✅ 4.4 Preview das três operações (desenho por cima do gráfico, resumo no painel; some ao trocar de operação, desligar o modo, cortar dados ou trocar o X).
   * ✅ 4.5 OK/árvore: registrar, abrir um nó (restaura operação e parâmetros), usar como origem, excluir (com os filhos), ⚠ com Recalcular/Manter e o Recalcular que para pedindo ajuste.
   * ✅ 4.5.1 Revisão: origem só pelo clique na árvore (caixa "Origem dos dados"), olho/lápis/lixeira no hover, análise repetida bloqueada.
   * ✅ 4.5.2 Detalhes da análise recolhíveis (fechados de início) e árvore sem altura fixa; nomes automáticos repetidos numerados.
   * ✅ 4.6 Add: a análise vira um canal (x', y') em "Análises do arquivo:" (menu da esquerda); entra no Y só com o mesmo X; acompanha o Recalcular; ⚠ quando a origem muda; renomear/excluir; excluir a análise da árvore deixa o canal desvinculado.
   * ✅ 4.6.1 Ícones das operações na barra da Nova Amostragem.
   * ✅ 4.7 Calculadora com análises (x′, y′): tokens y′/x′, domínio da expressão (tabela OU análises com o mesmo x′), resultado vira análise nova, sobrescrever desvincula (x′ reescrito é sinalizado).
   * ✅ 4.8 Ajustes: análises no painel de edição (cor/espessura/estilo/marcador), barras de erro ±σ das médias móveis no gráfico, sair do modo apaga os olhos, árvore mostra canais com análises mesmo fora do Y.
   * ✅ 4.9 Análise da calculadora na árvore: conta feita com análises (ex.: média A + média B) vira nó com várias origens, ligado a elas por um braço na árvore; serve de origem para novas análises, o Recalcular refaz a conta depois das origens e excluir uma origem leva a análise junto.
   * ✅ 4.10 Apply / Add to file: OK vira Apply (desmarca a operação e seleciona a análise nova); Add to file sai da configuração para a seção "Análise selecionada" (com 👁 Mostrar no gráfico) e funciona a qualquer momento sobre a análise clicada; excluir na árvore tira do arquivo os canais da cadeia, com confirmação.
5. ⏳ Revisar arquitetura: `allow_duplicate`, `EstadoApp`, renderização excessiva, cache do gráfico.
