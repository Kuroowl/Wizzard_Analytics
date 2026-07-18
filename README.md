# 🧙‍♂️ Wizard Analytics

O **Wizard Analytics** é uma ferramenta em Python desenvolvida para extração, processamento e visualização de dados  arquivos brutos em formatos `TXT` e `CSV`.

## 🚀 Funcionalidades

* **Leitura Inteligente:** Suporte a arquivos de dados brutos (`TXT` e `CSV`).
* **Extração e Limpeza:** Identificação automática de delimitadores e tratamento de dados.
* **Plotagem Avançada:** Geração de gráficos de pressão com opção de destaque de amostras selecionadas (*downsampling*).
* **Exportação:** Salvamento de gráficos em PNG e dados em 'CSV'.

## 📁 Estrutura do Projeto

```text
wizard-analytics/
│
├── src/
│   ├── gui/                    # 1. CAMADA VISUAL (INTERFACE)
│   │   ├── __init__.py
│   │   ├── app.py              # Janela principal do Tkinter
│   │   └── components.py       # Botões, menus e modais personalizados
│   │
│   ├── core/                   # 2. CAMADA DE LÓGICA (OPERAÇÕES E PROCESSAMENTO)
│   │   ├── __init__.py
│   │   ├── extractor.py        # Leitura e limpeza de TXT/CSV (Pandas)
│   │   ├── operations/         # Cálculos matemáticos, filtros, downsampling, merges
|   |   |   |── __init__.py
|   |   |   ├── sampling.py     # Redução de pontos (downsampling, merges)
|   |   |   ├── filters.py      # Filtros matemáticos (média móvel, passa-baixa)
|   |   |   ├── stats.py        # Estatísticas (máximos, mínimos, desvio padrão)
|   |   |   ├── math.py         # Operações matemáticas ( entre dados, derivadas, integrais) 
|   |   |   
│   │   └── plotter/          # Geração dos gráficos (Matplotlib/Seaborn)
|   |   |   |── __init__.py
|   |   |   |── plotter.py
|   |   |   |── other.py
|   |   
│   └── utils/                  # 3. CAMADA DE SUPORTE
│       ├── __init__.py
│       └── helpers.py          # Manipulação de arquivos, salvamento de PDFs, logs
│
├── main.py                     # PONTO DE ENTRADA (O arquivo que dá o "play" no app)
├── .gitignore
└── README.md
