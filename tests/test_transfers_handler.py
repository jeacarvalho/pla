import pandas as pd
import pytest
from datetime import datetime

import sys

sys.path.insert(0, "/home/s015533607/Documentos/desenv/pla/importers")

from transfers_handler import (
    identify_transfers,
    generate_transfer_entries,
    generate_orphan_transfer_entries,
)


class TestIdentifyTransfers:
    def test_identifies_paired_transfers(self):
        data = {
            "Data": [
                datetime(2024, 1, 15),
                datetime(2024, 1, 15),
            ],
            "Descrição": [
                "Transferência para Inter",
                "Transferência recebida do BB",
            ],
            "Valor": [-200.00, 200.00],
            "D/R": ["D", "R"],
            "CONTA": ["BbCorrente", "BancoInter"],
            "Categoria": ["Transferências", "Transferências"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        processed, orphans = identify_transfers(df, set())
        assert len(processed) == 2
        assert len(orphans) == 0

    def test_identifies_saldo_inicial(self):
        data = {
            "Data": [datetime(2024, 1, 1)],
            "Descrição": ["Saldo inicial"],
            "Valor": [1000.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        processed, orphans = identify_transfers(df, set())
        assert len(processed) == 0
        assert len(orphans) == 1
        assert orphans[0]["tipo"] == "saldo_inicial"

    def test_identifies_ajuste(self):
        data = {
            "Data": [datetime(2024, 1, 1)],
            "Descrição": ["Ajuste de saldo"],
            "Valor": [10.00],
            "D/R": ["R"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        processed, orphans = identify_transfers(df, set())
        assert len(processed) == 0
        assert len(orphans) == 1
        assert orphans[0]["tipo"] == "ajuste"

    def test_ignores_excluded_indices(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Transferência"],
            "Valor": [-200.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Transferências"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        processed, orphans = identify_transfers(df, {0})
        assert len(processed) == 0
        assert len(orphans) == 0

    def test_identifies_orphan_transfer(self):
        data = {
            "Data": [
                datetime(2024, 1, 15),
                datetime(2024, 1, 15),
            ],
            "Descrição": ["Transferência D", "Transferência R"],
            "Valor": [-200.00, 200.00],
            "D/R": ["D", "R"],
            "CONTA": ["BbCorrente", "C6Bank"],
            "Categoria": ["outros", "outros"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        processed, orphans = identify_transfers(df, set())
        assert len(processed) == 2
        assert len(orphans) == 0


class TestGenerateTransferEntries:
    def test_generates_transfer_entry(self):
        data = {
            "Data": [
                datetime(2024, 1, 15),
                datetime(2024, 1, 15),
            ],
            "Descrição": [
                "Transferência para Inter",
                "Transferência recebida",
            ],
            "Valor": [-200.00, 200.00],
            "D/R": ["D", "R"],
            "CONTA": ["BbCorrente", "BancoInter"],
            "Categoria": ["Transferências", "Transferências"],
            "Situação": ["Pago", "Pago"],
        }
        df = pd.DataFrame(data)
        processed = {0, 1}
        lines, count = generate_transfer_entries(df, processed)
        assert count == 1
        assert "Assets:BR:BbCorrente" in lines[1]
        assert "Assets:BR:BancoInter" in lines[2]

    def test_identifies_saque_atm(self):
        data = {
            "Data": [datetime(2024, 1, 15)],
            "Descrição": ["Saque ATM"],
            "Valor": [-300.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        processed = {0}
        lines, count = generate_transfer_entries(df, processed)
        assert count == 0


class TestGenerateOrphanTransferEntries:
    def test_generates_saldo_inicial_entry(self):
        orphans = [
            {
                "idx": 0,
                "conta": "BbCorrente",
                "valor": 1000.00,
                "data": datetime(2024, 1, 1),
                "dr": "D",
                "desc": "Saldo inicial",
                "tipo": "saldo_inicial",
            }
        ]
        data = {
            "Data": [datetime(2024, 1, 1)],
            "Descrição": ["Saldo inicial"],
            "Valor": [1000.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_orphan_transfer_entries(orphans, df)
        assert count == 1
        assert "Equity:SaldoInicial" in lines[2]

    def test_generates_ajuste_debit_entry(self):
        orphans = [
            {
                "idx": 0,
                "conta": "BbCorrente",
                "valor": 10.00,
                "data": datetime(2024, 1, 1),
                "dr": "D",
                "desc": "Ajuste",
                "tipo": "ajuste",
            }
        ]
        data = {
            "Data": [datetime(2024, 1, 1)],
            "Descrição": ["Ajuste"],
            "Valor": [-10.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Outros"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_orphan_transfer_entries(orphans, df)
        assert count == 1
        assert "Equity:Ajustes" in lines[2]

    def test_generates_orphan_transfer_entry(self):
        orphans = [
            {
                "idx": 0,
                "conta": "BbCorrente",
                "valor": 200.00,
                "data": datetime(2024, 1, 1),
                "dr": "D",
                "desc": "Transferência",
                "debug_motivo": "sem_par_identificado_D",
            }
        ]
        data = {
            "Data": [datetime(2024, 1, 1)],
            "Descrição": ["Transferência"],
            "Valor": [-200.00],
            "D/R": ["D"],
            "CONTA": ["BbCorrente"],
            "Categoria": ["Transferências"],
            "Situação": ["Pago"],
        }
        df = pd.DataFrame(data)
        lines, count = generate_orphan_transfer_entries(orphans, df)
        assert count == 1
        assert "Equity:TransferenciasPendentes" in lines[1]
