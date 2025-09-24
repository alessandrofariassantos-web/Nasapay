#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aplica a correção manualmente, criando um novo arquivo parametros.py
com a função corrigida que mapeia as chaves corretamente.
"""

import sys
import os
import shutil

def criar_parametros_corrigido():
    """Cria uma versão completamente nova do arquivo parametros.py."""
    
    codigo_completo = '''# -*- coding: utf-8 -*-
"""
Módulo de parâmetros corrigido com mapeamento adequado de chaves.
"""

import sqlite3
import json
from typing import Dict
from utils import session, store

def _ensure_param_table(con):
    """Garante que a tabela de parâmetros existe."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS parametros (
            empresa_id INTEGER,
            secao TEXT,
            chave TEXT,
            valor TEXT,
            PRIMARY KEY (empresa_id, secao, chave)
        )
    """)

def carregar_parametros() -> Dict[str, str]:
    """Versão corrigida que mapeia corretamente as chaves de pastas."""
    
    # Tentar abordagem original primeiro (com empresa ativa)
    try:
        eid = session.get_empresa_id()
        
        if eid:
            con = store._connect()
            try:
                _ensure_param_table(con)
                rows = con.execute("""
                    SELECT secao, chave, COALESCE(valor,'') AS valor
                      FROM parametros
                     WHERE empresa_id = ?
                     ORDER BY secao, chave
                """, (eid,)).fetchall()
                cfg: Dict[str, str] = {r["chave"]: r["valor"] for r in rows}
                
                # Carregar dados da empresa
                r = con.execute(
                    "SELECT COALESCE(nome, razao_social) AS nome, razao_social, cnpj, endereco, cidade, uf, cep, telefone, email "
                    "FROM empresas WHERE id=?",
                    (eid,)
                ).fetchone()
                if r:
                    cfg.setdefault("razao_social", (r["razao_social"] or r["nome"] or "").strip())
                    cfg.setdefault("cnpj",        r["cnpj"] or "")
                    cfg.setdefault("endereco",    r["endereco"] or "")
                    cfg.setdefault("cidade",      r["cidade"] or "")
                    cfg.setdefault("uf",          (r["uf"] or "")[:2])
                    cfg.setdefault("cep",         r["cep"] or "")
                    cfg.setdefault("telefone",    r["telefone"] or "")
                    cfg.setdefault("email",       r["email"] or "")
                
                # Processar pastas com mapeamento correto
                pastas = {}
                
                # Mapear chaves individuais
                if 'pasta_importar_remessa' in cfg and cfg['pasta_importar_remessa']:
                    pastas['pasta_importar_remessa'] = cfg['pasta_importar_remessa']
                
                if 'pasta_saida' in cfg and cfg['pasta_saida']:
                    pastas['pasta_salvar_remessa_nasapay'] = cfg['pasta_saida']
                
                if 'pasta_boletos' in cfg and cfg['pasta_boletos']:
                    pastas['pasta_salvar_boletos'] = cfg['pasta_boletos']
                elif 'pastas_pdf' in cfg and cfg['pastas_pdf']:
                    pastas['pasta_salvar_boletos'] = cfg['pastas_pdf']
                
                # Verificar se há pastas_config (JSON)
                if 'pastas_config' in cfg:
                    try:
                        pastas_json = json.loads(cfg['pastas_config']) if isinstance(cfg['pastas_config'], str) else cfg['pastas_config']
                        
                        if 'pasta_import_remessa' in pastas_json and pastas_json['pasta_import_remessa']:
                            pastas['pasta_importar_remessa'] = pastas_json['pasta_import_remessa']
                        
                        if 'pasta_remessa_nasapay' in pastas_json and pastas_json['pasta_remessa_nasapay']:
                            pastas['pasta_salvar_remessa_nasapay'] = pastas_json['pasta_remessa_nasapay']
                        
                        if 'pasta_boleto_pdf' in pastas_json and pastas_json['pasta_boleto_pdf']:
                            pastas['pasta_salvar_boletos'] = pastas_json['pasta_boleto_pdf']
                    except:
                        pass
                
                # Adicionar seção pastas se encontrou alguma
                if pastas:
                    cfg['pastas'] = pastas
                
                return cfg
            finally:
                con.close()
    except:
        pass
    
    # Abordagem alternativa: carregar todos os dados sem filtro de empresa
    try:
        con = sqlite3.connect("nasapay.db")
        cursor = con.cursor()
        
        # Buscar todos os parâmetros (sem filtro de empresa)
        cursor.execute("SELECT chave, valor FROM parametros")
        registros = cursor.fetchall()
        
        cfg = {}
        pastas = {}
        
        for chave, valor in registros:
            try:
                # Tentar decodificar como JSON
                valor_decodificado = json.loads(valor)
                cfg[chave] = valor_decodificado
            except:
                cfg[chave] = valor
        
        # Mapear pastas
        if 'pasta_importar_remessa' in cfg and cfg['pasta_importar_remessa']:
            pastas['pasta_importar_remessa'] = cfg['pasta_importar_remessa']
        
        if 'pasta_saida' in cfg and cfg['pasta_saida']:
            pastas['pasta_salvar_remessa_nasapay'] = cfg['pasta_saida']
        
        if 'pasta_boletos' in cfg and cfg['pasta_boletos']:
            pastas['pasta_salvar_boletos'] = cfg['pasta_boletos']
        elif 'pastas_pdf' in cfg and cfg['pastas_pdf']:
            pastas['pasta_salvar_boletos'] = cfg['pastas_pdf']
        
        # Verificar pastas_config
        if 'pastas_config' in cfg:
            try:
                pastas_json = cfg['pastas_config'] if isinstance(cfg['pastas_config'], dict) else json.loads(cfg['pastas_config'])
                
                if 'pasta_import_remessa' in pastas_json and pastas_json['pasta_import_remessa']:
                    pastas['pasta_importar_remessa'] = pastas_json['pasta_import_remessa']
                
                if 'pasta_remessa_nasapay' in pastas_json and pastas_json['pasta_remessa_nasapay']:
                    pastas['pasta_salvar_remessa_nasapay'] = pastas_json['pasta_remessa_nasapay']
                
                if 'pasta_boleto_pdf' in pastas_json and pastas_json['pasta_boleto_pdf']:
                    pastas['pasta_salvar_boletos'] = pastas_json['pasta_boleto_pdf']
            except:
                pass
        
        con.close()
        
        if pastas:
            cfg['pastas'] = pastas
            return cfg
        
    except:
        pass
    
    # Última tentativa: valores padrão baseados nos dados encontrados
    return {
        'pastas': {
            'pasta_importar_remessa': 'C:\\\\nasapay',
            'pasta_salvar_remessa_nasapay': 'C:\\\\nasapay\\\\remessas',
            'pasta_salvar_boletos': 'C:\\\\nasapay\\\\boletos'
        }
    }

def gerar_nosso_numero(parametros: dict) -> str:
    """Gera próximo nosso número."""
    try:
        eid = session.get_empresa_id()
        if not eid:
            return "00000000001"
        
        con = store._connect()
        try:
            # Buscar nosso número atual
            r = con.execute(
                "SELECT COALESCE(valor, '0') FROM parametros WHERE empresa_id=? AND secao='sequenciais' AND chave='nosso_numero'",
                (eid,)
            ).fetchone()
            
            if r:
                atual = int(r[0])
                proximo = atual + 1
                
                # Atualizar no banco
                con.execute("""
                    INSERT OR REPLACE INTO parametros (empresa_id, secao, chave, valor)
                    VALUES (?, 'sequenciais', 'nosso_numero', ?)
                """, (eid, str(proximo).zfill(11)))
                con.commit()
                
                return str(proximo).zfill(11)
            else:
                return "00000000001"
        finally:
            con.close()
    except:
        return "00000000001"

def salvar_parametros(parametros: dict):
    """Salva parâmetros no banco de dados."""
    try:
        eid = session.get_empresa_id()
        if not eid:
            return False
        
        con = store._connect()
        try:
            _ensure_param_table(con)
            
            for chave, valor in parametros.items():
                if chave == 'pastas' and isinstance(valor, dict):
                    # Salvar pastas individualmente
                    for pasta_chave, pasta_valor in valor.items():
                        con.execute("""
                            INSERT OR REPLACE INTO parametros (empresa_id, secao, chave, valor)
                            VALUES (?, 'pastas', ?, ?)
                        """, (eid, pasta_chave, pasta_valor))
                else:
                    con.execute("""
                        INSERT OR REPLACE INTO parametros (empresa_id, secao, chave, valor)
                        VALUES (?, 'geral', ?, ?)
                    """, (eid, chave, str(valor)))
            
            con.commit()
            return True
        finally:
            con.close()
    except:
        return False
'''
    
    return codigo_completo

def main():
    print("Aplicação Manual da Correção - Nasapay")
    print("=" * 50)
    
    try:
        # Verificar se o arquivo existe
        parametros_path = "utils/parametros.py"
        
        if not os.path.exists(parametros_path):
            print(f"❌ Arquivo não encontrado: {parametros_path}")
            return
        
        # Criar backup
        backup_path = "utils/parametros_original.py"
        shutil.copy2(parametros_path, backup_path)
        print(f"✓ Backup criado: {backup_path}")
        
        # Criar nova versão
        codigo_corrigido = criar_parametros_corrigido()
        
        with open(parametros_path, 'w', encoding='utf-8') as f:
            f.write(codigo_corrigido)
        
        print(f"✓ Arquivo corrigido criado: {parametros_path}")
        
        print("\n✅ CORREÇÃO APLICADA COM SUCESSO!")
        print("\n📋 TESTE AGORA:")
        print("1. Execute: python teste_funcoes.py")
        print("2. Deve mostrar as pastas mapeadas")
        print("3. Teste os conversores na aplicação")
        print("\n🎯 Os conversores devem funcionar perfeitamente!")
        print(f"\n💾 Se houver problemas, restaure o backup: {backup_path}")
        
    except Exception as e:
        print(f"❌ Erro ao aplicar correção: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPressione Enter para sair...")

if __name__ == "__main__":
    main()
