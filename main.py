"""Gera o histórico, trata os dados, desenha os gráficos e pode carregar o Oracle."""

from __future__ import annotations

import argparse

from farmtech_dados.gerar_leituras import gerar
from farmtech_dados.graficos import gerar_todos
from farmtech_dados.indicadores import calcular, salvar
from farmtech_dados.tratar import salvar_tratado, tratar


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Histórico de irrigação da FarmTech Solutions."
    )
    parser.add_argument(
        "--oracle",
        action="store_true",
        help="Cria as tabelas e carrega o histórico no Oracle configurado no .env.",
    )
    args = parser.parse_args()

    bruto = gerar()
    dados, limpeza = tratar(bruto)
    tratado = salvar_tratado(dados)
    resumo = calcular(dados)
    indicadores = salvar(resumo)
    graficos = gerar_todos(dados, resumo)

    print(f"CSV bruto: {bruto}")
    print(
        f"Leituras brutas: {limpeza['brutas']}. "
        f"Removidas: {limpeza['removidas']}. "
        f"Válidas: {limpeza['validas']}."
    )
    print(f"CSV tratado: {tratado}")
    print(f"Indicadores: {indicadores}")
    print(
        f"Bomba ligada por {resumo['horas_bomba']} h, "
        f"em {resumo['acionamentos']} acionamentos. "
        f"Água estimada: {resumo['agua_total_l']:.0f} L "
        f"a {resumo['vazao_l_h']:.0f} L/h."
    )
    print("Água e sensores por mês:")
    for mes in resumo["por_mes"]:
        print(
            f"  {mes['mes']}: {mes['agua_l']:.0f} L, "
            f"umidade {mes['umidade_min']:.1f}–{mes['umidade_max']:.1f}%, "
            f"pH {mes['ph_min']:.2f}–{mes['ph_max']:.2f}"
        )
    print("Correlação com a decisão de ligar a bomba:")
    for item in resumo["ranking_bomba"]:
        print(f"  {item['variavel']}: {item['correlacao']:+.2f}")
    print("Gráficos:")
    for caminho in graficos:
        print(f"  {caminho}")

    if args.oracle:
        from farmtech_dados.oracle_carga import carregar, consultar, salvar_consultas

        print("Carregando o Oracle.")
        contagens = carregar(dados)
        print("Registros depois da carga:")
        for tabela, total in contagens.items():
            print(f"  {tabela}: {total}")
        resultados = consultar()
        destino = salvar_consultas(resultados)
        print(f"Consultas gravadas em {destino}")
        for titulo, colunas, linhas in resultados:
            print()
            print(titulo)
            print(" | ".join(colunas))
            for linha in linhas:
                print(" | ".join(str(valor) for valor in linha))


if __name__ == "__main__":
    main()
