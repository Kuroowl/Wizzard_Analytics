"""
Callbacks do Wizzard: o que acontece quando o usuário faz alguma coisa.

Camadas:
    gui/        -> COMO aparece (layout, renderizadores, rodapé/feedback)
    callbacks/  -> O QUE ACONTECE quando o usuário interage (orquestração)
    core/       -> COMO a operação/cálculo é feito (dados, operações)

Um módulo por área, cada um expondo 'registrar_callbacks_<area>(app, estado)'.
Migração em andamento (Fase 2): enquanto durar, o registrador central ainda
é src/gui/callbacks.py, que chama os módulos já migrados e guarda o resto.
Ao final, ele passa a morar aqui.
"""
