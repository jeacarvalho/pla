import pandas as pd
import pytest
from datetime import datetime

import sys

sys.path.insert(0, "/home/s015533607/Documentos/desenv/pla/importers")

from incomes_handler import (
    identify_transferencia_recebida_indices,
    identify_ajuste_indices,
    generate_transferencia_recebida_entries,
    generate_ajuste_entries,
    generate_income_entries,
)


class TestIdentifyTransferenciaRecebidaIndices:
    def test_identifies_transferencia_recebida(self):
        data = {
            "Data": [datetime(2024, 1, 15), datetime(2024, 1, 16)],
            "Descrição": ["Transferência recebida", "Supermercado"],
            "Valor": [100.00, -50.00],
            "D/R": ["R", "D"],
            "CONTA": ["BbCorrente", "BbCorrente"],
            "Categoria": ["Outros", "Alimentação"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_transferencia_recebida_indices(df)
        assert 0 in result
        assert 1 not in result

    def test_ignores_non_credit(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Transferência recebida"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_transferencia_recebida_indices(df)
        assert len(result) == 0


class TestIdentifyAjusteIndices:
    def test_identifies_ajuste_saldo(self):
        data = {
            "Data": [datetime(2024, 1, 15), datetime(2024, 1, 16)],
            "Descrição": ["Ajuste de saldo", "Supermercado"],
            "Valor": [10.00, -50.00],
            "D/R": ["R", "D"],
            "CONTA": ["BbCorrente", "BbCorrente"],
            "Categoria": ["Outros", "Alimentação"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_ajuste_indices(df)
        assert 0 in result
        assert 1 not in result


class TestGenerateTransferenciaRecebidaEntries:
    def test_generates_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Transferência recebida"],
            "Valor": [100.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_transferencia_recebida_entries(df, {0})
        assert count == 1
        assert "Income:TransferenciasRecebidas" in lines[2]


class TestGenerateAjusteEntries:
    def test_generates_ajuste_debit_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Ajuste de saldo"],
            "Valor": [-10.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_ajuste_entries(df, {0})
        assert count == 1
        assert "Equity:Ajustes" in lines[2]

    def test_generates_ajuste_credit_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Ajuste de saldo"],
            "Valor": [10.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_ajuste_entries(df, {0})
        assert count == 1
        assert "Equity:Ajustes" in lines[1]


class TestGenerateIncomeEntries:
    def test_generates_income_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Salário"],
            "Valor": [3000.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Recebimentos"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_income_entries(df, set())
        assert count == 1
        assert "Assets:BR:BbCorrente" in lines[1]
        assert "Income:Recebimentos" in lines[2]

    def test_excludes_indices(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Salário"],
            "Valor": [3000.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Recebimentos"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_income_entries(df, {0})
        assert count == 0

    def test_ignores_debit_rows(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Despesa"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Alimentação"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_income_entries(df, set())
        assert count == 0
