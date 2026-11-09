"""Gráficos do histórico de solo e da decisão de irrigar."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from farmtech_dados.parametros import GRAFICOS, UMIDADE_DESLIGAR, UMIDADE_LIGAR

NOMES = {
    "umidade": "Umidade",
    "ph": "pH",
    "fosforo": "Fósforo",
    "potassio": "Potássio",
    "nitrogenio": "Nitrogênio",
    "chuva": "Chuva",
    "bomba": "Bomba",
}


def gerar_todos(dados: pd.DataFrame, resumo: dict) -> list[Path]:
    GRAFICOS.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["axes.unicode_minus"] = False
    return [
        _evolucao(dados),
        _bomba(dados),
        _distribuicao(dados),
        _correlacao(dados, resumo),
    ]


def _evolucao(dados: pd.DataFrame) -> Path:
    diario = (
        dados.set_index("data_hora")
        .resample("D")
        .agg(umidade=("umidade_suavizada", "mean"), ph=("ph_suavizado", "mean"))
    )
    fig, eixo_umidade = plt.subplots(figsize=(12, 5))
    eixo_ph = eixo_umidade.twinx()
    linha_umidade = eixo_umidade.plot(
        diario.index,
        diario["umidade"],
        color="#1b7f4e",
        linewidth=2,
        label="Umidade média do dia",
    )
    linha_ph = eixo_ph.plot(
        diario.index,
        diario["ph"],
        color="#9b2226",
        linewidth=2,
        label="pH médio do dia",
    )
    eixo_umidade.set_ylabel("Umidade do solo (%)")
    eixo_ph.set_ylabel("pH")
    eixo_umidade.set_ylim(30, 100)
    eixo_ph.set_ylim(5.6, 7.6)
    eixo_umidade.set_title("Evolução da umidade e do pH ao longo da safra")
    eixo_umidade.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    linhas = linha_umidade + linha_ph
    eixo_umidade.legend(linhas, [linha.get_label() for linha in linhas], loc="upper right")
    fig.tight_layout()
    return _salvar(fig, "evolucao_umidade_ph.png")


def _bomba(dados: pd.DataFrame) -> Path:
    inicio = pd.Timestamp("2026-06-18")
    fim = pd.Timestamp("2026-07-03")
    janela = dados[(dados["data_hora"] >= inicio) & (dados["data_hora"] < fim)]
    fig, eixo = plt.subplots(figsize=(12, 5))
    eixo.plot(
        janela["data_hora"],
        janela["umidade"],
        color="#94a3b8",
        linewidth=1,
        label="Umidade lida",
    )
    eixo.plot(
        janela["data_hora"],
        janela["umidade_suavizada"],
        color="#1b7f4e",
        linewidth=2,
        label="Umidade suavizada",
    )
    eixo.fill_between(
        janela["data_hora"],
        30,
        100,
        where=janela["bomba"].to_numpy() == 1,
        color="#f4a261",
        alpha=0.35,
        label="Bomba ligada",
    )
    eixo.axhline(UMIDADE_LIGAR, color="#264653", linestyle="--", linewidth=1, label="Liga abaixo de 70%")
    eixo.axhline(UMIDADE_DESLIGAR, color="#9b2226", linestyle="--", linewidth=1, label="Desliga a partir de 80%")
    eixo.set_ylim(30, 100)
    eixo.set_ylabel("Umidade do solo (%)")
    eixo.set_title("Umidade e acionamento da bomba entre 18/06 e 02/07")
    eixo.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    eixo.legend(loc="lower right", ncol=2)
    fig.tight_layout()
    return _salvar(fig, "umidade_e_bomba.png")


def _distribuicao(dados: pd.DataFrame) -> Path:
    fig, eixos = plt.subplots(1, 3, figsize=(13, 4.2))
    sns.histplot(dados["umidade"], bins=30, ax=eixos[0], color="#1b7f4e")
    eixos[0].set_title("Umidade")
    eixos[0].set_xlabel("Umidade (%)")
    eixos[0].set_ylabel("Leituras")

    sns.histplot(dados["ph"], bins=30, ax=eixos[1], color="#2a6f97")
    eixos[1].set_title("pH")
    eixos[1].set_xlabel("pH")
    eixos[1].set_ylabel("")

    contagem = pd.DataFrame(
        [
            {"Sensor": "Fósforo", "Estado": "adequado", "Horas": int((dados["fosforo"] == 1).sum())},
            {"Sensor": "Fósforo", "Estado": "deficiente", "Horas": int((dados["fosforo"] == 0).sum())},
            {"Sensor": "Potássio", "Estado": "adequado", "Horas": int((dados["potassio"] == 1).sum())},
            {"Sensor": "Potássio", "Estado": "deficiente", "Horas": int((dados["potassio"] == 0).sum())},
            {"Sensor": "Nitrogênio", "Estado": "adequado", "Horas": int((dados["nitrogenio"] == 1).sum())},
            {"Sensor": "Nitrogênio", "Estado": "deficiente", "Horas": int((dados["nitrogenio"] == 0).sum())},
        ]
    )
    sns.barplot(
        data=contagem,
        x="Sensor",
        y="Horas",
        hue="Estado",
        ax=eixos[2],
        palette={"adequado": "#1b7f4e", "deficiente": "#9b2226"},
    )
    eixos[2].set_title("Nutrientes")
    eixos[2].set_xlabel("")
    eixos[2].set_ylabel("Horas")
    eixos[2].set_ylim(0, eixos[2].get_ylim()[1] * 1.18)
    for container in eixos[2].containers:
        eixos[2].bar_label(container, fontsize=8)
    fig.suptitle("Distribuição das leituras dos sensores", y=1.02)
    fig.tight_layout()
    return _salvar(fig, "distribuicao_sensores.png")


def _correlacao(dados: pd.DataFrame, resumo: dict) -> Path:
    matriz = dados.loc[:, list(NOMES)].corr().rename(index=NOMES, columns=NOMES)
    lider = resumo["ranking_bomba"][0]
    nome_lider = NOMES.get(lider["variavel"], lider["variavel"])
    fig, eixo = plt.subplots(figsize=(8, 6.4))
    sns.heatmap(
        matriz,
        annot=True,
        fmt=".2f",
        cmap="vlag",
        vmin=-1,
        vmax=1,
        square=True,
        ax=eixo,
    )
    eixo.set_title(
        "Correlação entre variáveis\n"
        f"Maior relação com a bomba: {nome_lider} ({lider['correlacao']:+.2f})"
    )
    fig.tight_layout()
    return _salvar(fig, "correlacao.png")


def _salvar(fig: plt.Figure, nome: str) -> Path:
    destino = GRAFICOS / nome
    fig.savefig(destino, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return destino
