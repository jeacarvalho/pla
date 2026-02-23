import pandas as pd
import pytest
from datetime import datetime

import sys

sys.path.insert(0, "/home/s015533607/Documentos/desenv/pla/importers")

from card_payments_handler import (
    _get_cartao_from_conta,
    identify_card_payment_indices,
    generate_card_payment_entries,
)


class TestGetCartaoFromConta:
    def test_banco_inter_returns_cartao_inter(self):
        result = _get_cartao_from_conta("BancoInter", "qualquer", datetime(2024, 1, 1))
        assert result == "CartaoDeCreditoInter"

    def test_c6bank_returns_mastercard(self):
        result = _get_cartao_from_conta("C6Bank", "qualquer", datetime(2024, 1, 1))
        assert result == "MastercardC6Bank"

    def test_itau_returns_latam(self):
        result = _get_cartao_from_conta(
            "ItauPersonalite", "qualquer", datetime(2024, 1, 1)
        )
        assert result == "LatamPass"

    def test_bb_before_threshold_returns_saraiva(self):
        result = _get_cartao_from_conta("BbCorrente", "qualquer", datetime(2023, 1, 1))
        assert result == "Saraiva"

    def test_bb_smiles_after_threshold_returns_smiles(self):
        result = _get_cartao_from_conta("BbCorrente", "Smiles", datetime(2024, 1, 1))
        assert result == "SmilesBbPlatinum"

    def test_bb_other_after_threshold_returns_saraiva(self):
        result = _get_cartao_from_conta("BbCorrente", "Fatura", datetime(2024, 1, 1))
        assert result == "Saraiva"

    def test_bb_after_2025_returns_pendente(self):
        result = _get_cartao_from_conta("BbCorrente", "Fatura", datetime(2025, 3, 1))
        assert result == "BbCorrente_Pendente"

    def test_unknown_conta_returns_none(self):
        result = _get_cartao_from_conta(
            "ContaDesconhecida", "qualquer", datetime(2024, 1, 1)
        )
        assert result is None


class TestIdentifyCardPaymentIndices:
    def test_identifies_pagamento_fatura(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_card_payment_indices(df)
        assert 0 in result

    def test_identifies_payment_keyword(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Payment invoice"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_card_payment_indices(df)
        assert 0 in result

    def test_ignores_non_debit(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [500.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_card_payment_indices(df)
        assert len(result) == 0

    def test_ignores_non_asset_account(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["Saraiva"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        result = identify_card_payment_indices(df)
        assert len(result) == 0


class TestGenerateCardPaymentEntries:
    def test_generates_entry(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_card_payment_entries(df, {0})
        assert count == 1
        assert "Liabilities:Cartao:Saraiva" in lines[1]

    def test_generates_entry_for_banco_inter(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["BancoInter"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_card_payment_entries(df, {0})
        assert count == 1
        assert "Liabilities:Cartao:CartaoDeCreditoInter" in lines[1]

    def test_empty_indices(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Pagamento de fatura"],
            "Valor": [-500.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_card_payment_entries(df, set())
        assert count == 0
        assert len(lines) == 0
