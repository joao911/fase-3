"""Limpa o CSV do Monitor Serial e suaviza umidade e pH com média móvel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from farmtech_dados.parametros import (
    DADOS,
    JANELA_MEDIA,
    PH_MAX_FISICO,
    PH_MIN_FISICO,
    UMIDADE_MAX_FISICA,
    UMIDADE_MIN_FISICA,
)

COLUNAS_NUMERICAS = (
    "umidade",
    "ph",
    "fosforo",
    "potassio",
    "nitrogenio",
    "chuva",
    "bomba",
)


def media_movel(valores: pd.Series, janela: int = JANELA_MEDIA) -> np.ndarray:
    """Média móvel das últimas `janela` leituras válidas, calculada com NumPy."""
    if janela < 1:
        raise ValueError("A janela da média móvel precisa ser pelo menos 1.")
    arr = valores.to_numpy(dtype=float)
    acumulado = np.insert(np.cumsum(arr), 0, 0.0)
    indices = np.arange(len(arr))
    inicios = np.maximum(0, indices + 1 - janela)
    totais = acumulado[indices + 1] - acumulado[inicios]
    quantidades = indices + 1 - inicios
    return np.round(totais / quantidades, 2)


def tratar(caminho: Path | None = None) -> tuple[pd.DataFrame, dict]:
    origem = DADOS / "leituras_brutas.csv" if caminho is None else caminho
    bruto = pd.read_csv(origem)
    return limpar(bruto)


def limpar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    dados = bruto.copy()
    dados["data_hora"] = pd.to_datetime(dados["data_hora"], errors="coerce")
    for coluna in COLUNAS_NUMERICAS:
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    valido = (
        dados["data_hora"].notna()
        & dados["umidade"].between(UMIDADE_MIN_FISICA, UMIDADE_MAX_FISICA)
        & dados["ph"].between(PH_MIN_FISICO, PH_MAX_FISICO)
        & dados["fosforo"].isin([0, 1])
        & dados["potassio"].isin([0, 1])
        & dados["nitrogenio"].isin([0, 1])
        & dados["chuva"].isin([0, 1])
        & dados["bomba"].isin([0, 1])
        & dados["origem"].isin(["simulada", "serial"])
    )
    limpo = dados.loc[valido].sort_values("data_hora").reset_index(drop=True)
    for coluna in ("fosforo", "potassio", "nitrogenio", "chuva", "bomba"):
        limpo[coluna] = limpo[coluna].astype(int)

    limpo["umidade_suavizada"] = media_movel(limpo["umidade"])
    limpo["ph_suavizado"] = media_movel(limpo["ph"])
    relatorio = {
        "brutas": int(len(bruto)),
        "validas": int(len(limpo)),
        "removidas": int(len(bruto) - len(limpo)),
    }
    return limpo, relatorio


def salvar_tratado(dados: pd.DataFrame, caminho: Path | None = None) -> Path:
    destino = DADOS / "leituras_tratadas.csv" if caminho is None else caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados.to_csv(destino, index=False)
    return destino
