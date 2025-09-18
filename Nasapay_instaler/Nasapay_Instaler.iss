; ==============================
; Nasapay - Instalador Inno Setup (Win10/11 x64)
; Cria pastas: Arquivos, Boletos, Remessas, Retornos
; Preserva .json/.db/.csv existentes e cria defaults (em branco) se não houver
; ==============================

#define MyAppName      "Nasapay"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "Nasa Securitizadora S.A."
#define MyInstallDir   "C:\nasapay"

; >>> PASTA do PyInstaller --onedir (onde ficam Nasapay.exe e _internal)
#define MySrcDir       "C:\nasapay\dist\Nasapay"

; >>> Recursos extras (opcionais)
#define MyIconFile     "C:\nasapay\nasapay_instaler\nasapay.ico"
#define MyLogoApp      "C:\nasapay\nasapay_instaler\logo_nasapay.png"
#define MyLogoBoleto   "C:\nasapay\nasapay_instaler\logo_boleto.png"

[Setup]
AppId={{A0B57E28-ED0B-4A1F-86E9-8D3F8E4C1313}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={#MyInstallDir}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputBaseFilename=Nasapay-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
Uninstallable=yes
DirExistsWarning=no

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Dirs]
; Estrutura de dados (mantida em upgrades/uninstall)
Name: "{#MyInstallDir}";                          Flags: uninsneveruninstall
Name: "{#MyInstallDir}\Arquivos";                 Flags: uninsneveruninstall
Name: "{#MyInstallDir}\Boletos";                  Flags: uninsneveruninstall
Name: "{#MyInstallDir}\Remessas";                 Flags: uninsneveruninstall
Name: "{#MyInstallDir}\Retornos";                 Flags: uninsneveruninstall

[InstallDelete]
; Limpa apenas runtime antigo (sem tocar dados do usuário)
Type: filesandordirs; Name: "{#MyInstallDir}\_internal"
Type: filesandordirs; Name: "{#MyInstallDir}\lib"
Type: files;          Name: "{#MyInstallDir}\*.dll"
Type: files;          Name: "{#MyInstallDir}\Nasapay.exe"

[Files]
; Copia o build --onedir do PyInstaller para C:\nasapay (sem sobrescrever .json/.db/.csv)
Source: "{#MySrcDir}\*"; DestDir: "{#MyInstallDir}"; Excludes: "*.json;*.db;*.csv"; Flags: ignoreversion recursesubdirs createallsubdirs

; Recursos visuais (se não estiverem dentro do onedir)
Source: "{#MyIconFile}";   DestDir: "{#MyInstallDir}"; Flags: ignoreversion
Source: "{#MyLogoApp}";    DestDir: "{#MyInstallDir}"; Flags: ignoreversion onlyifdoesntexist
Source: "{#MyLogoBoleto}"; DestDir: "{#MyInstallDir}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{commonprograms}\Nasapay"; Filename: "{#MyInstallDir}\Nasapay.exe"; IconFilename: "{#MyInstallDir}\nasapay.ico"
Name: "{commondesktop}\Nasapay";  Filename: "{#MyInstallDir}\Nasapay.exe"; IconFilename: "{#MyInstallDir}\nasapay.ico"; Tasks: desktopicon

; [Run]
; Para abrir ao final, descomente:
; Filename: "{#MyInstallDir}\Nasapay.exe"; Flags: nowait postinstall skipifsilent

; ==============================
;  [Code] - cria defaults se não existirem
; ==============================
[Code]
function FileExistsEx(const FileName: string): Boolean;
begin
  Result := FileExists(ExpandConstant(FileName));
end;

procedure EnsureDefaultFiles();
var
  TargetDir, FJson, FDb, FCsv: string;
  DefaultJson, CsvHeader: string;
begin
  TargetDir := ExpandConstant('{#MyInstallDir}');
  FJson := TargetDir + '\config.json';
  FDb   := TargetDir + '\database.db';
  FCsv  := TargetDir + '\sequenciais.csv';

  // JSON default (campos em branco; somente paths predefinidas)
  DefaultJson :=
    '{' + #13#10 +
    '  "empresa": {' + #13#10 +
    '    "razao_social": "",' + #13#10 +
    '    "cnpj": "",' + #13#10 +
    '    "endereco": "",' + #13#10 +
    '    "cidade": "",' + #13#10 +
    '    "uf": "",' + #13#10 +
    '    "cep": "",' + #13#10 +
    '    "telefone": "",' + #13#10 +
    '    "email": ""' + #13#10 +
    '  },' + #13#10 +
    '  "parametros": {' + #13#10 +
    '    "carteira": "",' + #13#10 +
    '    "agencia": "",' + #13#10 +
    '    "conta": "",' + #13#10 +
    '    "digito": "",' + #13#10 +
    '    "codigo_cedente": "",' + #13#10 +
    '    "multa_percentual": "",' + #13#10 +
    '    "juros_dia_percentual": "",' + #13#10 +
    '    "especie_titulo": "",' + #13#10 +
    '    "ultimo_nosso_numero": "",' + #13#10 +
    '    "ultimo_sequencial_remessa": ""' + #13#10 +
    '  },' + #13#10 +
    '  "paths": {' + #13#10 +
    '    "arquivos": "C:\\\\nasapay\\\\Arquivos",' + #13#10 +
    '    "boletos":  "C:\\\\nasapay\\\\Boletos",' + #13#10 +
    '    "remessas": "C:\\\\nasapay\\\\Remessas",' + #13#10 +
    '    "retornos": "C:\\\\nasapay\\\\Retornos"' + #13#10 +
    '  }' + #13#10 +
    '}';

  // CSV default (se usar controle auxiliar)
  CsvHeader := 'nosso_numero;sequencial_remessa;data_criacao';

  if not FileExists(FJson) then
    SaveStringToFile(FJson, DefaultJson, False);

  if not FileExists(FDb) then
    // Cria .db vazio — o app cria as tabelas na primeira execução
    SaveStringToFile(FDb, '', False);

  if not FileExists(FCsv) then
    SaveStringToFile(FCsv, CsvHeader + #13#10, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(ExpandConstant('{#MyInstallDir}\Arquivos'));
    ForceDirectories(ExpandConstant('{#MyInstallDir}\Boletos'));
    ForceDirectories(ExpandConstant('{#MyInstallDir}\Remessas'));
    ForceDirectories(ExpandConstant('{#MyInstallDir}\Retornos'));
    EnsureDefaultFiles();
  end;
end;
