"""Cria as tabelas no Oracle e carrega CSV, JSON e texto sem duplicar linhas."""

from __future__ import annotations

import json
import os
from pathlib import Path

import oracledb
import pandas as pd

from farmtech_dados.indicadores import intervalos_bomba
from farmtech_dados.parametros import DADOS, FASE2, RAIZ, SQL, VAZAO_L_H

TABELAS = (
    "ft_historico_bomba",
    "ft_leituras",
    "ft_insumos",
    "ft_manejo",
    "ft_culturas",
)
CULTURA_TXT = FASE2 / "dados" / "cultura.txt"
INSUMOS_JSON = FASE2 / "dados" / "insumos.json"


class ConfiguracaoOracleError(RuntimeError):
    pass


def carregar_env(caminho: Path | None = None) -> None:
    arquivo = RAIZ / ".env" if caminho is None else caminho
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue
        chave, valor = texto.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


def conectar():
    carregar_env()
    faltando = [
        nome
        for nome in ("ORACLE_HOST", "ORACLE_PORT", "ORACLE_SID", "ORACLE_USER", "ORACLE_PASSWORD")
        if not os.environ.get(nome)
    ]
    if faltando:
        raise ConfiguracaoOracleError(
            "Defina "
            + ", ".join(faltando)
            + " no ambiente ou no arquivo .env. O modelo está em .env.example."
        )
    dsn = oracledb.makedsn(
        os.environ["ORACLE_HOST"],
        int(os.environ["ORACLE_PORT"]),
        sid=os.environ["ORACLE_SID"],
    )
    return oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=dsn,
        tcp_connect_timeout=20,
    )


def ler_cultura_txt(caminho: Path = CULTURA_TXT) -> dict:
    """Lê o texto da cultura exportado pela aplicação das fases 1 e 2."""
    dados = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        texto = linha.strip()
        if not texto or texto.startswith("#") or ":" not in texto:
            continue
        chave, valor = texto.split(":", 1)
        dados[chave.strip()] = valor.strip()
    for chave in ("ph_min", "ph_max", "umidade_ligar", "umidade_desligar"):
        dados[chave] = float(dados[chave])
    return dados


