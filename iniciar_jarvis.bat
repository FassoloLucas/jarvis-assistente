@echo off
REM Sempre roda o J.A.R.V.I.S. pela venv do projeto (.venv), nunca pelo
REM Python global da máquina — evita o problema recorrente de rodar sem as
REM dependências opcionais instaladas ali (connectlife, resemblyzer/torch)
REM e a ferramenta correspondente falhar silenciosamente com um erro
REM genérico ("não consegui falar com o ar condicionado", etc).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Venv nao encontrada em .venv\Scripts\python.exe
    echo Crie ela primeiro com:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" javis.py
pause
