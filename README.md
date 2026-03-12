# FonteGest

Sistema de gestão de abastecimento de água para condomínios. Permite que operadores registrem lançamentos de consumo por unidade, acompanhem cobranças, gerenciem estoque e sincronizem dados financeiros com o ERP Retaguarda (DataSnap).

## Visão Geral

- **Operadores** gerenciam um ou mais condomínios, lançam consumo mensal por unidade e acompanham status de cobrança.
- **FonteGest** submete lotes de cobrança ao ERP e sincroniza de volta o status de pagamento (pago/em aberto).
- **Retaguarda (ERP)** é responsável pela geração de boletos e confirmação de pagamentos — essa responsabilidade nunca pertence ao FonteGest.
- **Comissão** é calculada por condomínio em três modalidades: valor fixo, percentual sobre recebido, ou por unidade vendida (R$/galão, via tabela `CommissionRate`).

---

## Stack

| Camada     | Tecnologia                                              |
|------------|---------------------------------------------------------|
| Backend    | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic  |
| Banco      | PostgreSQL 16                                           |
| Frontend   | Vue 3 (Composition API), TypeScript, Vite, Tailwind 3  |
| Proxy      | Nginx 1.27                                             |
| Container  | Docker Compose                                          |
| CI/CD      | GitHub Actions + GHCR                                   |
| Deps (BE)  | uv                                                      |
| Deps (FE)  | npm                                                     |

---

## Estrutura de Pastas

```
FonteGest/
├── backend/                  # API FastAPI (Python)
│   ├── app/
│   │   ├── main.py           # Ponto de entrada da aplicação FastAPI
│   │   ├── api/              # Routers HTTP (um arquivo por domínio)
│   │   ├── core/
│   │   │   ├── config.py     # Settings via pydantic-settings (lê .env)
│   │   │   └── database.py   # Engine async, sessão e Base declarativa
│   │   ├── models/           # Modelos SQLAlchemy (tabelas do banco)
│   │   ├── schemas/          # Schemas Pydantic (request/response)
│   │   └── services/         # Lógica de negócio (comissão, ERP, etc.)
│   ├── alembic/              # Migrations do banco de dados
│   │   ├── env.py            # Configuração async do Alembic
│   │   └── versions/         # Arquivos de migration gerados
│   ├── tests/                # Testes automatizados (pytest)
│   ├── Dockerfile            # Imagem da API (python:3.12-slim + uv)
│   ├── entrypoint.sh         # Executa migrations e sobe o uvicorn
│   ├── pyproject.toml        # Dependências, ruff e pytest config
│   ├── uv.lock               # Lock file do uv (commitar sempre)
│   └── .env.example          # Variáveis de ambiente necessárias
│
├── frontend/                 # SPA Vue 3 + TypeScript
│   ├── src/
│   │   ├── main.ts           # Bootstrap da aplicação Vue
│   │   ├── App.vue           # Componente raiz
│   │   ├── components/       # Componentes reutilizáveis
│   │   ├── assets/           # Imagens e fontes estáticas
│   │   └── style.css         # Tailwind directives + design tokens CSS
│   ├── public/               # Arquivos servidos sem processamento
│   ├── vite.config.ts        # Proxy /api → backend, alias @/
│   ├── tailwind.config.js    # Tokens de design (cores, sombras, fontes)
│   ├── tsconfig.json         # Configuração TypeScript
│   ├── package.json          # Dependências e scripts npm
│   └── Dockerfile            # Apenas para build standalone (não usado no compose)
│
├── nginx/
│   ├── nginx.conf            # Serve SPA, proxy /api/, serve /media/evidencias/
│   └── Dockerfile            # Multi-stage: build Vue → nginx:1.27-alpine
│
├── infra/                    # Reservado para scripts de infraestrutura (Terraform, etc.)
│
├── docs/                     # Documentação do projeto
│   ├── SPRINTS.md            # Planejamento detalhado de todos os sprints
│   ├── descricao-projeto.md  # Descrição de negócio do sistema
│   ├── PoC.md                # Registro da prova de conceito
│   └── Especificação Técnica FonteGest Condomínios.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml            # Lint (ruff) + testes (pytest) + build frontend
│       └── deploy.yml        # Build e push das imagens Docker para GHCR
│
├── docker-compose.yml        # Orquestração: db + api + nginx (produção)
├── docker-compose.dev.yml    # Overrides de desenvolvimento (hot-reload)
└── .gitignore
```

