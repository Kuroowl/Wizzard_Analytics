SCRIPT_DIVISORIA = r"""
<script>
// Conversores HSV<->RGB do seletor de cor (ver _seletor_cor em
// renderizadores.py). Ficam FORA do DOMContentLoaded, presos em
// 'window', porque duas partes independentes precisam deles: o
// arraste do mouse aqui embaixo (iniciarSeletorCor) E o
// app.clientside_callback registrado em callbacks.py (que roda em
// outro momento, disparado pelo Dash, não por este listener).
window.wizzardCor = {
    hsvParaRgb: function (h, s, v) {
        h = ((h % 360) + 360) % 360;
        var c = v * s;
        var x = c * (1 - Math.abs((h / 60) % 2 - 1));
        var m = v - c;
        var rp, gp, bp;
        if (h < 60) { rp = c; gp = x; bp = 0; }
        else if (h < 120) { rp = x; gp = c; bp = 0; }
        else if (h < 180) { rp = 0; gp = c; bp = x; }
        else if (h < 240) { rp = 0; gp = x; bp = c; }
        else if (h < 300) { rp = x; gp = 0; bp = c; }
        else { rp = c; gp = 0; bp = x; }
        return {
            r: Math.round((rp + m) * 255),
            g: Math.round((gp + m) * 255),
            b: Math.round((bp + m) * 255),
        };
    },
    rgbParaHsv: function (r, g, b) {
        r /= 255; g /= 255; b /= 255;
        var max = Math.max(r, g, b), min = Math.min(r, g, b);
        var delta = max - min;
        var h = 0;
        if (delta !== 0) {
            if (max === r) h = 60 * (((g - b) / delta) % 6);
            else if (max === g) h = 60 * (((b - r) / delta) + 2);
            else h = 60 * (((r - g) / delta) + 4);
        }
        if (h < 0) h += 360;
        var s = max === 0 ? 0 : delta / max;
        var v = max;
        return { h: h, s: s, v: v };
    },
};

document.addEventListener('DOMContentLoaded', function () {
    // Liga um divisor arrastável (elemento com a classe '.divisor-resize') a
    // um painel-alvo, cujo 'width' é atualizado ao vivo durante o arraste.
    // 'rodapeAlvo', se passado, recebe exatamente a mesma largura em cada
    // movimento — é assim que a seção do rodapé fica "vinculada ao tamanho"
    // do painel de cima, sem precisar de nenhum acoplamento de conteúdo.
    // 'calcularLargura(e)' decide a direção do cálculo (painel à esquerda
    // do cursor cresce com clientX crescente; painel à direita é o oposto).
    function habilitarDivisor(divisorId, painelAlvo, rodapeAlvo, larguraMin, larguraMax, calcularLargura) {
        var divisor = document.getElementById(divisorId);
        if (!divisor || !painelAlvo) return;

        var arrastando = false;

        divisor.addEventListener('mousedown', function (e) {
            arrastando = true;
            divisor.classList.add('arrastando');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', function (e) {
            if (!arrastando) return;
            var novaLargura = calcularLargura(e);
            novaLargura = Math.max(larguraMin, Math.min(larguraMax, novaLargura));
            painelAlvo.style.width = novaLargura + 'px';
            if (rodapeAlvo) rodapeAlvo.style.width = novaLargura + 'px';
        });

        document.addEventListener('mouseup', function () {
            if (!arrastando) return;
            arrastando = false;
            divisor.classList.remove('arrastando');
            document.body.style.cursor = 'default';
            document.body.style.userSelect = 'auto';
        });
    }

    function iniciar() {
        var sidebar = document.querySelector('.sidebar');
        var painelDireito = document.querySelector('.painel-direito');
        var rodapeArquivo = document.getElementById('rodape-secao-arquivo');
        var rodapeEdit = document.getElementById('rodape-secao-edit');

        if (!sidebar || !painelDireito || !rodapeArquivo || !rodapeEdit) {
            setTimeout(iniciar, 300);
            return;
        }

        // Divisor esquerdo: sidebar (file menu) <-> centro.
        // Cresce pra direita conforme o cursor se afasta da borda esquerda
        // fixa da sidebar.
        habilitarDivisor('divisor-resize', sidebar, rodapeArquivo, 200, 600, function (e) {
            return e.clientX - sidebar.getBoundingClientRect().left;
        });

        // Divisor direito: centro <-> painel-direito (edit menu).
        // O painel fica encostado na borda direita da janela, que não se
        // move — então a largura cresce conforme o cursor se afasta DELA
        // pra esquerda (direção oposta ao divisor da sidebar).
        // larguraMin = 300 (era 260) — precisa bater com o 'min-width'
        // de '.painel-direito' em edit_menu.css: abaixo disso a linha
        // 'Limits' (min/max + autoscale + cadeado, ver
        // _linha_limite_eixo em renderizadores.py) já não cabe sem
        // comprimir. Os dois valores (aqui e no CSS) precisam ficar
        // sincronizados manualmente — não há uma fonte única
        // compartilhada entre JS e CSS neste projeto.
        habilitarDivisor('divisor-resize-edit', painelDireito, rodapeEdit, 300, 560, function (e) {
            return painelDireito.getBoundingClientRect().right - e.clientX;
        });

        // Sincroniza a largura inicial das seções do rodapé com a dos
        // painéis assim que tudo estiver montado, caso os valores padrão
        // definidos em CSS (280px / 260px) algum dia se desalinhem.
        rodapeArquivo.style.width = sidebar.getBoundingClientRect().width + 'px';
        rodapeEdit.style.width = painelDireito.getBoundingClientRect().width + 'px';
    }
    iniciar();

    function iniciarNavegacaoAbas() {
        var container = document.getElementById('container-abas-chrome');
        var btnEsquerda = document.getElementById('aba-nav-esquerda');
        var btnDireita = document.getElementById('aba-nav-direita');
        if (!container || !btnEsquerda || !btnDireita) {
            setTimeout(iniciarNavegacaoAbas, 300);
            return;
        }

        var MARGEM = 2;

        function atualizarSetas() {
            var temOverflow = container.scrollWidth > container.clientWidth + MARGEM;
            var podeVoltar = container.scrollLeft > MARGEM;
            var podeAvancar = container.scrollLeft < (container.scrollWidth - container.clientWidth - MARGEM);

            btnEsquerda.classList.toggle('visivel', temOverflow && podeVoltar);
            btnDireita.classList.toggle('visivel', temOverflow && podeAvancar);
        }

        function larguraDeUmaAba() {
            var primeiraAba = container.querySelector('.aba-chrome');
            return primeiraAba ? primeiraAba.getBoundingClientRect().width : 120;
        }

        btnEsquerda.addEventListener('click', function () {
            container.scrollBy({ left: -larguraDeUmaAba(), behavior: 'smooth' });
        });
        btnDireita.addEventListener('click', function () {
            container.scrollBy({ left: larguraDeUmaAba(), behavior: 'smooth' });
        });

        container.addEventListener('scroll', atualizarSetas);
        window.addEventListener('resize', atualizarSetas);

        new MutationObserver(atualizarSetas).observe(container, { childList: true });

        atualizarSetas();
    }
    iniciarNavegacaoAbas();

    function iniciarAlertaRodape() {
        // Delegação no 'document' (em vez de pegar o elemento e grudar o
        // listener nele) porque o conteúdo do badge/popup é reescrito pelo
        // Dash a cada callback (children/className mudam) — um listener
        // preso direto no nó corre risco de sumir junto se o Dash trocar o
        // nó por um novo. Delegar no document nunca perde o gancho.
        document.addEventListener('click', function (e) {
            var badge = e.target.closest && e.target.closest('#rodape-alerta-badge');
            var popup = document.getElementById('rodape-alerta-popup');
            if (!popup) return;

            if (badge) {
                popup.classList.toggle('aberta');
                e.stopPropagation();
                return;
            }

            // Clique fora do popup (e fora do badge, já tratado acima):
            // fecha se estiver aberto.
            if (popup.classList.contains('aberta') && !e.target.closest('#rodape-alerta-popup')) {
                popup.classList.remove('aberta');
            }
        });
    }
    iniciarAlertaRodape();

    function iniciarSeletorCor() {
        // Abre/fecha o painel flutuante ao clicar na caixinha — mesma
        // técnica de delegação de 'iniciarAlertaRodape' logo acima: o
        // card 'Curva' inteiro (com o seletor dentro) é recriado toda
        // vez que o usuário troca de aba ou reabre a edição, então um
        // listener preso direto no nó se perderia.
        document.addEventListener('click', function (e) {
            var caixa = e.target.closest && e.target.closest('.cor-picker-caixa');
            var painelAberto = document.querySelector('.cor-picker-painel.aberto');

            if (caixa) {
                var painel = caixa.parentElement.querySelector('.cor-picker-painel');
                var jaAberto = painel.classList.contains('aberto');
                if (painelAberto && painelAberto !== painel) painelAberto.classList.remove('aberto');
                painel.classList.toggle('aberto', !jaAberto);
                e.stopPropagation();
                return;
            }

            if (painelAberto && !e.target.closest('.cor-picker-painel')) {
                painelAberto.classList.remove('aberto');
            }
        });

        // Escreve um novo valor num dos 3 campos R/G/B disparando um
        // evento 'input' nativo — é assim que o Dash (que escuta o DOM,
        // não só cliques do React) percebe a mudança e roda
        // 'sincronizar_cor_rgb' em callbacks.py, sem precisar de nenhum
        // componente Dash "escondido" só pra fazer essa ponte.
        function definirCampoRgb(elemento, valor) {
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(elemento, valor);
            elemento.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function aplicarRgb(wrapper, h, s, v) {
            // Busca os 3 campos pela ORDEM em que nascem dentro do wrapper
            // (R, G, B — ver _campo_rgb x3 em _seletor_cor, renderizadores.py),
            // não mais por id fixo: desde que _seletor_cor passou a aceitar
            // um 'prefixo' (pode existir mais de um seletor de cor no
            // painel, ex: cor da 'Curva' e cor de fundo em 'Outros'), os
            // ids de cada campo variam por instância — só a ORDEM é garantida.
            var rgb = window.wizzardCor.hsvParaRgb(h, s, v);
            wrapper.dataset.hue = h;
            wrapper.dataset.sat = s;
            wrapper.dataset.val = v;

            // '.cor-picker-input' é a DIV que embrulha o <input> de
            // verdade (+ os botões de stepper +/- que essa versão do
            // dash-core-components desenha em volta de todo
            // dcc.Input(type='number')) — setar '.value' diretamente
            // nessa DIV lança 'Illegal invocation' (não é um
            // HTMLInputElement) e aborta a função pela metade, silen-
            // ciosamente: o clique/arraste na área/matiz parava de
            // fazer efeito nenhum, mas digitar direto no campo
            // continuava funcionando (isso não passa por aqui, é
            // digitação nativa do navegador). Por isso o 'input' de
            // verdade, dentro dela.
            var campos = wrapper.querySelectorAll('.cor-picker-input input');
            if (campos[0]) definirCampoRgb(campos[0], rgb.r);
            if (campos[1]) definirCampoRgb(campos[1], rgb.g);
            if (campos[2]) definirCampoRgb(campos[2], rgb.b);
        }

        var arrastandoArea = null;
        var arrastandoHue = null;

        document.addEventListener('mousedown', function (e) {
            var area = e.target.closest && e.target.closest('.cor-picker-area');
            var hue = e.target.closest && e.target.closest('.cor-picker-hue');

            if (area) {
                arrastandoArea = area;
                moverNaArea(area, e);
                e.preventDefault();
            } else if (hue) {
                arrastandoHue = hue;
                moverNoHue(hue, e);
                e.preventDefault();
            }
        });

        document.addEventListener('mousemove', function (e) {
            if (arrastandoArea) moverNaArea(arrastandoArea, e);
            if (arrastandoHue) moverNoHue(arrastandoHue, e);
        });

        document.addEventListener('mouseup', function () {
            arrastandoArea = null;
            arrastandoHue = null;
        });

        // Área de saturação (eixo X) / brilho (eixo Y, invertido: topo =
        // brilho máximo). A matiz não muda aqui, só lê o 'data-hue' que
        // já está salvo no wrapper (escrito no primeiro render em Python
        // ou pelo último arraste na barra de matiz).
        function moverNaArea(area, e) {
            var wrapper = area.closest('.cor-picker-wrapper');
            if (!wrapper) return;
            var rect = area.getBoundingClientRect();
            var x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            var y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
            var h = parseFloat(wrapper.dataset.hue || '0');
            aplicarRgb(wrapper, h, x, 1 - y);

            var cursor = area.querySelector('.cor-picker-area-cursor');
            if (cursor) {
                cursor.style.left = (x * 100) + '%';
                cursor.style.top = (y * 100) + '%';
            }
        }

        function moverNoHue(hue, e) {
            var wrapper = hue.closest('.cor-picker-wrapper');
            if (!wrapper) return;
            var rect = hue.getBoundingClientRect();
            var x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            var h = x * 360;
            var s = parseFloat(wrapper.dataset.sat || '0');
            var v = parseFloat(wrapper.dataset.val || '0');
            aplicarRgb(wrapper, h, s, v);

            var fundo = wrapper.querySelector('.cor-picker-area-fundo');
            if (fundo) fundo.style.backgroundColor = 'hsl(' + h.toFixed(1) + ', 100%, 50%)';

            var cursor = hue.querySelector('.cor-picker-hue-cursor');
            if (cursor) cursor.style.left = (x * 100) + '%';
        }
    }
    iniciarSeletorCor();

    // Mapa de comandos LaTeX 'simples' -> símbolo Unicode equivalente,
    // usado nas caixas de texto de Título/Axis x/Axis y da seção
    // 'Eixos' (ver 'painel-edicao-latex-input' em edit_menu.css e
    // _linha_eixo em renderizadores.py). NÃO é um motor de LaTeX de
    // verdade (sem fórmulas, frações, sub/sobrescrito) — só troca o
    // comando digitado pelo caractere Unicode correspondente, porque
    // um <input> comum só mostra texto puro, nunca fórmula renderizada.
    // Lista ordenada com os nomes mais longos primeiro onde há risco de
    // sobreposição (ex: 'Sigma' antes de qualquer coisa que pudesse
    // bater como prefixo dela).
    var MAPA_LATEX_SIMPLES = [
        ['\\Delta', 'Δ'], ['\\delta', 'δ'],
        ['\\Gamma', 'Γ'], ['\\gamma', 'γ'],
        ['\\Theta', 'Θ'], ['\\theta', 'θ'],
        ['\\Lambda', 'Λ'], ['\\lambda', 'λ'],
        ['\\Sigma', 'Σ'], ['\\sigma', 'σ'],
        ['\\Omega', 'Ω'], ['\\omega', 'ω'],
        ['\\Phi', 'Φ'], ['\\phi', 'φ'],
        ['\\Psi', 'Ψ'], ['\\psi', 'ψ'],
        ['\\Pi', 'Π'], ['\\pi', 'π'],
        ['\\alpha', 'α'], ['\\beta', 'β'], ['\\chi', 'χ'],
        ['\\epsilon', 'ε'], ['\\eta', 'η'], ['\\mu', 'μ'],
        ['\\nu', 'ν'], ['\\xi', 'ξ'], ['\\rho', 'ρ'], ['\\tau', 'τ'],
        ['\\infty', '∞'], ['\\pm', '±'], ['\\mp', '∓'],
        ['\\times', '×'], ['\\div', '÷'], ['\\cdot', '·'],
        ['\\leq', '≤'], ['\\geq', '≥'], ['\\neq', '≠'], ['\\approx', '≈'],
        ['\\equiv', '≡'], ['\\rightarrow', '→'], ['\\leftarrow', '←'],
        ['\\sqrt', '√'], ['\\circ', '°'], ['\\degree', '°'],
        ['\\partial', '∂'], ['\\nabla', '∇'], ['\\sum', 'Σ'],
        ['\\prod', 'Π'], ['\\int', '∫'],
    ];

    function traduzirLatexSimples(texto) {
        var resultado = texto;
        MAPA_LATEX_SIMPLES.forEach(function (par) {
            resultado = resultado.split(par[0]).join(par[1]);
        });
        // '$...$' são só os delimitadores de 'modo matemático' do
        // LaTeX — depois que os comandos já viraram símbolo, não
        // sobra função nenhuma pra eles aqui (não existe renderização
        // de fórmula real nesta caixa, só a troca pontual de símbolo).
        resultado = resultado.split('$').join('');
        return resultado;
    }

    function iniciarTraducaoLatex() {
        // Setter nativo de 'value' do <input>: setar 'e.target.value'
        // direto funciona visualmente, mas o React (por trás do
        // dcc.Input) rastreia o valor anterior por fora do DOM e pode
        // não perceber a troca — resultando no campo "voltando" pro
        // texto digitado assim que o Dash re-renderiza algo. Usar o
        // setter nativo (em vez da atribuição direta) antes de disparar
        // o evento 'input' é o contorno padrão pra isso.
        var setterNativoValue = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;

        document.addEventListener('input', function (e) {
            var alvo = e.target;
            // 'painel-edicao-latex-input' foi passada como className do
            // dcc.Input, mas essa versão do dash-core-components desenha
            // um <input type='text'> DENTRO de uma <div> que leva a
            // className (mesma estrutura de '.cor-picker-input' — ver
            // iniciarSeletorCor logo acima, e de '.painel-edicao-
            // stepper-input' — ver alternar_stepper em callbacks.py) —
            // então o alvo real do evento 'input' (o <input>) nunca tem
            // essa classe; é preciso checar o PAI mais próximo com ela.
            var wrapper = alvo && alvo.closest && alvo.closest('.painel-edicao-latex-input');
            if (!wrapper || alvo.tagName !== 'INPUT') return;

            var original = alvo.value;
            var traduzido = traduzirLatexSimples(original);
            if (traduzido === original) return;

            setterNativoValue.call(alvo, traduzido);
            alvo.dispatchEvent(new Event('input', { bubbles: true }));

            // Cursor vai pro fim: a troca normalmente ENCURTA o texto
            // (ex: 6 caracteres '\Delta' viram 1 'Δ'), então preservar a
            // posição exata exigiria mapear cada substituição
            // individualmente. Pra caixas curtas de título/rótulo (uso
            // real daqui), ir pro fim é a opção simples e previsível.
            var posicao = traduzido.length;
            alvo.setSelectionRange(posicao, posicao);
        });
    }
    iniciarTraducaoLatex();

    function iniciarSelecaoCorte() {
        // Modo de seleção de 'Aparar dados' (e, no futuro, 'Excluir
        // dados' — mesma mecânica de 2 cliques): a guia vermelha
        // TRACEJADA que acompanha o mouse é 100% client-side — mas usa
        // os eventos NATIVOS do Plotly ('plotly_hover'/'plotly_click',
        // disparados pela própria lib no elemento do gráfico) em vez
        // de calcular pixel->dado na mão. Antes fazia esse cálculo
        // manualmente (posição do mouse + range do eixo) por cima do
        // 'hovermode' padrão do Plotly, que desenha o PRÓPRIO
        // indicador (spike line + rótulo) — como o Plotly ENCAIXA no
        // ponto de dado mais próximo e o cálculo manual seguia o pixel
        // exato do mouse, as duas linhas discordavam visualmente. Usar
        // o evento nativo elimina esse desencontro (nossa linha nasce
        // EXATAMENTE onde o Plotly já calculou) — e o indicador nativo
        // (spike/hover label) fica escondido via CSS só durante
        // 'corte-ativo' (ver '#container-grafico.corte-ativo' em
        // icon_menu.css), sobrando só a nossa.
        //
        // O gráfico só reage quando 'container-grafico' (o wrapper
        // ESTÁVEL — ver layout.py; dcc.Graph em si não reflete bem
        // atualizações de className via callback, peculiaridade da
        // própria biblioteca) tem a classe 'corte-ativo', ligada/
        // desligada por iniciar_selecao_corte/confirmar_corte/
        // cancelar_corte em callbacks.py. A guia PARA de seguir o
        // mouse assim que o segundo corte é clicado — 'corte-completo'
        // (adicionada por registrar_clique_corte no mesmo momento que
        // o segundo clique é aceito) é o que marca esse ponto.

        function emModoSelecao() {
            var container = document.getElementById('container-grafico');
            return !!(container && container.classList.contains('corte-ativo'));
        }

        function selecaoCompleta() {
            var container = document.getElementById('container-grafico');
            return !!(container && container.classList.contains('corte-completo'));
        }

        // Shapes JÁ DESENHADAS pelo Python (linhas sólidas + hachura dos
        // cortes confirmados) — filtra fora qualquer guia tracejada de
        // um hover anterior, senão cada novo movimento empilharia mais
        // uma linha em cima da última em vez de substituir.
        function formasConfirmadas(gd) {
            return (gd.layout.shapes || []).filter(function (s) {
                return !(s.line && s.line.dash === 'dash');
            });
        }

        // Liga os listeners NATIVOS do Plotly ('gd.on(...)') uma única
        // vez por elemento de gráfico — 'gd' muda de instância sempre
        // que 'container-grafico.children' é substituído por inteiro
        // (ver confirmar_corte/cancelar_corte, callbacks.py); o guard
        // via 'dataset.corteLigado' evita ligar os mesmos listeners
        // duas vezes numa instância que já os tem, e o 'mouseenter'
        // (fase de captura, que ele não faz bubble normalmente) garante
        // que uma instância NOVA seja pega assim que o mouse chega
        // nela, sem precisar de um MutationObserver à parte.
        document.addEventListener('mouseenter', function (e) {
            var wrapper = e.target.closest && e.target.closest('#grafico-plotly-real');
            if (!wrapper) return;
            var gd = wrapper.querySelector('.js-plotly-plot');
            if (!gd || gd.dataset.corteLigado) return;
            gd.dataset.corteLigado = '1';

            gd.on('plotly_hover', function (dadosEvento) {
                if (!emModoSelecao() || selecaoCompleta()) return;
                var ponto = dadosEvento.points && dadosEvento.points[0];
                if (!ponto) return;
                var formas = formasConfirmadas(gd);
                formas.push({
                    type: 'line', xref: 'x', yref: 'paper',
                    x0: ponto.x, x1: ponto.x, y0: 0, y1: 1,
                    line: { color: '#D62728', width: 2, dash: 'dash' },
                });
                Plotly.relayout(gd, { shapes: formas });
            });

            gd.on('plotly_unhover', function () {
                if (!emModoSelecao() || selecaoCompleta()) return;
                Plotly.relayout(gd, { shapes: formasConfirmadas(gd) });
            });

            // O clique de verdade não desenha nada aqui (isso é papel
            // do Python, depois que o valor for confirmado como um
            // corte — ver registrar_clique_corte em callbacks.py) — só
            // ESCREVE o valor no campo escondido 'corte-clique-x',
            // pelo mesmo truque de setter nativo + evento 'input' já
            // usado no seletor de cor (iniciarSeletorCor, acima) — é
            // isso que faz o Dash perceber a mudança e rodar o
            // callback Python correspondente.
            gd.on('plotly_click', function (dadosEvento) {
                if (!emModoSelecao() || selecaoCompleta()) return;
                var ponto = dadosEvento.points && dadosEvento.points[0];
                if (!ponto) return;
                var campo = document.getElementById('corte-clique-x');
                if (!campo) return;
                var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(campo, ponto.x);
                campo.dispatchEvent(new Event('input', { bubbles: true }));
            });
        }, true);
    }
    iniciarSelecaoCorte();

    function iniciarBarraCarregamentoRodape() {
        // Liga o preenchimento verde do '#rodape-status' ao estado REAL de
        // carregamento do Dash: o dcc.Loading que envolve 'container-grafico'
        // (ver layout.py, id='loading-grafico') marca esse elemento com o
        // atributo 'data-dash-is-loading="true"' enquanto um callback que o
        // atualiza está rodando (ex: upload de arquivo) — não precisamos de
        // nenhum Output/State novo no Python, só observar esse atributo.
        function tentar() {
            var alvo = document.getElementById('container-grafico');
            // Barra ocupa a seção central inteira do rodapé (não só o texto
            // da mensagem do mago) — ver '.rodape-progresso-central' em
            // status_menu.css e o motivo no comentário logo acima.
            var barra = document.getElementById('rodape-progresso-central');
            if (!alvo || !barra) {
                setTimeout(tentar, 300);
                return;
            }

            var progresso = 0;
            var intervalo = null;
            var estavaCarregando = false;

            function definirLargura(pct) {
                barra.style.width = pct + '%';
            }

            function iniciarProgresso() {
                clearInterval(intervalo);
                barra.classList.remove('rodape-concluido');
                barra.classList.add('rodape-carregando');
                progresso = 0;
                definirLargura(0);

                // Cresce rápido no início e desacelera perto de 90% —
                // como não dá pra saber a duração real do processamento
                // (é um callback síncrono do Dash), a barra só "assume"
                // os últimos 10% quando o carregamento termina de fato
                // (ver concluirProgresso), em vez de fingir 100% antes da
                // hora.
                intervalo = setInterval(function () {
                    var passo = (90 - progresso) * 0.08;
                    progresso = Math.min(90, progresso + Math.max(passo, 0.4));
                    definirLargura(progresso);
                }, 120);
            }

            function concluirProgresso() {
                clearInterval(intervalo);
                barra.classList.remove('rodape-carregando');
                definirLargura(100);
                barra.classList.add('rodape-concluido');

                // A classe 'rodape-concluido' dispara a animação CSS
                // 'rodape-progresso-concluir' (0.7s): a barra fica cheia e
                // some por transparência, sem encolher de volta. Só depois
                // que a animação termina é que resetamos a largura pra 0 —
                // nesse ponto já está com opacity 0, então o reset não
                // aparece. A mensagem do mago (texto do '#rodape-status')
                // nunca é tocada aqui, só essa camada de preenchimento.
                setTimeout(function () {
                    barra.classList.remove('rodape-concluido');
                    definirLargura(0);
                }, 700);
            }

            new MutationObserver(function () {
                var carregando = alvo.getAttribute('data-dash-is-loading') === 'true';
                if (carregando && !estavaCarregando) {
                    iniciarProgresso();
                } else if (!carregando && estavaCarregando) {
                    concluirProgresso();
                }
                estavaCarregando = carregando;
            }).observe(alvo, { attributes: true, attributeFilter: ['data-dash-is-loading'] });
        }
        tentar();
    }
    iniciarBarraCarregamentoRodape();

    function iniciarBarraCarregamentoToolbar() {
        // MESMO padrão da barra do rodapé (iniciarBarraCarregamentoRodape,
        // logo acima — reaproveita literalmente as classes 'rodape-
        // carregando'/'rodape-concluido' e a keyframe 'rodape-progresso-
        // concluir', já que o efeito visual é idêntico, só muda ONDE
        // aparece), só que na barra do PROMPT de corte ('Confirmar
        // seleção?' — ver toolbar-confirmacao-progresso em layout.py),
        // não na seção central do rodapé. Único sinal novo: só ativa se
        // o prompt estiver VISÍVEL no momento (senão qualquer outro
        // carregamento de 'container-grafico' — trocar de aba, marcar
        // canal — faria essa barra picar sem sentido nenhum, já que o
        // prompt nem aparece nesses casos).
        function tentar() {
            var alvo = document.getElementById('container-grafico');
            var prompt = document.getElementById('toolbar-confirmacao-corte');
            var barra = document.getElementById('toolbar-confirmacao-progresso');
            if (!alvo || !prompt || !barra) {
                setTimeout(tentar, 300);
                return;
            }

            var progresso = 0;
            var intervalo = null;
            var estavaCarregando = false;

            function promptVisivel() {
                return prompt.style.display !== 'none';
            }

            function definirLargura(pct) {
                barra.style.width = pct + '%';
            }

            function iniciarProgresso() {
                clearInterval(intervalo);
                barra.classList.remove('rodape-concluido');
                barra.classList.add('rodape-carregando');
                progresso = 0;
                definirLargura(0);
                intervalo = setInterval(function () {
                    var passo = (90 - progresso) * 0.08;
                    progresso = Math.min(90, progresso + Math.max(passo, 0.4));
                    definirLargura(progresso);
                }, 120);
            }

            function concluirProgresso() {
                clearInterval(intervalo);
                barra.classList.remove('rodape-carregando');
                definirLargura(100);
                barra.classList.add('rodape-concluido');
                setTimeout(function () {
                    barra.classList.remove('rodape-concluido');
                    definirLargura(0);
                }, 700);
            }

            new MutationObserver(function () {
                var carregando = alvo.getAttribute('data-dash-is-loading') === 'true' && promptVisivel();
                if (carregando && !estavaCarregando) {
                    iniciarProgresso();
                } else if (!carregando && estavaCarregando) {
                    concluirProgresso();
                }
                estavaCarregando = carregando;
            }).observe(alvo, { attributes: true, attributeFilter: ['data-dash-is-loading'] });
        }
        tentar();
    }
    iniciarBarraCarregamentoToolbar();
});
</script>
"""


def construir_index_string():
    """
    Monta o HTML raiz customizado do Dash, injetando SCRIPT_DIVISORIA no fim
    do <body>. As chaves duplas ({{%...%}}) são placeholders que o próprio
    Dash substitui depois — não mexer nelas.
    """
    return f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
        {SCRIPT_DIVISORIA}
    </body>
</html>
"""