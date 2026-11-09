"""Testes do histórico, da limpeza e dos indicadores."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from farmtech_dados.gerar_leituras import DEFEITOS, simular
from farmtech_dados.oracle_carga import ler_cultura_txt, ler_insumos_json
from farmtech_dados.indicadores import calcular, intervalos_bomba
from farmtech_dados.parametros import FASE2, VAZAO_L_H
from farmtech_dados.tratar import limpar, media_movel

import pandas as pd


class TestArquivosFase2(unittest.TestCase):
    def test_texto_e_json_da_aplicacao(self):
        cultura = ler_cultura_txt()
        insumos = ler_insumos_json()
        self.assertEqual(cultura["nome"], "Tomate")
        self.assertEqual(cultura["ph_min"], 6.0)
        self.assertEqual(insumos["vazao_l_h"], VAZAO_L_H)
        self.assertEqual(len(insumos["insumos"]), 3)


class TestMediaMovel(unittest.TestCase):
    def test_janela_de_duas_leituras(self):
        resultado = media_movel(pd.Series([1.0, 2.0, 3.0, 4.0]), janela=2)
        self.assertEqual(resultado.tolist(), [1.0, 1.5, 2.5, 3.5])


class TestHistorico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(FASE2))
        cls.limpo = simular()
        cls.tratado, cls.limpeza = limpar(_com_defeitos(cls.limpo))

    def test_cobre_tres_meses(self):
        self.assertEqual(self.limpo["data_hora"].iloc[0], datetime(2026, 6, 1))
        self.assertEqual(self.limpo["data_hora"].iloc[-1], datetime(2026, 8, 31, 23))
        self.assertEqual(set(self.limpo["origem"]), {"simulada"})

    def test_bomba_segue_a_regra_da_fase_2(self):
        from farmtech.irrigacao import decidir

        bomba = False
        for linha in self.limpo.itertuples(index=False):
            decisao = decidir(
                umidade=linha.umidade,
                ph=linha.ph,
                ph_confirmado=True,
                nitrogenio=bool(linha.nitrogenio),
                fosforo=bool(linha.fosforo),
                potassio=bool(linha.potassio),
                bomba_ligada=bomba,
                nivel_chuva=80 if linha.chuva else 0,
            )
            self.assertEqual(int(decisao.ligar_bomba), int(linha.bomba))
            bomba = decisao.ligar_bomba

    def test_remove_somente_as_leituras_invalidas(self):
        self.assertEqual(self.limpeza["removidas"], len(DEFEITOS))
        self.assertTrue(self.tratado["umidade"].between(0, 100).all())
        self.assertTrue(self.tratado["ph"].between(0, 14).all())
        self.assertLess(
            self.tratado["umidade_suavizada"].var(),
            self.tratado["umidade"].var(),
        )

    def test_agua_fecha_com_as_horas_ligadas(self):
        resumo = calcular(self.tratado)
        self.assertEqual(resumo["horas_bomba"], int(self.tratado["bomba"].sum()))
        self.assertAlmostEqual(resumo["agua_total_l"], resumo["horas_bomba"] * VAZAO_L_H)
        self.assertGreater(resumo["acionamentos"], 1)
        self.assertTrue({0, 1} <= set(self.tratado["bomba"]))
        historico = intervalos_bomba(self.tratado)
        self.assertEqual(len(historico), resumo["acionamentos"])
        self.assertEqual(int(historico["horas"].sum()), resumo["horas_bomba"])


def _com_defeitos(limpo: pd.DataFrame) -> pd.DataFrame:
    dados = limpo.copy()
    for coluna in ("umidade", "ph", "fosforo", "potassio", "nitrogenio", "chuva", "bomba"):
        dados[coluna] = dados[coluna].astype(object)
    for indice, (coluna, valor) in DEFEITOS.items():
        dados.loc[indice, coluna] = valor if valor != "" else None
    return dados


if __name__ == "__main__":
    unittest.main()
