import pandas as pd
import pytest
from datetime import datetime

import sys

sys.path.insert(0, "/home/s015533607/Documentos/desenv/pla/importers")

from expenses_handler import (
    identify_boleto_indices,
    identify_cartao_expense_indices,
    generate_boleto_entries,
    generate_cartao_expense_entries,
    generate_expense_entries,
)


class TestIdentifyBoletoIndices:
    def test_identifies_boleto_payment(self):
        data = {
            "Data": [datetime(2024, 1, 15), datetime(2024, 1, 16)],
            "Descrição": ["Pagamento de título", "Supermercado"],
            "Valor": [-100.00, -50.00],
            "D/R": ["D", "D"],
            "CONTA": ["BbCorrente", "BbCorrente"],
            "Categoria": ["Outros", "Alimentação"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_boleto_indices(df)
        assert 0 in result
        assert 1 not in result

    def test_identifies_boleto_keyword(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Boleto"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_boleto_indices(df)
        assert 0 in result

    def test_ignores_non_debit(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de título"],
            "Valor": [100.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_boleto_indices(df)
        assert len(result) == 0


class TestIdentifyCartaoExpenseIndices:
    def test_identifies_cartao_outros(self):
        data = {
            "Data": [datetime(2024, 1, 15), datetime(2024, 1, 16)],
            "Descrição": ["Compra", "Saque"],
            "Valor": [-100.00, -50.00],
            "D/R": ["D", "D"],
            "CONTA": ["Saraiva", "BbCorrente"],
            "Categoria": ["Outros", "Outros"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_cartao_expense_indices(df)
        assert 0 in result
        assert 1 not in result

    def test_ignores_non_liability_account(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Compra"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_cartao_expense_indices(df)
        assert len(result) == 0

    def test_ignores_non_outros_category(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Compra"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["Saraiva"],
            "Categoria": ["Alimentação"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_cartao_expense_indices(df)
        assert len(result) == 0


class TestGenerateBoletoEntries:
    def test_generates_boleto_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de título"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_boleto_entries(df, {0})
        assert count == 1
        assert "2024-01-15" in lines[0]
        assert "Expenses:Boletos" in lines[1]
        assert "Assets:BR:BbCorrente" in lines[2]

    def test_empty_indices(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de título"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_boleto_entries(df, set())
        assert count == 0
        assert len(lines) == 0


class TestGenerateCartaoExpenseEntries:
    def test_generates_cartao_expense_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Compra no cartão"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["Saraiva"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_cartao_expense_entries(df, {0})
        assert count == 1
        assert "Expenses:OutrosCartao" in lines[1]


class TestGenerateExpenseEntries:
    def test_generates_expense_entry(self, sample_df):
        lines, count = generate_expense_entries(sample_df, set())
        assert count == 5

    def test_excludes_indices(self, sample_df):
        lines, count = generate_expense_entries(sample_df, {0})
        assert count == 4

    def test_excludes_saldo_inicial(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Saldo inicial"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_expense_entries(df, set())
        assert count == 0

    def test_respects_paid_status(self):
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
        lines, count = generate_expense_entries(df, set())
        assert "*" in lines[0]

    def test_pending_uses_flag_exclamation(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Despesa"],
            "Valor": [-100.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Alimentação"],
            "Situação": ["Pendente"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_expense_entries(df, set())
        assert "!" in lines[0]
