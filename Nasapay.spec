# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# força levar todos os módulos dos seus pacotes locais
hiddenimports = (
    collect_submodules('src')
    + collect_submodules('utils')
    + [
        'utils.ui_envio',
        'utils.ui_envio.core',
        'utils.ui_envio.smtp',
        'utils.ui_envio.assinatura',
        'utils.ui_envio.common',
        'utils.ui_envio.data',
        'utils.ui_envio.modelo_msg',
        'utils.ui_envio.pdftext',
    ]
)

# leve também quaisquer dados internos desses pacotes, se houver
datas = (
    collect_data_files('utils')
    + collect_data_files('src')
    + [
        (r"C:\nasapay\nasapay_instaler\logo_nasapay.png", "."),
        (r"C:\nasapay\nasapay_instaler\logo_boleto.png", "."),
    ]
)

a = Analysis(
    ['main.py'],
    pathex=[r'C:\nasapay'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Nasapay',
    debug=False,                # mude p/ True se quiser console p/ debug
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,              # mude p/ True se quiser ver erros no console
    icon=r"C:\nasapay\nasapay_instaler\nasapay.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Nasapay',
)
