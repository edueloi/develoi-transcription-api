@echo off
setlocal EnableDelayedExpansion

title Develoi Transcription API

echo.
echo  ========================================
echo   Develoi Local AI - Iniciando servicos
echo  ========================================
echo.

:: --- Verifica .env ---
if not exist ".env" (
    echo [SETUP] Criando .env a partir de .env.example...
    copy ".env.example" ".env" >nul
    echo [SETUP] .env criado. Edite o arquivo se necessario.
)

:: --- Verifica pasta tmp ---
if not exist "tmp" (
    mkdir tmp
)

:: --- Verifica Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+ e tente novamente.
    pause
    exit /b 1
)

:: --- Verifica/cria virtualenv ---
if not exist ".venv\Scripts\activate.bat" (
    echo [SETUP] Criando ambiente virtual Python...
    python -m venv .venv
)

:: --- Ativa virtualenv ---
call .venv\Scripts\activate.bat

:: --- Instala dependencias se necessario ---
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Instalando dependencias Python...
    pip install -r requirements.txt
    echo [SETUP] Dependencias instaladas.
)

:: --- Verifica Ollama ---
where ollama >nul 2>&1
if errorlevel 1 (
    echo.
    echo [AVISO] Ollama nao encontrado no PATH.
    echo         Baixe em: https://ollama.com/download
    echo         A API de transcricao funcionara, mas a IA estara offline.
    echo.
) else (
    :: Verifica se Ollama ja esta rodando
    curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
    if errorlevel 1 (
        echo [OLLAMA] Iniciando Ollama em background...
        start "" /B ollama serve
        :: Aguarda Ollama subir (max 15s)
        set /a tentativas=0
        :wait_ollama
        timeout /t 2 /nobreak >nul
        curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
        if errorlevel 1 (
            set /a tentativas+=1
            if !tentativas! LSS 7 goto wait_ollama
            echo [AVISO] Ollama demorou para responder. Continuando mesmo assim...
        ) else (
            echo [OLLAMA] Ollama esta online.
        )
    ) else (
        echo [OLLAMA] Ollama ja esta rodando.
    )

    :: Verifica se o modelo padrao existe
    for /f "delims=" %%i in ('type .env ^| findstr "OLLAMA_DEFAULT_MODEL"') do set ENV_LINE=%%i
    for /f "tokens=2 delims==" %%m in ("!ENV_LINE!") do set MODEL=%%m
    if "!MODEL!"=="" set MODEL=qwen2.5:7b

    ollama list 2>nul | findstr /i "!MODEL!" >nul 2>&1
    if errorlevel 1 (
        echo [OLLAMA] Baixando modelo !MODEL! (pode demorar na primeira vez)...
        ollama pull !MODEL!
    ) else (
        echo [OLLAMA] Modelo !MODEL! ja disponivel.
    )
)

:: --- Inicia a API ---
echo.
echo [API] Iniciando servidor FastAPI...
echo [API] Painel disponivel em: http://localhost:8000
echo [API] Docs disponivel em:   http://localhost:8000/docs
echo.
echo  Pressione Ctrl+C para parar o servidor.
echo  ========================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

endlocal
