"""Indicadores de manejo calculados sobre as leituras já tratadas."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from farmtech_dados.parametros import DADOS, VAZAO_L_H

COLUNAS_CORRELACAO = (
    "umidade",
    "ph",
    "fosforo",
    "potassio",
    "nitrogenio",
    "chuva",
    "bomba",
)


def calcular(dados: pd.DataFrame, vazao_l_h: float = VAZAO_L_H) -> dict:
    horas = int(dados["bomba"].sum())
    por_dia = _por_dia(dados, vazao_l_h)
    por_mes = _por_mes(dados, vazao_l_h)
    correlacao = dados.loc[:, COLUNAS_CORRELACAO].corr().round(4)
    com_bomba = {
        nome: round(float(correlacao.loc[nome, "bomba"]), 4)
        for nome in COLUNAS_CORRELACAO
        if nome != "bomba"
    }
    ranking = sorted(com_bomba.items(), key=lambda item: abs(item[1]), reverse=True)
    return {
        "vazao_l_h": vazao_l_h,
        "horas_bomba": horas,
        "acionamentos": _acionamentos(dados["bomba"]),
        "agua_total_l": round(horas * vazao_l_h, 1),
        "por_dia": por_dia,
        "por_mes": por_mes,
        "correlacao": correlacao.to_dict(),
        "correlacao_com_bomba": com_bomba,
        "ranking_bomba": [{"variavel": nome, "correlacao": valor} for nome, valor in ranking],
    }


def intervalos_bomba(dados: pd.DataFrame, vazao_l_h: float = VAZAO_L_H) -> pd.DataFrame:
    """Agrupa horas seguidas com a bomba ligada em um histórico de acionamentos."""
    if dados.empty:
        return pd.DataFrame(columns=["inicio", "fim", "horas", "vazao_l_h", "volume_litros"])

    ligado = dados["bomba"].astype(int) == 1
    mudou = ligado.ne(ligado.shift(fill_value=False))
    grupo = mudou.cumsum()
    registros = []
    for _, bloco in dados.loc[ligado].groupby(grupo[ligado]):
        inicio = bloco["data_hora"].iloc[0]
        horas = int(len(bloco))
        registros.append(
            {
                "inicio": inicio.to_pydatetime(),
                "fim": (bloco["data_hora"].iloc[-1] + pd.Timedelta(hours=1)).to_pydatetime(),
                "horas": horas,
                "vazao_l_h": vazao_l_h,
                "volume_litros": round(horas * vazao_l_h, 1),
            }
        )
    return pd.DataFrame(registros)


def salvar(resumo: dict, caminho: Path | None = None) -> Path:
    destino = DADOS / "indicadores.json" if caminho is None else caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def _acionamentos(bomba: pd.Series) -> int:
    atual = bomba.astype(int)
    anterior = atual.shift(1, fill_value=0)
    return int(((anterior == 0) & (atual == 1)).sum())


def _por_dia(dados: pd.DataFrame, vazao_l_h: float) -> list[dict]:
    tabela = dados.copy()
    tabela["dia"] = tabela["data_hora"].dt.strftime("%Y-%m-%d")
    linhas = []
    for dia, bloco in tabela.groupby("dia", sort=True):
        horas = int(bloco["bomba"].sum())
        linhas.append(
            {
                "dia": dia,
                "horas_bomba": horas,
                "acionamentos": _acionamentos(bloco["bomba"]),
                "agua_l": round(horas * vazao_l_h, 1),
                "umidade_media": round(float(bloco["umidade_suavizada"].mean()), 2),
                "umidade_min": round(float(bloco["umidade_suavizada"].min()), 2),
                "umidade_max": round(float(bloco["umidade_suavizada"].max()), 2),
                "ph_medio": round(float(bloco["ph_suavizado"].mean()), 2),
                "ph_min": round(float(bloco["ph_suavizado"].min()), 2),
                "ph_max": round(float(bloco["ph_suavizado"].max()), 2),
            }
        )
    return linhas


def _por_mes(dados: pd.DataFrame, vazao_l_h: float) -> list[dict]:
    tabela = dados.copy()
    tabela["mes"] = tabela["data_hora"].dt.strftime("%Y-%m")
    linhas = []
    for mes, bloco in tabela.groupby("mes", sort=True):
        horas = int(bloco["bomba"].sum())
        linhas.append(
            {
                "mes": mes,
                "horas_bomba": horas,
                "acionamentos": _acionamentos(bloco["bomba"]),
                "agua_l": round(horas * vazao_l_h, 1),
                "umidade_media": round(float(bloco["umidade_suavizada"].mean()), 2),
                "umidade_min": round(float(bloco["umidade_suavizada"].min()), 2),
                "umidade_max": round(float(bloco["umidade_suavizada"].max()), 2),
                "ph_medio": round(float(bloco["ph_suavizado"].mean()), 2),
                "ph_min": round(float(bloco["ph_suavizado"].min()), 2),
                "ph_max": round(float(bloco["ph_suavizado"].max()), 2),
            }
        )
    return linhas
