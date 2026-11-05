$ErrorActionPreference = "SilentlyContinue"

$catalogo = @{}
$wsh = New-Object -ComObject WScript.Shell

function Adicionar-App($nome, $tipo, $destino, $origem) {
    if ([string]::IsNullOrWhiteSpace($nome) -or
        [string]::IsNullOrWhiteSpace($destino)) {
        return
    }

    $chave = "$tipo|$destino".ToLowerInvariant()

    if (-not $catalogo.ContainsKey($chave)) {
        $catalogo[$chave] = [PSCustomObject]@{
            name = $nome.Trim()
            type = $tipo
            target = $destino
            source = $origem
        }
    }
}

Write-Host "`n[1/4] Lendo atalhos do Menu Iniciar..." -ForegroundColor Cyan

$pastas = @(
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs",
    "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
)

foreach ($pasta in $pastas) {
    if (Test-Path $pasta) {
        Get-ChildItem $pasta -Recurse -File -Include *.lnk |
            ForEach-Object {
                try {
                    $atalho = $wsh.CreateShortcut($_.FullName)

                    if ($atalho.TargetPath) {
                        Adicionar-App `
                            $_.BaseName `
                            "shortcut" `
                            $_.FullName `
                            "Menu Iniciar"
                    }
                } catch {}
            }
    }
}

Write-Host "[2/4] Lendo aplicativos do Windows..." -ForegroundColor Cyan

if (Get-Command Get-StartApps -ErrorAction SilentlyContinue) {
    Get-StartApps | ForEach-Object {
        Adicionar-App $_.Name "appx" $_.AppID "Windows"
    }
}

Write-Host "[3/4] Lendo programas instalados..." -ForegroundColor Cyan

$chavesRegistro = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
)

foreach ($chave in $chavesRegistro) {
    Get-ItemProperty $chave | ForEach-Object {
        $nome = $_.DisplayName
        $icone = [string]$_.DisplayIcon

        if ($nome -and $icone) {
            $executavel = $null

            if ($icone -match '^\s*"([^"]+\.exe)"') {
                $executavel = $Matches[1]
            } elseif ($icone -match '^\s*(.+?\.exe)(?:,\s*-?\d+)?\s*$') {
                $executavel = $Matches[1].Trim('"')
            }

            if ($executavel -and (Test-Path $executavel -PathType Leaf)) {
                Adicionar-App $nome "exe" $executavel "Registro do Windows"
            }
        }
    }
}

Write-Host "[4/4] Lendo executaveis do PATH..." -ForegroundColor Cyan

$pastasPath = $env:Path -split ";"

foreach ($pasta in $pastasPath) {
    $pasta = $pasta.Trim().Trim('"')

    if ($pasta -and (Test-Path $pasta -PathType Container)) {
        Get-ChildItem $pasta -Filter *.exe -File |
            ForEach-Object {
                Adicionar-App $_.BaseName "exe" $_.FullName "PATH"
            }
    }
}

$saida = "C:\Jarvis\dados"
New-Item -ItemType Directory -Path $saida -Force | Out-Null

$arquivo = Join-Path $saida "catalogo_aplicativos.json"

$dados = [PSCustomObject]@{
    generated_at = (Get-Date).ToString("o")
    computer = $env:COMPUTERNAME
    total = $catalogo.Count
    apps = @($catalogo.Values | Sort-Object name)
}

$dados | ConvertTo-Json -Depth 5 |
    Set-Content -Path $arquivo -Encoding UTF8

Write-Host "`n====================================" -ForegroundColor Green
Write-Host "CATALOGO GERADO COM SUCESSO!" -ForegroundColor Green
Write-Host "Total de entradas: $($catalogo.Count)"
Write-Host "Arquivo: $arquivo"
Write-Host "====================================" -ForegroundColor Green

Write-Host "`nALGUNS APLICATIVOS ENCONTRADOS:"
$catalogo.Values |
    Sort-Object name |
    Select-Object -First 25 name, type, source |
    Format-Table -AutoSize
