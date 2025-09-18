# Nasapay v1 — Auditoria de Pasta

**Pasta analisada:** `c:\nasapay`  
**Data da análise:** 2025-09-12 13:22:42

**Arquivos:** 36 .py, 2 .json, 2 .csv, 1 DBs, 20 imagens, total ~ 114.0 MB

## Possíveis pontos de entrada (main)
- audit_nasapay.py
- main.py

## Tecnologias / Pistas detectadas
- Desktop GUI (Tkinter)
- E-mail (smtplib)
- E-mail utils (email)
- PDF generation (reportlab)
- SQLite DB
- ZIP packaging (zipfile)

## Arquivos Python (resumo)
### __init__.py

### audit_nasapay.py
- Imports: ast, csv, datetime, io, json, pathlib, re, sqlite3, sys
- Funções: human_size, safe_read_text, parse_python, summarize_requirements, list_sqlite_schema, detect_frameworks, main

### main.py
- Imports: PIL, cadastros, ctypes, importlib, os, re, src, sys, tkinter, traceback, types, utils
- Classes: MenuLabel(4 métodos)
- Funções: _excepthook, _preferred_logo_path, _kill_near_white, _fallback_logo, _resolve_open_envio_boletos, _resolve_nn_registry, _ensure_cadastros_pkg, _install_cadastros_fallback, _handle_parametros_import_error, iniciar_janela, __init__, _on_enter

### src\__init__.py

### src\boletos.py
- Imports: datetime, os, reportlab, src, tkinter, utils
- Funções: draw_logo_fit, draw_i25, format_valor_brl, _parse_brl_to_float, _parse_pct_to_float, _fmt_cpf, _fmt_cnpj, format_doc_pagador, format_doc, pad_left, _unique_sequencial, _popup_boletos_gerados

### src\conversor_bradesco.py
- Imports: datetime, src, tkinter, utils
- Funções: _digits, _normalize_tipo_insc, converter_arquivo_bradesco

### src\conversor_xml.py
- Imports: datetime, os, tkinter, utils, xml
- Funções: converter_arquivo_xml

### src\extrator_titulos.py
- Imports: datetime, os, re, utils, xml
- Funções: _digits, _doc_base_sem_dv, _doc_pagador_14, _formatar_cep, _formatar_fone, extrair_titulos_de_arquivo, extrair_de_xml, extrair_de_bradesco

### src\remessa_meta.py
- Imports: json, os, re
- Funções: record_remessa_meta

### src\retorno_bmp.py
- Imports: json, os, tkinter
- Funções: _load_cfg, _ddmmaa, _money13, _status, parse_retorno_bmp, abrir_retorno_bmp_gui

### src\retorno_to_bradesco400.py
- Imports: datetime, json, os, parametros, tkinter, utils
- Funções: _load_cfg, _last_meta, _benef_from_meta_or_cfg, _bump_seq_retorno, _slice_try, _fmt_valor, _parse_bmp_retorno, _header_retorno_bradesco, _trailer_retorno_bradesco, _detail_retorno_bradesco, converter_bmp_para_bradesco400, pick

### utils\__init__.py

### utils\boletos_bmp.py
- Imports: datetime
- Funções: _limpa_valor_brl, fator_vencimento, campo_livre, _mod10, _mod11_barcode, montar_codigo_barras, montar_linha_digitavel, dv_nosso_numero_base7

### utils\cadastros\__init__.py

### utils\cadastros\cobranca.py
- Imports: tkinter
- Funções: _format_percent_from_raw, _attach_percent_mask, build_aba_cobranca, on_keypress, _linha, _bind_upper, on_key

### utils\cadastros\conta_email.py
- Imports: dns, email, re, smtplib, socket, ssl, subprocess, tkinter, utils
- Funções: _digits, _bind_lower, _bind_digits, _linha, _nslookup_mx, _detect_provider_by_mx, _friendly_smtp_error, build_aba_email, _preset_generico, _preset_seu_dominio, _testar_portas_async, _enviar_teste_async

### utils\cadastros\conta_nasapay.py
- Imports: re, tkinter
- Funções: _digits, _bind_digits, _pad_zeros_on_blur, build_aba_conta, on_key, on_blur, _linha, _ced_blur

