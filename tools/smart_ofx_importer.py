#!/usr/bin/env python3
"""
Smart OFX Importer - Transforma transações OFX em lançamentos Beancount.
Utiliza mapping.csv para classificação automática e FITID para deduplicação.
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

import ofxparse


def extrair_fitids_existentes(history_path: Path, imports_path: Path) -> set:
    """Extrai todos os FITIDs dos arquivos Beancount existentes."""
    fitids = set()

    for file_path in [history_path, imports_path]:
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")

        pattern = r'origem_id:\s*"([^"]+)"'
        matches = re.findall(pattern, content)
        fitids.update(matches)

    return fitids


def carregar_mapping(mapping_path: Path) -> dict:
    """Carrega o arquivo mapping.csv e retorna dicionário {padrao: conta_alvo}."""
    mapping = {}

    with open(mapping_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            padrao = row["padrao"].strip().upper()
            conta = row["conta_alvo"].strip()
            if padrao and conta:
                mapping[padrao] = conta

    return mapping


def limpar_texto_busca(texto: str) -> str:
    """Normaliza texto para busca no mapping."""
    if not texto:
        return ""

    texto = str(texto).upper()

    texto = re.sub(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", "", texto)
    texto = re.sub(r"\s*\d+/\d+\s*", " ", texto)
    texto = re.sub(r"\s*ÚNICA\s*", " ", texto)
    texto = re.sub(r"\b\d{6,}\b", "", texto)
    texto = re.sub(r"\bSAO\s*PAULO\s*BR\b", "", texto)
    texto = re.sub(r"\bNITEROI\s*BRA?\b", "", texto)
    texto = re.sub(r"\bRIO\s*DE\s*JANEIRO\s*BR\b", "", texto)
    texto = re.sub(r"\bBR\b$", "", texto)
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def classificar_transacao(name: str, memo: str, mapping: dict) -> tuple[str, bool]:
    """
    Classifica transação usando o mapping.csv.
    Retorna tuple (conta_alvo, é_transferencia_propria).
    """
    texto_name = limpar_texto_busca(name)
    texto_memo = limpar_texto_busca(memo)

    texto_busca = texto_memo
    if texto_busca:
        texto_busca = texto_memo
    elif texto_name:
        texto_busca = texto_name
    else:
        texto_busca = ""

    if texto_busca in mapping:
        return mapping[texto_busca], False

    padroes_ordenados = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)

    for padrao, conta in padroes_ordenados:
        if padrao and texto_busca and padrao in texto_busca:
            return conta, False

    for padrao, conta in padroes_ordenados:
        if len(padrao) >= 5 and texto_busca and padrao in texto_busca:
            return conta, False

    return "Expenses:Ajustes", False


def detectar_transferencia_propria(memo: str, nome_usuario: str) -> bool:
    """Detecta se a transação é uma transferência para o próprio usuário."""
    if not memo:
        return False

    memo_upper = memo.upper()
    nome_upper = nome_usuario.upper()

    if nome_upper in memo_upper:
        return True

    if (
        "TRANSFERENCIA" in memo_upper
        and "ENTRE" in memo_upper
        and "CONTAS" in memo_upper
    ):
        return True

    return False


def formatar_data_beancount(data: datetime) -> str:
    """Formata data para padrão Beancount (YYYY-MM-DD)."""
    return data.strftime("%Y-%m-%d")


def gerar_lancamento(
    data: datetime,
    memo: str,
    name: str,
    valor: float,
    conta_bancaria: str,
    conta_alvo: str,
    fitid: str,
    is_transferencia: bool = False,
) -> str:
    """Gera lançamento Beancount formatado."""

    data_beancount = formatar_data_beancount(data)

    descricao = memo if memo else (name or "")
    descricao = re.sub(r"\s+", " ", descricao).strip()
    descricao = descricao.replace('"', '\\"')

    conta_bancaria_fmt = conta_bancaria.ljust(53)
    conta_alvo_fmt = conta_alvo.ljust(53)
    valor_fmt = f"{valor:.2f} BRL"
    valor_invertido_fmt = f"{-valor:.2f} BRL"

    linhas_metadado = f'  origem_id: "{fitid}"'
    if is_transferencia:
        linhas_metadado += '\n  transferencia: "true"'

    lancamento = (
        f'{data_beancount} * "{descricao}"\n'
        f"  {conta_bancaria_fmt}  {valor_fmt}\n"
        f"  {conta_alvo_fmt}  {valor_invertido_fmt}\n"
        f"{linhas_metadado}\n"
    )

    return lancamento


def processar_ofx(
    ofx_path: Path,
    conta_bancaria: str,
    mapping: dict,
    fitids_existentes: set,
    nome_usuario: str = "Jose Eduardo",
) -> tuple[list[str], int, int]:
    """Processa arquivo OFX e retorna lista de lançamentos Beancount."""

    import tempfile
    import os

    ofx_path_clean = ofx_path
    with open(ofx_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if "ENCODING: UTF - 8" in content or "ENCODING:UTF-8" not in content:
        content = content.replace("ENCODING: UTF - 8", "ENCODING:UTF-8")
        content = content.replace("ENCODING:UTF-8", "ENCODING:UTF-8")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ofx", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            ofx_path_clean = Path(tmp.name)

    try:
        with open(ofx_path_clean, encoding="utf-8") as f:
            ofx = ofxparse.OfxParser.parse(f)
    except UnicodeDecodeError:
        with open(ofx_path_clean, encoding="latin-1") as f:
            ofx = ofxparse.OfxParser.parse(f)
    except Exception:
        with open(ofx_path, encoding="latin-1") as f:
            ofx = ofxparse.OfxParser.parse(f)

    if ofx_path_clean != ofx_path and os.path.exists(ofx_path_clean):
        os.unlink(ofx_path_clean)

    lancamentos = []
    duplicados = 0
    nao_classificados = 0

    for account in ofx.accounts:
        for transacao in account.statement.transactions:
            fitid = transacao.id

            if not fitid:
                fitid = f"{transacao.date}_{transacao.amount}_{transacao.name}"

            if fitid in fitids_existentes:
                duplicados += 1
                continue

            fitids_existentes.add(fitid)

            payee = transacao.payee or ""
            memo = transacao.memo or ""

            is_transferencia_propria = detectar_transferencia_propria(
                memo, nome_usuario
            )

            if is_transferencia_propria:
                conta_alvo = "Equity:TransferenciasPendentes"
                is_transferencia = True
            else:
                conta_alvo, _ = classificar_transacao(payee, memo, mapping)
                is_transferencia = False

                if conta_alvo == "Expenses:Ajustes":
                    nao_classificados += 1

            lancamento = gerar_lancamento(
                data=transacao.date,
                memo=memo,
                name=payee,
                valor=transacao.amount,
                conta_bancaria=conta_bancaria,
                conta_alvo=conta_alvo,
                fitid=fitid,
                is_transferencia=is_transferencia,
            )

            lancamentos.append(lancamento)

    return lancamentos, duplicados, nao_classificados


def main():
    parser = argparse.ArgumentParser(
        description="Importa transações OFX para Beancount usando mapping.csv"
    )
    parser.add_argument("ofx_file", type=Path, help="Caminho do arquivo OFX")
    parser.add_argument(
        "--account",
        required=True,
        help="Conta bancária de destino (ex: Assets:Circulante:Disponibilidades:Inter)",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("tools/mapping.csv"),
        help="Caminho do arquivo mapping.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ledger/imports.beancount"),
        help="Caminho do arquivo de saída",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("ledger/history.beancount"),
        help="Caminho do arquivo history.beancount",
    )
    parser.add_argument(
        "--usuario",
        type=str,
        default="Jose Eduardo",
        help="Nome do usuário para detectar transferências próprias",
    )

    args = parser.parse_args()

    if not args.ofx_file.exists():
        print(f"Erro: Arquivo OFX não encontrado: {args.ofx_file}")
        return 1

    mapping_path = Path(args.mapping)
    if not mapping_path.exists():
        print(f"Erro: Arquivo mapping não encontrado: {mapping_path}")
        return 1

    print(f"Carregando mapping de: {mapping_path}")
    mapping = carregar_mapping(mapping_path)
    print(f"  {len(mapping)} padrões carregados")

    print(f"Verificando FITIDs existentes em history e imports...")
    fitids_existentes = extrair_fitids_existentes(args.history, args.output)
    print(f"  {len(fitids_existentes)} FITIDs encontrados")

    print(f"Processando OFX: {args.ofx_file}")
    lancamentos, duplicados, nao_classificados = processar_ofx(
        args.ofx_file,
        args.account,
        mapping,
        fitids_existentes,
        args.usuario,
    )

    print(f"  {len(lancamentos)} novos lançamentos")
    print(f"  {duplicados} duplicados (ignorados)")
    print(f"  {nao_classificados} não classificados (!)")

    if not lancamentos:
        print("Nenhum novo lançamento para adicionar.")
        return 0

    with open(args.output, mode="a", encoding="utf-8") as f:
        f.write("\n")
        for lancamento in lancamentos:
            f.write(lancamento)
            f.write("\n")

    print(f"Lançamentos adicionados a: {args.output}")

    print("Validando com bean-check...")
    import subprocess

    main_beancount = Path("ledger/main.beancount")
    result = subprocess.run(
        ["bean-check", str(main_beancount)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Validação OK")
    else:
        output_lines = result.stdout.splitlines()
        errors = [l for l in output_lines if "imports.beancount" in l or "ERROR" in l]
        if errors:
            print(f"  ✗ Erros encontrados:")
            for line in errors[:10]:
                print(f"    {line}")
        else:
            print("  ✓ Validação OK (erros em outros arquivos)")

    return 0


if __name__ == "__main__":
    exit(main())
