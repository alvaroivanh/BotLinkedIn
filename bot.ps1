# Lanzador del BotLinkedIn
# Uso: .\bot.ps1 <comando> [opciones]
# Ejemplos:
#   .\bot.ps1 --help
#   .\bot.ps1 resume parse "C:\ruta\a\micv.pdf"
#   .\bot.ps1 search run --keywords "python developer" --location "Madrid"
#   .\bot.ps1 dashboard start

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = $PSScriptRoot
Set-Location $repo
& "$repo\.venv\Scripts\python.exe" -m src.main @args
