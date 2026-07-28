SCRIPT_DIVISORIA = """
<script>
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
        habilitarDivisor('divisor-resize-edit', painelDireito, rodapeEdit, 200, 500, function (e) {
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

                // Some sozinha pouco depois de concluir — a mensagem do
                // mago (texto do '#rodape-status') nunca é tocada aqui,
                // só a camada de preenchimento atrás de todo o conteúdo
                // da seção central.
                setTimeout(function () {
                    barra.classList.remove('rodape-concluido');
                    definirLargura(0);
                }, 450);
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