### utils\cadastros\empresa.py
- Imports: re, tkinter, utils
- Funções: _upper_text, _lower_email, _uf_mask, _digits, _mask_cnpj, _mask_cep_oldstyle, _mask_tel_var, _index_after_n_digits, _bind_mask_keep_caret, _bind_simple_case, _linha, _warn_if_incomplete_cep

### utils\cadastros\pastas.py
- Imports: json, os, tkinter
- Funções: _carregar_config, _salvar_config, _garante_pasta, build_aba_pastas, open_pastas_tab, _espelha_legado, _linha, linha_pasta, salvar, escolher, _on_write, escolher

### utils\gerar_remessa.py
- Imports: datetime, os, re, tkinter, unicodedata, utils, zipfile
- Funções: _set_range, _dig, _alfan, _linha_vazia, _set_seq_final, _centavos_from_brl, _fmt_date_ddmmaa, _pct_to_hundredths3, _juros_dia_centavos, _proximo_sequencial, _persistir_sequencial, _codigo_arquivo_remessa

### utils\mailer.py
- Imports: email, os, smtplib, ssl, typing
- Funções: _coerce_bool, send_email_with_attachments

### utils\nn_registry.py
- Imports: csv, datetime, os, re, typing
- Funções: _dig, _doc_norm, _centavos_from_any, _fmt_brl, _basename, _ensure_csv, _load_rows, _write_rows, _key_from_titulo, next_nosso_numero, buscar_nosso_numero, registrar_titulos

### utils\nn_registry_ui.py
- Imports: os, tkinter
- Funções: _open_window, open_registry_window, open_nn_registry, open_nn_registry_window, autosize_columns, set_status, refresh, on_export, on_import, on_delete, on_edit, on_open_csv

### utils\parametros.py
- Imports: cadastros, json, os, tkinter, utils
- Classes: _State(3 métodos)
- Funções: _defaults, _read_json, carregar_parametros, salvar_parametros, gerar_nosso_numero, _bind_digits_limit, _bind_pad_zeros_on_blur, _build_aba_sequenciais, _tab_text, abrir_parametros, __init__, var

### utils\popup_confirmacao.py
- Imports: re, tkinter
- Funções: _parse_brl, _fmt_brl, _center_on_parent, popup_confirmacao_titulos, fechar

### utils\store.py
- Imports: datetime, hashlib, os, sqlite3, typing, utils
- Funções: _ensure_dir, _connect, _table_info, _has_column, _try_add_column, init_db, _digits, _to_centavos, _sha1_file, _today_str, upsert_pagador_from_titulo, ensure_titulo

### utils\ui_busy.py
- Imports: PIL, os, threading, tkinter
- Classes: BusyOverlay(4 métodos)
- Funções: run_with_busy, __init__, _draw_logo, _tick, close, worker, finish

### utils\ui_envio\__init__.py
- Imports: assinatura, core, modelo_msg

### utils\ui_envio\assinatura.py
- Imports: common, html, parametros, re, tkinter, utils
- Funções: html_escape, _text_to_html, open_assinatura_tab, tags_at, color_of, _apply_font, _toggle, _pick_color, _choose_logo, _persist, _fechar, _resize

### utils\ui_envio\common.py
- Imports: tkinter
- Funções: html_escape, _add_page, _center_on_parent, _close

### utils\ui_envio\core.py
- Imports: assinatura, os, parametros, pdftext, re, smtp, tkinter, unicodedata, utils
- Funções: _add_page, _center_on_parent, _titles_table_html, _build_html_message, _current_pagador, _selected_titles, _collect_attachments, _candidate_pdf_dirs, _find_pdf_for_title, _enviar_sacados, _ui_envio_sacado, open_modelo_tab

### utils\ui_envio\data.py
- Docstring: Camada de dados para a tela de Envio.
- Imports: datetime, os, re, sqlite3, typing
- Funções: _con, _fmt_br_dt, _digits, _fmt_phone, _fmt_email, _is_valid_email, _ensure_columns, load_initial, _fetch_pagadores, _fetch_boletos_do_pagador, refresh_pagadores, save_pagador_field

### utils\ui_envio\modelo_msg.py
- Imports: parametros, tkinter, utils
- Funções: _center_on_parent, open_modelo_mensagem_tab, _close, _make_tree, _insert_from, _save, _close

