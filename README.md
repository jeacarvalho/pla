# PLA - Personal Ledger Automation

Sistema de contabilidade pessoal de partidas dobradas baseado em Beancount (Plain Text Accounting).

## Objetivo

Automação da vida financeira pessoal integrando dados legados (Organizze) e importações manuais periódicas.

## Quick Start

```bash
# Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Rodar interface web (Fava)
fava ledger/main.beancount
```

## Estrutura

```
pla/
├── ledger/        # Arquivos .beancount
├── importers/     # Scripts de ETL
├── config/        # Mapeamentos YAML
└── data/          # Dados brutos (não versionado)
```

## Comandos Úteis

```bash
# Validar ledger
bean-check ledger/main.beancount

# Verificar saldo
bean-report ledger/main.beancount bal
```
