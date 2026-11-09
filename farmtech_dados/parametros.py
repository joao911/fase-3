"""Constantes da fase 3, alinhadas à regra do tomateiro da fase 2."""

from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "dados"
GRAFICOS = RAIZ / "graficos"
SQL = RAIZ / "sql"
FASE2 = RAIZ.parent / "fase 2"

INICIO = datetime(2026, 6, 1)
DIAS = 92
SEMENTE = 42
JANELA_MEDIA = 6

# Setor didático de gotejamento. Cada leitura vale uma hora.
VAZAO_L_H = 500.0
AREA_M2 = 500.0

# Mesmos limiares de farmtech/cultura.py, usados nos gráficos e no cadastro.
PH_IDEAL_MIN = 6.0
PH_IDEAL_MAX = 6.5
UMIDADE_LIGAR = 70.0
UMIDADE_DESLIGAR = 80.0

UMIDADE_MIN_FISICA = 0.0
UMIDADE_MAX_FISICA = 100.0
PH_MIN_FISICO = 0.0
PH_MAX_FISICO = 14.0

COLUNAS_BRUTAS = (
    "data_hora",
    "umidade",
    "ph",
    "fosforo",
    "potassio",
    "nitrogenio",
    "chuva",
    "bomba",
    "origem",
)
