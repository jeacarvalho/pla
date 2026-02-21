#!/usr/bin/env python3
"""
Pipeline de Processamento Organizze
Executa as 3 etapas em sequência:
  1. Consolida arquivos XLS em unificado.xlsx
  2. Adiciona coluna D/R (Despesa/Receita)
  3. Ordena por Data e Valor para parear transferências
"""

from importers import consolidate, etapa1_dr, etapa2_ordenar


def main():
    print("=" * 60)
    print("INICIANDO PIPELINE ORGANIZZE")
    print("=" * 60)

    print("\n[1/3] Consolidando arquivos...")
    consolidate.main()

    print("\n[2/3] Processando D/R...")
    etapa1_dr.main()

    print("\n[3/3] Ordenando por Data e Valor...")
    etapa2_ordenar.main()

    print("\n" + "=" * 60)
    print("PIPELINE CONCLUÍDO COM SUCESSO")
    print("=" * 60)
    print("Arquivo final: data/unificado_dr_ordenado.xlsx")


if __name__ == "__main__":
    main()