---

## Como Rodar Localmente

### Pré-requisitos

- Docker e Docker Compose instalados
- (Opcional, para dev) Python 3.12 + uv, Node 20 + npm

### Produção (Docker Compose completo)

```bash
# Copie e preencha as variáveis de ambiente
cp backend/.env.example backend/.env

# Suba todos os serviços (banco, api, nginx) — faz build das imagens
docker compose up --build

# Acesse em: http://localhost:8080
```

O Nginx expõe a porta **8080**. O banco e a API ficam na rede interna e não são acessíveis diretamente pelo host.

### Desenvolvimento (hot-reload)

Modo recomendado para desenvolver: backend com `--reload` automático + frontend com HMR via Vite.

**Terminal 1 — Banco + API (hot-reload):**
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up db api
# API em: http://localhost:8000 (recarrega automaticamente ao salvar .py)
```

**Terminal 2 — Frontend (HMR):**
```bash
cd frontend && npm run dev
# SPA em: http://localhost:5173 (proxy /api → localhost:8000)
```

Alterações em `.py` são refletidas imediatamente sem restart. Alterações em `.vue`/`.ts` atualizam o browser instantaneamente.

**Parar os serviços:**
```bash
docker compose down        # para e remove containers (banco preservado)
docker compose down -v     # ⚠️ apaga também os volumes (banco PERDIDO)
```

### Backend sem Docker

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# API em: http://localhost:8000
```

---

## Testes e Quality Assurance

### Backend

```bash
cd backend

# Lint
uv run ruff check .
uv run ruff format --check .

# Testes com Cobertura
UV_PROJECT_ENVIRONMENT=.venv-local uv sync
UV_PROJECT_ENVIRONMENT=.venv-local PYTHONPATH=. uv run pytest tests/ -v --cov=app --cov-report=term-missing
```

### Frontend

Testes automatizados utilizando Vitest, Vue Test Utils e jsdom.

```bash
cd frontend
npm install
npm run test:unit
```

---

## CI/CD

| Workflow        | Trigger               | O que faz                                              |
|-----------------|-----------------------|--------------------------------------------------------|
| `ci.yml`        | Push em qualquer branch | Lint + testes do backend; build do frontend           |
| `deploy.yml`    | Push em `main`        | Build e push das imagens `api` e `nginx` para o GHCR  |

As imagens são publicadas no GitHub Container Registry (`ghcr.io`).

Secrets necessários no repositório (Settings > Secrets > Actions):

```
DATABASE_URL   SECRET_KEY   ERP_BASE_URL   ERP_MODE   ENV
SSH_HOST       SSH_USER     SSH_KEY
```

---

## Variáveis de Ambiente (Backend)

| Variável                    | Padrão                                              | Descrição                          |
|-----------------------------|-----------------------------------------------------|------------------------------------|
| `ENV`                       | `development`                                       | `development` ou `production`      |
| `SECRET_KEY`                | `change-me-in-production`                           | Chave para JWT                     |
| `DATABASE_URL`              | `postgresql+asyncpg://fontegest:fontegest@db:5432/fontegest` | URL do banco              |
| `ERP_MODE`                  | `mock`                                              | `mock` ou `datasnap`               |
| `ERP_BASE_URL`              | —                                                   | URL base da API Retaguarda         |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15`                                              | Expiração do access token          |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7`                                                 | Expiração do refresh token         |
