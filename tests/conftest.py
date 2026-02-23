import pandas as pd
import pytest
from datetime import datetime


@pytest.fixture
def sample_expense_row():
    return pd.Series(
        {
            "Data": datetime(2024, 1, 15),
            "Descrição": "Supermercado Extra",
            "Valor": -150.50,
            "D/R": "D",
            "CONTA": "BbCorrente",
            "Categoria": "Alimentação",
            "Situação": "Pago",
        }
    )


@pytest.fixture
def sample_income_row():
    return pd.Series(
        {
            "Data": datetime(2024, 1, 10),
            "Descrição": "Salário Janeiro",
            "Valor": 5000.00,
            "D/R": "R",
            "CONTA": "BbCorrente",
            "Categoria": "Recebimentos",
            "Situação": "Pago",
        }
    )


@pytest.fixture
def sample_transfer_d_row():
    return pd.Series(
        {
            "Data": datetime(2024, 1, 20),
            "Descrição": "Transferência para Inter",
            "Valor": -200.00,
            "D/R": "D",
            "CONTA": "BbCorrente",
            "Categoria": "Transferências",
            "Situação": "Pago",
        }
    )


@pytest.fixture
def sample_transfer_r_row():
    return pd.Series(
        {
            "Data": datetime(2024, 1, 20),
            "Descrição": "Transferência recebida do BB",
            "Valor": 200.00,
            "D/R": "R",
            "CONTA": "BancoInter",
            "Categoria": "Transferências",
            "Situação": "Pago",
        }
    )


@pytest.fixture
def sample_card_payment_row():
    return pd.Series(
        {
            "Data": datetime(2024, 1, 25),
            "Descrição": "Pagamento de fatura - Saraiva",
            "Valor": -500.00,
            "D/R": "D",
            "CONTA": "BbCorrente",
            "Categoria": "Outros",
            "Situação": "Pago",
        }
    )


@pytest.fixture
def sample_df():
    data = {
        "Data": [
            datetime(2024, 1, 15),
            datetime(2024, 1, 16),
            datetime(2024, 1, 17),
            datetime(2024, 1, 18),
            datetime(2024, 1, 19),
            datetime(2024, 1, 20),
            datetime(2024, 1, 21),
        ],
        "Descrição": [
            "Supermercado",
            "Salário",
            "Transferência para Inter",
            "Transferência recebida do BB",
            "Pagamento de fatura",
            "Saque ATM",
            "Aluguel",
        ],
        "Valor": [
            -100.00,
            3000.00,
            -200.00,
            200.00,
            -500.00,
            -300.00,
            -1500.00,
        ],
        "D/R": [
            "D",
            "R",
            "D",
            "R",
            "D",
            "D",
            "D",
        ],
        "CONTA": [
            "BbCorrente",
            "BbCorrente",
            "BbCorrente",
            "BancoInter",
            "BbCorrente",
            "BbCorrente",
            "C6Bank",
        ],
        "Categoria": [
            "Alimentação",
            "Recebimentos",
            "Transferências",
            "Transferências",
            "Outros",
            "Transferências",
            "Moradia",
        ],
        "Situação": [
            "Pago",
            "Pago",
            "Pago",
            "Pago",
            "Pago",
            "Pago",
            "Pago",
        ],
    }
    return pd.DataFrame(data)


@pytest.fixture
def empty_df():
    return pd.DataFrame(
        columns=["Data", "Descrição", "Valor", "D/R", "CONTA", "Categoria", "Situação"]
    )
