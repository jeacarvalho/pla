import pandas as pd
import pytest
from datetime import datetime

from organizze_shared import (
    sanitize_name,
    sanitize_description,
    get_account_path,
    get_cartao_from_conta,
    generate_pair_id,
    extract_accounts_from_df,
    extract_categories_from_df,
)


class TestSanitizeName:
    def test_basic_name(self):
        assert sanitize_name("Supermercado") == "Supermercado"

    def test_with_accent(self):
        assert sanitize_name("Alimentação") == "Alimentacao"

    def test_with_special_chars(self):
        assert sanitize_name("Loja @#$%") == "Loja"

    def test_with_numbers(self):
        assert sanitize_name("Conta 123") == "Conta123"

    def test_empty_string(self):
        assert sanitize_name("") == "Unknown"

    def test_only_spaces(self):
        assert sanitize_name("   ") == "Unknown"

    def test_na_value(self):
        assert sanitize_name(pd.NA) == "Unknown"

    def test_lowercase_to_capitalized(self):
        assert sanitize_name("supermercado extra") == "SupermercadoExtra"


class TestSanitizeDescription:
    def test_basic_description(self):
        assert sanitize_description("Compra no mercado") == "Compra no mercado"

    def test_long_description_truncated(self):
        desc = "A" * 100
        result = sanitize_description(desc)
        assert len(result) == 60
        assert result.endswith("...")

    def test_replaces_quotes(self):
        assert sanitize_description('Teste "aspas"') == "Teste 'aspas'"

    def test_removes_newlines(self):
        assert sanitize_description("Line1\nLine2") == "Line1 Line2"

    def test_na_value(self):
        assert sanitize_description(pd.NA) == "Sem descricao"


class TestGetAccountPath:
    def test_asset_account(self):
        assert get_account_path("BbCorrente") == "Assets:BR:BbCorrente"

    def test_asset_inter(self):
        assert get_account_path("BancoInter") == "Assets:BR:BancoInter"

    def test_liability_card(self):
        assert (
            get_account_path("CartaoDeCreditoInter")
            == "Liabilities:Cartao:CartaoDeCreditoInter"
        )

    def test_liability_saraiva(self):
        assert get_account_path("Saraiva") == "Liabilities:Cartao:Saraiva"

    def test_unknown_account_defaults_to_assets(self):
        assert get_account_path("ContaDesconhecida") == "Assets:BR:ContaDesconhecida"


class TestGetCartaoFromConta:
    def test_banco_inter_maps_to_cartao_inter(self):
        assert get_cartao_from_conta("BancoInter", "qualquer") == "CartaoDeCreditoInter"

    def test_c6bank_maps_to_mastercard(self):
        assert get_cartao_from_conta("C6Bank", "qualquer") == "MastercardC6Bank"

    def test_itau_personalite_maps_to_latam(self):
        assert get_cartao_from_conta("ItauPersonalite", "qualquer") == "LatamPass"

    def test_bb_corrente_smiles_detection(self):
        assert (
            get_cartao_from_conta("BbCorrente", "Smiles pontos") == "SmilesBbPlatinum"
        )

    def test_bb_corrente_saraiva_default(self):
        assert get_cartao_from_conta("BbCorrente", "Outra coisa") == "Saraiva"

    def test_unknown_conta_returns_none(self):
        assert get_cartao_from_conta("ContaDesconhecida", "desc") is None


class TestGeneratePairId:
    def test_same_indices_same_hash(self):
        id1 = generate_pair_id(1, 2)
        id2 = generate_pair_id(1, 2)
        assert id1 == id2

    def test_different_indices_different_hash(self):
        id1 = generate_pair_id(1, 2)
        id2 = generate_pair_id(2, 1)
        assert id1 != id2

    def test_hash_length(self):
        assert len(generate_pair_id(1, 2)) == 16


class TestExtractAccountsFromDf:
    def test_extracts_bank_accounts(self, sample_df):
        banks, cards = extract_accounts_from_df(sample_df)
        assert "BbCorrente" in banks
        assert "BancoInter" in banks
        assert "C6Bank" in banks
        assert len(cards) == 0

    def test_empty_df(self, empty_df):
        banks, cards = extract_accounts_from_df(empty_df)
        assert len(banks) == 0
        assert len(cards) == 0


class TestExtractCategoriesFromDf:
    def test_extracts_expense_categories(self, sample_df):
        expenses, incomes = extract_categories_from_df(sample_df)
        assert "Alimentacao" in expenses
        assert "Moradia" in expenses
        assert "Outros" in expenses

    def test_extracts_income_categories(self, sample_df):
        expenses, incomes = extract_categories_from_df(sample_df)
        assert "Recebimentos" in incomes

    def test_transferencias_excluded_from_expenses(self):
        data = {
            "Data": [
                datetime(2024, 1, 15),
                datetime(2024, 1, 16),
            ],
            "Descrição": ["Transferência", "Recebimento"],
            "Valor": [-200.00, 100.00],
            "D/R": ["D", "R"],
            "CONTA": ["BbCorrente", "BbCorrente"],
            "Categoria": ["transferência", "Recebimentos"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        expenses, incomes = extract_categories_from_df(df)
        assert "Transferencias" not in expenses
        assert "Recebimentos" in incomes

    def test_empty_df(self, empty_df):
        expenses, incomes = extract_categories_from_df(empty_df)
        assert len(expenses) == 0
        assert len(incomes) == 0
