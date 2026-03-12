# Runbook - FonteGest Condomínios

## Inicialização Rápida para Desenvolvimento

```bash
docker-compose up --build
```
Isso iniciará:
- **db**: PostgreSQL
- **api**: Backend FastAPI (porta 8000)
- **frontend**: Vite/Vue (porta 5173 para dev, ou Nginx na 80 no build)

## Como Rodar os Testes Backend

Os testes usam `pytest` e cobertura com `pytest-cov`.
```bash
cd backend
UV_PROJECT_ENVIRONMENT=.venv-local uv sync
UV_PROJECT_ENVIRONMENT=.venv-local PYTHONPATH=. uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

## Configurações e Logs (StructLog)
A aplicação grava logs em JSON no ambiente de produção para fácil raspagem por ferramentas de observabilidade (ex: ELK, Datadog), e renderiza logs formatados em ANSI no ambiente de desenvolvimento (`ENV="development"` configurado no `backend/app/core/config.py`).

## Migrações de Banco de Dados
A API gera suas tabelas via `Base.metadata.create_all` e realiza um Seed automático quando inicia. Caso necessite recriar o banco inteiro, você pode excluir o volume docker ou recriar os schemas.

## Monitoramento
Acesse `GET /api/health` para obter o status da conectividade do banco de dados (que agora retorna 503 em caso de indisponibilidade).
