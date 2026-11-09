"""Gera o histórico horário no formato do Monitor Serial da fase 2.

Cada ciclo do firmware vale uma hora. O arquivo cobre junho, julho e agosto
de 2026. Todas as linhas nascem marcadas como simuladas: não há captura do
Wokwi neste repositório, e o enunciado pede essa marcação quando o volume é
gerado em Python a partir da regra já construída.
"""

from __future__ import annotations

import csv
import sys
from datetime import timedelta

import numpy as np
import pandas as pd

from farmtech_dados.parametros import (
    COLUNAS_BRUTAS,
    DADOS,
    DIAS,
    FASE2,
    INICIO,
    SEMENTE,
)

DIAS_CHUVA = {8, 19, 33, 41, 58, 66, 80, 88}
# Índice da linha no CSV limpo e valor inválido que o tratamento deve remover.
DEFEITOS = {
    10: ("umidade", ""),
    25: ("umidade", "148"),
    26: ("umidade", "-4"),
    80: ("ph", ""),
    81: ("ph", "16.2"),
    82: ("ph", "erro"),
    150: ("fosforo", "3"),
    151: ("potassio", ""),
    220: ("nitrogenio", "ok"),
    300: ("bomba", ""),
    301: ("bomba", "4"),
    450: ("umidade", "250"),
    800: ("ph", "-0.5"),
    1200: ("fosforo", ""),
    1600: ("umidade", ""),
    2000: ("ph", "15"),
}


def _importar_regra():
    caminho = str(FASE2)
    if caminho not in sys.path:
        sys.path.insert(0, caminho)
    from farmtech.cultura import ph_sugerido
    from farmtech.irrigacao import decidir

    return ph_sugerido, decidir


def nutrientes_do_dia(dia: int) -> tuple[bool, bool, bool]:
    """Períodos curtos de deficiência para o histórico não ficar constante."""
    nitrogenio = not (5 <= dia <= 6)
    fosforo = not (45 <= dia <= 46)
    potassio = not (20 <= dia <= 22)
    return nitrogenio, fosforo, potassio


def simular() -> pd.DataFrame:
    """Uma linha por hora, com a mesma decisão de bomba da fase 2.

    A umidade sobe cerca de 2 pontos por hora com a bomba ligada, cai cerca
    de 0,7 ponto com ela desligada e sobe mais depressa nas horas de chuva.
    O pH caminha para o valor sugerido pelo NPK, exceto nos dias 70 a 72,
    em que o solo fica alcalino e a bomba permanece bloqueada.
    O ruído entra na leitura que o relé usa, como um sensor faria.
    """
    ph_sugerido, decidir = _importar_regra()
    gerador = np.random.default_rng(SEMENTE)
    umidade = 62.0
    ph = 6.15
    bomba = False
    linhas = []

    for indice in range(DIAS * 24):
        instante = INICIO + timedelta(hours=indice)
        dia = indice // 24
        hora = indice % 24
        nitrogenio, fosforo, potassio = nutrientes_do_dia(dia)
        chuva = dia in DIAS_CHUVA and 15 <= hora <= 20

        if chuva:
            umidade = min(93.0, umidade + 3.8)
        elif bomba:
            umidade = min(88.0, umidade + 2.0)
        else:
            umidade = max(34.0, umidade - 0.7)

        alvo = 7.1 if 70 <= dia <= 72 else ph_sugerido(nitrogenio, fosforo, potassio)
        ph = ph + 0.25 * (alvo - ph)

        umidade_lida = round(umidade + float(gerador.normal(0, 0.8)), 2)
        ph_lido = round(ph + float(gerador.normal(0, 0.04)), 2)
        decisao = decidir(
            umidade=umidade_lida,
            ph=ph_lido,
            ph_confirmado=True,
            nitrogenio=nitrogenio,
            fosforo=fosforo,
            potassio=potassio,
            bomba_ligada=bomba,
            nivel_chuva=80 if chuva else 0,
        )
        bomba = decisao.ligar_bomba
        linhas.append(
            {
                "data_hora": instante,
                "umidade": umidade_lida,
                "ph": ph_lido,
                "fosforo": int(fosforo),
                "potassio": int(potassio),
                "nitrogenio": int(nitrogenio),
                "chuva": int(chuva),
                "bomba": int(bomba),
                "origem": "simulada",
            }
        )

    return pd.DataFrame(linhas, columns=list(COLUNAS_BRUTAS))


def salvar_bruto(limpo: pd.DataFrame, caminho=None) -> object:
    """Grava o CSV e espalha leituras inválidas para o tratamento remover."""
    destino = DADOS / "leituras_brutas.csv" if caminho is None else caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    registros = limpo.to_dict(orient="records")
    for indice, (coluna, valor) in DEFEITOS.items():
        registros[indice][coluna] = valor

    with destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(COLUNAS_BRUTAS))
        escritor.writeheader()
        for item in registros:
            escritor.writerow({coluna: _celula(item[coluna]) for coluna in COLUNAS_BRUTAS})
    return destino


def gerar() -> object:
    limpo = simular()
    return salvar_bruto(limpo)


def _celula(valor) -> str:
    if isinstance(valor, str):
        return valor
    if isinstance(valor, float):
        return f"{valor:.2f}"
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d %H:%M:%S")
    return str(int(valor))
