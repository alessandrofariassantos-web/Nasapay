#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para testar se as funções dos conversores existem e funcionam.
Coloque este arquivo na pasta raiz do Nasapay (C:\nasapay) e execute:
python teste_funcoes.py
"""

import sys
import os

# Adicionar caminhos necessários
sys.path.insert(0, '.')
sys.path.insert(0, 'utils')
sys.path.insert(0, 'src')

def testar_conversor_xml():
    print("=== Testando Conversor XML ===")
    try:
        import src.conversor_xml as cx
        print(f"✓ Módulo importado: {cx}")
        
        if hasattr(cx, 'open_conversor_xml'):
            print("✓ Função open_conversor_xml existe")
            print(f"  Função: {cx.open_conversor_xml}")
        else:
            print("✗ Função open_conversor_xml NÃO existe")
            print(f"  Funções disponíveis: {[f for f in dir(cx) if not f.startswith('_')]}")
            
        if hasattr(cx, 'converter_arquivo_xml'):
            print("✓ Função converter_arquivo_xml existe")
        else:
            print("✗ Função converter_arquivo_xml NÃO existe")
            
    except Exception as e:
        print(f"✗ Erro ao importar: {e}")
        import traceback
        traceback.print_exc()

def testar_conversor_bradesco():
    print("\n=== Testando Conversor Bradesco ===")
    try:
        import src.conversor_bradesco as cb
        print(f"✓ Módulo importado: {cb}")
        
        if hasattr(cb, 'open_conversor_bradesco'):
            print("✓ Função open_conversor_bradesco existe")
        else:
            print("✗ Função open_conversor_bradesco NÃO existe")
            print(f"  Funções disponíveis: {[f for f in dir(cb) if not f.startswith('_')]}")
            
    except Exception as e:
        print(f"✗ Erro ao importar: {e}")
        import traceback
        traceback.print_exc()

def testar_conversor_bb240():
    print("\n=== Testando Conversor BB240 ===")
    try:
        import src.conversor_bb240 as cbb
        print(f"✓ Módulo importado: {cbb}")
        
        if hasattr(cbb, 'open_conversor_bb240'):
            print("✓ Função open_conversor_bb240 existe")
        else:
            print("✗ Função open_conversor_bb240 NÃO existe")
            print(f"  Funções disponíveis: {[f for f in dir(cbb) if not f.startswith('_')]}")
            
    except Exception as e:
        print(f"✗ Erro ao importar: {e}")
        import traceback
        traceback.print_exc()

def testar_validador():
    print("\n=== Testando Validador ===")
    try:
        import utils.validador_remessa as vr
        print(f"✓ Módulo importado: {vr}")
        
        if hasattr(vr, 'open_validador_remessa'):
            print("✓ Função open_validador_remessa existe")
        else:
            print("✗ Função open_validador_remessa NÃO existe")
            print(f"  Funções disponíveis: {[f for f in dir(vr) if not f.startswith('_')]}")
            
    except Exception as e:
        print(f"✗ Erro ao importar: {e}")
        import traceback
        traceback.print_exc()

def testar_parametros():
    print("\n=== Testando Parâmetros ===")
    try:
        from utils.parametros import carregar_parametros
        parametros = carregar_parametros()
        print(f"✓ Parâmetros carregados: {type(parametros)}")
        print(f"  Pastas: {parametros.get('pastas', {})}")
    except Exception as e:
        print(f"✗ Erro ao carregar parâmetros: {e}")
        import traceback
        traceback.print_exc()

def verificar_cache():
    print("\n=== Verificando Cache ===")
    cache_dirs = []
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if d == '__pycache__':
                cache_dirs.append(os.path.join(root, d))
    
    if cache_dirs:
        print("✗ Encontrados diretórios de cache:")
        for cache_dir in cache_dirs:
            print(f"  {cache_dir}")
        print("  Execute: for /d /r . %d in (__pycache__) do @rmdir /s /q \"%d\"")
    else:
        print("✓ Nenhum cache encontrado")

if __name__ == "__main__":
    print("Teste de Funções Nasapay")
    print("=" * 50)
    
    verificar_cache()
    testar_parametros()
    testar_conversor_xml()
    testar_conversor_bradesco()
    testar_conversor_bb240()
    testar_validador()
    
    print("\n" + "=" * 50)
    print("Teste concluído!")
    input("Pressione Enter para sair...")