### utils\ui_envio\pdftext.py
- Imports: PyPDF2, os, pdf2image, pdfminer, pytesseract
- Funções: extract_text

### utils\ui_envio\smtp.py
- Imports: email, mimetypes, os, smtplib, ssl, uuid
- Funções: _from_header, img_to_cid, _attach_inline, _attach_files, _smtp_connect, send_html

### utils\validador_remessa.py
- Imports: os, re, utils
- Funções: _slice, _dig, _must_len, validar_remessa_bmp

## Arquivos JSON (chaves de alto nível)
- config.json: razao_social, cnpj, endereco, cidade, uf, cep, telefone, email, agencia, conta, digito, carteira, codigo_cedente, nosso_numero, ultima_remessa, especie, multa, juros, instrucao1, instrucao2
- nn_registry.json: 

## CSV (cabeçalhos)
- nn_registry.csv: documento;vencimento;valor_centavos;doc_pagador;sacado;nosso_numero;agencia;conta;carteira;arquivo;criado_em
- sequenciais.csv: nosso_numero;sequencial_remessa;data_criacao

## Bancos de dados SQLite (esquema)
### nasapay.db
- table: boleto
  - columns (8): id, titulo_id, pdf_path, pdf_sha1, generated_at, email_para, email_enviado_em, email_msg_id
- table: config_pastas
  - columns (3): empresa_id, tipo, caminho
- table: contas_bancarias
  - columns (15): id, bank_code, agencia, conta, conta_dv, carteira, variacao, convenio, codigo_cedente, beneficiario_nome, beneficiario_doc, apelido, banco, agencia_dv, empresa_id
- table: email_log
  - columns (7): id, titulo_id, to, subject, sent_at, status, error
- table: email_status
  - columns (5): sacado_id, doc, first_sent_ts, last_sent_ts, send_count
- table: empresas
  - columns (49): id, razao_social, cnpj, endereco, cidade, uf, cep, telefone, email, banco, agencia, agencia_dv, conta, conta_dv, carteira, especie, multa, juros, codigo_cedente, convenio, nosso_numero_atual, ultima_remessa, smtp_nome_remetente, smtp_email, smtp_host, smtp_porta, smtp_usuario, smtp_senha, smtp_tls_ssl, smtp_requer_auth, smtp_security, smtp_auth, smtp_teste_destino, smtp_assinatura_texto, smtp_assinatura_imagem, smtp_assunto_padrao, smtp_modelo_msg_raw, modelo_font, modelo_size, pasta_remessas, pasta_retorno, pasta_boletos, pasta_importacao, pasta_data, pasta_dist, ativo, nome, created_at, updated_at
- table: pagador
  - columns (12): id, doc, nome, email, endereco, cidade, uf, cep, telefone, created_at, fantasia, contato
- table: pagador_meta
  - columns (3): pagador_id, fantasia, contato
- table: sacados
  - columns (11): id, razao, fantasia, telefone, email, contato, endereco, cidade, uf, cep, updated_ts
- table: settings
  - columns (2): key, json
- table: sqlite_sequence
  - columns (2): name, seq
- table: titulo
  - columns (15): id, pagador_id, origem, documento, nosso_numero, nn_dv, carteira, valor_centavos, vencimento, emissao, status, created_at, send_count, first_sent_ts, last_sent_ts
- table: titulo_email_status
  - columns (3): titulo_id, status, last_sent_ts
- table: titulos
  - columns (12): id, sacado_id, doc, venc, valor, nosso, status_email, first_sent_ts, last_sent_ts, send_count, pdf_path, extra_paths
- table: usuarios
  - columns (5): id, nome, login, senha_hash, ativo
- table: usuarios_empresas
  - columns (2): id_usuario, id_empresa

## Outros arquivos de texto
- Arquivos\1408251.txt
- Arquivos\9011861.TXT
- Arquivos\cobrem001_0046_44536-3_270825_001.TXT
- Arquivos\cobrem001_0046_44536-3_270825_002.TXT
- build\Nasapay\warn-Nasapay.txt
- dist\Nasapay\_internal\setuptools\_vendor\importlib_metadata-8.0.0.dist-info\top_level.txt
- dist\Nasapay\_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt
- nasapay_audit_report.md