def ler_insumos_json(caminho: Path = INSUMOS_JSON) -> dict:
    """Lê a vazão do setor e as doses de N, P e K da fase 2."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["vazao_l_h"] = float(dados["vazao_l_h"])
    dados["area_m2"] = float(dados["area_m2"])
    return dados


def carregar(dados: pd.DataFrame, conn=None) -> dict[str, int]:
    """Recarrega a safra. Uma segunda execução substitui as linhas e não as duplica."""
    propria = conn is None
    if propria:
        conn = conectar()
    try:
        with conn.cursor() as cursor:
            if not _esquema_compativel(cursor):
                _recriar(cursor)
            else:
                _apagar_linhas(cursor)
            cultura_id = _inserir_cultura(cursor)
            _inserir_manejo_e_insumos(cursor, cultura_id)
            _inserir_leituras(cursor, dados, cultura_id)
            _inserir_historico(cursor, dados, cultura_id)
            contagens = _contagens(cursor)
        conn.commit()
        return contagens
    finally:
        if propria:
            conn.close()


def consultar(conn=None) -> list[tuple[str, list[str], list[tuple]]]:
    propria = conn is None
    if propria:
        conn = conectar()
    resultados = []
    try:
        texto = (SQL / "consultas.sql").read_text(encoding="utf-8")
        with conn.cursor() as cursor:
            for bloco in texto.split(";"):
                if "SELECT" not in bloco.upper():
                    continue
                cursor.execute(bloco)
                colunas = [item[0] for item in cursor.description]
                linhas = cursor.fetchall()
                resultados.append((_titulo(bloco), colunas, linhas))
    finally:
        if propria:
            conn.close()
    return resultados


def salvar_consultas(resultados, caminho: Path | None = None) -> Path:
    destino = DADOS / "resultado_consultas.txt" if caminho is None else caminho
    partes = []
    for titulo, colunas, linhas in resultados:
        partes.append(titulo)
        partes.append(" | ".join(colunas))
        for linha in linhas:
            partes.append(" | ".join(str(valor) for valor in linha))
        partes.append("")
    destino.write_text("\n".join(partes), encoding="utf-8")
    return destino


def _esquema_compativel(cursor) -> bool:
    cursor.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = 'FT_INSUMOS'")
    if cursor.fetchone()[0] != 1:
        return False
    cursor.execute(
        """
        SELECT COUNT(*) FROM user_tab_columns
        WHERE table_name = 'FT_LEITURAS' AND column_name = 'CULTURA_ID'
        """
    )
    return cursor.fetchone()[0] == 1


def _recriar(cursor) -> None:
    for tabela in TABELAS:
        try:
            cursor.execute(f"DROP TABLE {tabela} PURGE")
        except oracledb.DatabaseError as erro:
            if erro.args[0].code != 942:
                raise
    script = (SQL / "schema.sql").read_text(encoding="utf-8")
    for comando in script.split(";"):
        if "CREATE" not in comando.upper():
            continue
        cursor.execute(comando)


def _apagar_linhas(cursor) -> None:
    for tabela in TABELAS:
        cursor.execute(f"DELETE FROM {tabela}")


def _inserir_cultura(cursor) -> int:
    cultura = ler_cultura_txt()
    novo_id = cursor.var(int)
    cursor.execute(
        """
        INSERT INTO ft_culturas (
            nome, nome_cientifico, fase, ph_min, ph_max,
            umidade_ligar, umidade_desligar, observacao
        ) VALUES (
            :nome, :nome_cientifico, :fase, :ph_min, :ph_max,
            :umidade_ligar, :umidade_desligar, :observacao
        )
        RETURNING id INTO :id
        """,
        {**cultura, "id": novo_id},
    )
    return int(novo_id.getvalue()[0])


def _inserir_manejo_e_insumos(cursor, cultura_id: int) -> None:
    manejo = ler_insumos_json()
    if manejo["vazao_l_h"] != VAZAO_L_H:
        raise ConfiguracaoOracleError(
            "A vazão de fase 2/dados/insumos.json precisa ser a mesma de parametros.py."
        )
    cursor.execute(
        """
        INSERT INTO ft_manejo (cultura_id, vazao_l_h, area_m2, descricao)
        VALUES (:cultura_id, :vazao_l_h, :area_m2, :descricao)
        """,
        {
            "cultura_id": cultura_id,
            "vazao_l_h": manejo["vazao_l_h"],
            "area_m2": manejo["area_m2"],
            "descricao": manejo["descricao"],
        },
    )
    cursor.executemany(
        """
        INSERT INTO ft_insumos (cultura_id, nome, dose_min_kg_ha, dose_max_kg_ha)
        VALUES (:cultura_id, :nome, :dose_min_kg_ha, :dose_max_kg_ha)
        """,
        [{"cultura_id": cultura_id, **item} for item in manejo["insumos"]],
    )


def _inserir_leituras(cursor, dados: pd.DataFrame, cultura_id: int) -> None:
    linhas = [
        (
            cultura_id,
            linha.data_hora.to_pydatetime(),
            float(linha.umidade),
            float(linha.ph),
            int(linha.fosforo),
            int(linha.potassio),
            int(linha.nitrogenio),
            int(linha.chuva),
            int(linha.bomba),
            linha.origem,
            float(linha.umidade_suavizada),
            float(linha.ph_suavizado),
        )
        for linha in dados.itertuples(index=False)
    ]
    cursor.executemany(
        """
        INSERT INTO ft_leituras (
            cultura_id, data_hora, umidade, ph, fosforo, potassio, nitrogenio,
            chuva, bomba, origem, umidade_suavizada, ph_suavizado
        ) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12)
        """,
        linhas,
    )


def _inserir_historico(cursor, dados: pd.DataFrame, cultura_id: int) -> None:
    historico = intervalos_bomba(dados)
    if historico.empty:
        return
    linhas = [
        (
            cultura_id,
            linha.inicio,
            linha.fim,
            float(linha.horas),
            float(linha.vazao_l_h),
            float(linha.volume_litros),
        )
        for linha in historico.itertuples(index=False)
    ]
    cursor.executemany(
        """
        INSERT INTO ft_historico_bomba (
            cultura_id, inicio, fim, horas, vazao_l_h, volume_litros
        ) VALUES (:1, :2, :3, :4, :5, :6)
        """,
        linhas,
    )


def _contagens(cursor) -> dict[str, int]:
    totais = {}
    for tabela in TABELAS:
        cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
        totais[tabela] = int(cursor.fetchone()[0])
    return totais


def _titulo(bloco: str) -> str:
    for linha in bloco.splitlines():
        texto = linha.strip()
        if texto.startswith("--"):
            return texto[2:].strip()
    return "Consulta"
