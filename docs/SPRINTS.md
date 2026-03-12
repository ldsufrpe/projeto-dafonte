# FonteGest Condomínios — Plano de Sprints

**Referência:** Especificação Técnica FonteGest Condomínios
**PoC aprovada:** `docs/index.html` (identidade visual e fluxo de lançamento validados pelo cliente)
**Metodologia:** Sprints de 2 semanas | Total estimado: 13 sprints (~26 semanas)
**Premissa de migração:** O sistema substitui gestão manual por planilhas. Todo condomínio tem histórico, estoque físico e inadimplência acumulada no momento do go-live. O plano prevê fluxo de implantação guiada para absorver esses dados sem perda de informação.
**Divisão de responsabilidades financeiras:**
- **FonteGest** — registra consumo por unidade/produto, envia o lote de fechamento à Retaguarda e sincroniza o resultado de pagamentos de volta.
- **Retaguarda (ERP)** — única responsável por gerar boletos, processar pagamentos e validar liquidações. FonteGest nunca cria boletos nem marca pagamentos manualmente — apenas lê o status que a Retaguarda confirma.

---

## Convenções

| Símbolo | Significado |
|---------|-------------|
| `[BE]` | Back-end (FastAPI / Python) |
| `[FE]` | Front-end (Vue 3 / TypeScript) |
| `[INF]` | Infraestrutura (Docker / CI/CD / Nginx) |
| `[INT]` | Integração com Retaguarda (ERP DataSnap) |
| `[IMP]` | Implantação / Migração de dados |

---

## Sprint 0 — Fundação e Estrutura do Monorepo

**Meta:** Repositório pronto para desenvolvimento paralelo FE/BE com CI/CD funcional.

### Tarefas

#### [INF] Estrutura de Diretórios
- Criar monorepo com pastas `frontend/`, `backend/`, `nginx/`, `infra/`
- Configurar `.gitignore` unificado para Python, Node, segredos
- Criar `docker-compose.yml` base com os serviços: `db`, `api`, `frontend`, `nginx`
- Definir rede Docker interna `fontegest_network`; PostgreSQL sem exposição de porta ao host

#### [INF] CI/CD — GitHub Actions
- Pipeline `ci.yml`: lint + testes a cada push/PR
- Pipeline `deploy.yml`: build e push das imagens para GHCR (GitHub Container Registry) ao mesclar em `main`
- Configurar variáveis de ambiente via GitHub Secrets: `DATABASE_URL`, `SECRET_KEY`, `ERP_BASE_URL`, `ERP_MODE` (default `mock`), `ENV` (default `development`)

#### [BE] Scaffold FastAPI
- Criar projeto com `uv` (ou `poetry`): dependências base (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `httpx`, `python-jose`, `passlib`)
- Estrutura de pastas: `app/api/`, `app/core/`, `app/models/`, `app/schemas/`, `app/services/`
- Arquivo `app/core/config.py` com `BaseSettings` lendo `.env`

#### [FE] Scaffold Vue 3
- Criar projeto com `npm create vite@latest` (template `vue-ts`)
- Instalar dependências: `tailwindcss`, `chart.js`, `vue-chartjs`, `vue-router@4`, `pinia`, `axios`
- Configurar `tailwind.config.ts` com paleta e fontes espelhando a PoC aprovada
- Configurar `vite.config.ts` com proxy `/api` apontando para `http://api:8000` (Nginx em prod, Vite dev proxy em dev)

#### [INF] Nginx
- Configurar `nginx.conf`: servir `dist/` do Vue, fazer `proxy_pass` de `/api` para `http://api:8000`
- Mapear volume `evidencias_data` em modo somente leitura para `/media/evidencias`

**Critérios de Aceite**
- `docker compose up` sobe todos os serviços sem erros
- Pipeline CI executa e valida linting
- `GET /api/health` retorna `{"status": "ok"}`

---

## Sprint 1 — Modelos de Dados e Migrations

**Meta:** Schema de banco de dados completo e versionado via Alembic, refletindo todos os domínios do sistema.

### Tarefas

#### [BE] Modelos SQLAlchemy (async)
- `User` — id, username **[unique]**, erp_user_code (nullable), full_name (nullable — `USU_NOMECOMPLETO`), email (nullable — `USU_EMAIL`, sempre null neste ERP), hashed_password (nullable — vazio até sync), role (`admin` | `operator`), is_active — **usuários são cadastrados no DataSnap (`VW_US_ATIVOS`) e sincronizados via `sync-users`; o campo `USU_ADMIN` do ERP define automaticamente o `role` (1=admin, 0=operator) — sem atribuição manual; o admin local de bootstrap é o único criado fora do sync**
- `Condominium` — id, name, address, erp_code **[unique]**, commission_type (`fixed` | `percent` | `per_unit`), commission_value (usado apenas para `fixed` e `percent`), go_live_date, onboarding_complete, created_at
- `CommissionRate` — id, FK(condominium), FK(product), value_per_unit (decimal), valid_from (date) — **único por `(condominium_id, product_id, valid_from)` [unique constraint]**; histórico de taxas por produto; ex: Galão 20L = R$0,50/unidade, Galão 10L = R$0,25/unidade
- `OperatorAssignment` — FK(user), FK(condominium) — **unique `(user_id, condominium_id)`** — tabela de associação multi-tenancy
- `Unit` — id, FK(condominium), unit_code (ex: `101`), is_active — **unique `(condominium_id, unit_code)`** — garantia de que a unidade 101 não existe duplicada no mesmo condomínio
- `Resident` — id, FK(unit), name, cpf_masked, phone, is_current, created_at, updated_at

**Catálogo de Produtos (modelo dinâmico — substitui colunas fixas `qty_20l`/`qty_10l`):**
- `Product` — id, name (ex: "Galão 20L INDAIÁ"), capacity_liters (int), erp_product_code (nullable), is_active, sort_order, created_at
- `ProductPrice` — id, FK(product), FK(condominium, nullable — null = preço global), valid_from (date), unit_price, source (`local` | `erp`) — **unique `(product_id, condominium_id, valid_from)`** — evita ambiguidade ao consultar "preço vigente no mês X"

> **Decisão confirmada:** produtos e preços vêm da **Retaguarda** e são sincronizados e cacheados localmente (ver Sprint 4). `ProductPrice.source='erp'` é sempre preenchido pelo sync — não há cadastro manual de preços. Existem **3 tamanhos de galão: 5L, 10L e 20L**; cada condomínio pode operar com um subconjunto desses produtos (ex: apenas 10L e 20L). O catálogo disponível por condomínio também é informado pela Retaguarda.

**Faturamento com linhas por produto:**
- `Billing` — id, FK(unit), FK(resident, **nullable** — unidades sem morador cadastrado devem poder ser lançadas), reference_month (YYYY-MM), status (`draft` | `pending_submission` | `submitted` | `open` | `paid` | `no_consumption`), days_overdue, erp_invoice_id (preenchido pela Retaguarda via submit/sync), resident_changed (bool), is_legacy (bool), total_amount (calculado), created_at, updated_at — **unique `(unit_id, reference_month)`** — impede double-billing para a mesma unidade no mesmo mês
- `BillingItem` — id, FK(billing), FK(product), FK(product_price, **nullable** — preserva histórico mesmo se o registro de preço for removido), quantity (int), unit_price_snapshot (decimal), line_total (calculado) — **uma linha por produto consumido**

> `unit_price_snapshot` é a fonte de verdade do preço no momento do lançamento; `FK(product_price)` é referência de auditoria e pode ser nula sem perda de informação financeira.

**Estoque por produto:**
- `StockEntry` — id, FK(condominium), FK(product), reference_month, quantity, entry_type (`purchase` | `initial`), notes, created_at

**Evidências e Onboarding:**
- `Evidence` — id, FK(billing), file_path, original_filename, uploaded_at
- `OnboardingImport` — id, FK(condominium), imported_at, source_filename, status (`pending` | `done` | `error`), row_count, error_log (JSON)
- `LegacyDebt` — id, FK(unit), reference_month, amount, description, imported_at

#### [BE] Migrations Alembic
- Configurar `alembic.ini` e `env.py` para modo async
- Gerar migration inicial com todos os modelos
- Garantir que o entrypoint Docker execute `alembic upgrade head` antes de `uvicorn`

**Critérios de Aceite**
- `alembic upgrade head` executa sem erros em container limpo
- Todos os modelos criados com constraints corretas (FK, unique, not-null)
- Rollback via `alembic downgrade -1` funciona

---

## Sprint 2 — Autenticação, RBAC e Back-office Administrativo

**Meta:** Sistema de identidade completo com JWT, controle de acesso por papel e painel admin funcional.

### Tarefas

#### [BE] Auth JWT
- `POST /api/auth/login` — recebe `{ username, password }` (não e-mail), valida credenciais contra hash local, retorna `access_token` (JWT 15min) + `refresh_token` (JWT 7d); `get_current_user` busca por `username` no JWT
- `POST /api/auth/refresh` — renova access_token via refresh_token válido
- `POST /api/auth/logout` — invalida refresh_token (blacklist em DB ou Redis)
- Dependência FastAPI `get_current_user` — decodifica JWT, levanta 401 se inválido
- Dependência `require_admin` — levanta 403 se role != admin
- Dependência `require_operator` — aceita admin e operator; filtra condomínios pelo JWT

#### [BE] Back-office SQLAdmin
- Usar **SQLAdmin** (escolha definitiva): integração nativa com SQLAlchemy 2.0 async, UI Tabler moderna, setup mínimo
- Implementar `AuthenticationBackend` customizado que valida via JWT do FastAPI (sem senha separada para o admin)
- Registrar views: `UserAdmin`, `CondominiumAdmin`, `OperatorAssignmentAdmin`, `ProductAdmin`, `ProductPriceAdmin` — produtos precisam ser gerenciáveis desde o início, antes da UI de Configurações do Sprint 8
- Proteger rota `/admin` com `require_admin`; SQLAdmin montado em `/admin` via `Admin(app, async_engine, authentication_backend=...)`

#### [FE] Página de Login
- Rota `/login` — formulário com campos **usuário** e senha (não e-mail), botão "Entrar"
- Visual: card centralizado com logo FonteGest (idêntico ao header da PoC), cores e sombras do design system
- Store Pinia `useAuthStore`: ações `login()`, `logout()`, `refreshToken()`; persiste token em `localStorage`
- Axios interceptor: injeta `Authorization: Bearer <token>` em todas as requisições; em 401, tenta refresh e retenta; em falha, redireciona para `/login`
- Navigation guard Vue Router: rotas protegidas redirecionam para `/login` se não autenticado

**Critérios de Aceite**
- Login com credenciais válidas retorna tokens e redireciona para dashboard
- Tentativa com credenciais inválidas exibe mensagem de erro
- Refresh automático funciona sem interrupção da sessão
- Acesso ao back-office bloqueado para role operator

---

## Sprint 3 — Design System e Shell do Frontend

**Meta:** Aplicação Vue com navegação completa, design system fiel à PoC aprovada e estrutura de módulos definida.

### Tarefas

#### [FE] Design System (Tailwind + CSS)
Replicar e componentizar todos os estilos da PoC aprovada:
- `NavTab.vue` — aba de navegação com estado ativo/inativo e ícone
- `StatCard.vue` — card KPI com borda lateral colorida, ícone, valor e subtítulo
- `Badge.vue` — pill colorido para status (Pago, Em Aberto, Pendente, Atrasado)
- `ProgBar.vue` — barra de progresso animada com cor configurável
- `TblInput.vue` — input de tabela com foco azul e estado desabilitado
- `QtyInput.vue` — input numérico pequeno centralizado para galões
- `BtnEdit.vue` — botão lápis / checkmark para edição inline
- Estilos globais: scrollbar customizado, animação `fade-up`, fonte `system-ui`

#### [FE] Layout Shell (`AppLayout.vue`)
- Header sticky: logo FonteGest (ícone gota + texto), pill do condomínio ativo, avatar do usuário
- Navegação por abas: Dashboard, Lançamento, Histórico, Configurações
- Tabs "Histórico" e "Configurações" habilitadas (não mais `opacity-50 cursor-not-allowed`)
- `<RouterView>` no `<main>` com `max-w-screen-xl mx-auto px-6 py-8`
- Seletor de condomínio no header para operadores com múltiplos vínculos

#### [FE] Stores Pinia
- `useAuthStore` — token JWT, role, refresh automático (criado no Sprint 2, referenciado aqui)
- `useCondominiumStore` — condomínio ativo, lista de condomínios do operador
- `useProductStore` — lista de produtos ativos do catálogo com preço vigente; alimenta colunas dinâmicas da tabela de lançamento e estoque
- `useBillingStore` — unidades, itens por produto, mês de referência, status de edição
- `useStockStore` — entradas por produto, saldo calculado por produto

#### [FE] Rotas Vue Router
```
/login
/home                          ← landing pós-login (Painel de Trabalho)
/dashboard                     ← Dashboard analítico do condomínio ativo
/lancamento
/historico
/estoque
/configuracoes
/implantacao/:condominiumId    ← admin only
```

#### [FE] Navigation Guards
- Após login: verificar `condominiums.length` do `useCondominiumStore`
  - `> 1` → redirecionar para `/home`
  - `== 1` → definir condomínio como ativo e redirecionar direto para `/dashboard`
- Rotas operacionais (`/dashboard`, `/lancamento`, etc.) exigem `activeCondominium` definido; caso contrário redirecionar para `/home`

#### [FE] Componente `CondominiumCard.vue`
Card de status mensal por condomínio — usado em `/home`:
- Nome e endereço do condomínio
- Badge de status do mês: `Pendente` (cinza) / `Em andamento` (âmbar) / `Enviado` (azul) / `Sincronizado` (verde)
- Barra de progresso: unidades lançadas / total de unidades
- Totalizadores: Total Faturado (submetido) e Total Recebido (ERP-confirmado)
- Comissão devida ao condomínio no mês (calculada conforme `commission_type`)
- Botão de ação contextual: "Lançar" / "Fechar mês" / "Sincronizar" / "Ver Dashboard"
- Ao clicar no card: `useCondominiumStore.setActive(id)` + navegação para `/dashboard`

**Critérios de Aceite**
- Navegação entre abas funciona sem reload
- Layout é visualmente idêntico à PoC aprovada em desktop e mobile
- Componentes do design system documentados com props tipadas (TypeScript)
- Navigation guard encaminha operador com 1 condomínio direto para `/dashboard` sem passar por `/home`

---

## Sprint 4 — Camada de Abstração ERP + Dados Locais (Mock)

**Meta:** Implementar a interface de contrato do ERP e um cliente mock completo com dados locais baseados na PoC aprovada. A conexão real com o DataSnap será feita em sprint dedicado posterior. O sistema deve funcionar 100% sem o ERP durante o desenvolvimento.

### Estratégia de Abstração

```
app/services/
  erp/
    base.py          ← Interface/protocolo abstrato (ERPClientBase)
    mock_client.py   ← Implementação local com dados fixos (desenvolvimento)
    datasnap_client.py ← Implementação real httpx (sprint futuro — não implementar agora)
    factory.py       ← Retorna MockERPClient ou DataSnapClient conforme ERP_MODE env
```

Variável de ambiente: `ERP_MODE=mock` (padrão) | `ERP_MODE=datasnap`

### Tarefas

#### [BE] Interface de Contrato (`erp/base.py`)
Definir classe abstrata (Protocol) com os métodos que ambos os clientes devem implementar.

**Schemas Pydantic (`erp/schemas.py`)** — contratos do ERP:
- `UserSyncSchema`: `username` (USU_LOGIN), `password` (USU_SENHA — cleartext), `full_name` (USU_NOMECOMPLETO, nullable), `email` (USU_EMAIL, nullable), `is_admin` (bool — USU_ADMIN "1"→True)
- `CondominiumSyncSchema`: `erp_code` (IDPESSOA), `name` (RAZAOSOCIAL), `address` (nullable), `prices: dict[str, str|None]` — ex: `{"INDAIA20LT": "13,80", "INDAIA10L": "6,60", "IAIA20L": "12,00"}`
- `ProductSchema`: `erp_product_code`, `name`, `capacity_liters`, `unit_price: Decimal`

**Métodos do protocolo:**
- `async get_users() -> list[UserSyncSchema]` — view `VW_US_ATIVOS`; role mapeado de `USU_ADMIN`
- `async get_condominiums() -> list[CondominiumSyncSchema]` — view `VW_PESSOA_PRECOS`; preços embutidos como colunas
- `async get_products(erp_code: str) -> list[ProductSchema]` — derivado das colunas de preço de `get_condominiums()`; retorna apenas produtos com preço > 0 para o condomínio
- `async get_residents(erp_code: str) -> list[ResidentSchema]` — view a descobrir em Sprint 4b
- `async get_payment_status(erp_code: str, reference_month: str) -> list[PaymentStatusSchema]`
- `async submit_billing(payload: BillingPayloadSchema) -> SubmitResultSchema`

**DataSnap — padrão de comunicação (documentado para Sprint 4b):**
- Endpoint único: `POST /datasnap/rest/TDMServerM/ExecuteSQLMobile`
- Payload: `{ "SQLQuery": "SELECT * FROM VW_..." }`
- Resposta: `{ "result": [[[dados]]] }` — **3 níveis de encapsulamento**
- Utilitário `unwrap_datasnap(decoded)`: tenta `result[0][0]` → `result[0]` → fallback
- Utilitário `normalize_decimal(value: str) -> Decimal`: `"9,5"` → `Decimal("9.5")`

#### [BE] Cliente Mock (`erp/mock_client.py`)
Implementar `MockERPClient` com dados baseados na PoC aprovada (EDF. 5 AVENIDA — Dezembro/2025). Os dados são carregados do arquivo `backend/app/services/erp/mock_data.json` (ver também `docs/mock-retaguarda.json` como referência do contrato esperado).

**Catálogo de produtos fixo** (derivado das colunas reais de VW_PESSOA_PRECOS):
- `INDAIA20LT` → Galão 20L INDAIÁ (capacity=20, sort_order=1)
- `INDAIA10L` → Galão 10L INDAIÁ (capacity=10, sort_order=2)
- `IAIA20L` → Galão 20L IAIÁ (capacity=20, sort_order=3)

- `get_users()` → 2 usuários mock com `full_name`, `email`, `is_admin` (sem galão 5L)
- `get_condominiums()` → EDF. 5 AVENIDA (`erp_code="{MOCK-5AV}"`, prices: INDAIA20LT + INDAIA10L) e EDF. SOLAR (`erp_code="{MOCK-SOL}"`, prices: INDAIA20LT + IAIA20L — sem INDAIA10L)
- `get_products(erp_code)` → derivado de `get_condominiums()`, filtra colunas com preço > 0
- `get_residents()` → lista com os 20 apartamentos da PoC (101 a 2001), incluindo nome, cpf_masked (vazio), is_current=true
- `get_payment_status()` → **simula a Retaguarda confirmando pagamentos** — retorna status por unidade conforme dados da PoC: `paid` (com `erp_invoice_id` mock), `open` (com `days_overdue` correspondentes) e `no_consumption`; é essa resposta que o sync-payments usa para atualizar `Billing.status` — a única forma de marcar um `Billing` como `paid`
- `submit_billing()` → simula resposta de sucesso da Retaguarda com `erp_invoice_id` gerado localmente (ex: `MOCK-{uuid4}`) e delay de 1s (`asyncio.sleep(1)`) para simular latência de rede; retorna `{ success: true, erp_invoice_id, submitted_count }` para cada unidade

#### [BE] Factory (`erp/factory.py`)
```python
def get_erp_client() -> ERPClientBase:
    if settings.ERP_MODE == "datasnap":
        raise NotImplementedError("DataSnap client será implementado em sprint futuro")
    return MockERPClient()
```
Injetar via dependência FastAPI: `erp: ERPClientBase = Depends(get_erp_client)`

#### [BE] Seed de Banco de Dados (`app/core/seed.py`)
Script executado automaticamente na inicialização quando `ENV=development`:
- **Produtos** — seed fixo com 3 produtos do catálogo real (não vêm do ERP por endpoint, são colunas fixas da view):
  - Galão 20L INDAIÁ (`erp_product_code="INDAIA20LT"`, capacity=20, sort_order=1)
  - Galão 10L INDAIÁ (`erp_product_code="INDAIA10L"`, capacity=10, sort_order=2)
  - Galão 20L IAIÁ (`erp_product_code="IAIA20L"`, capacity=20, sort_order=3)
- Cria admin local: `username="admin" / password="admin123"` com `role=admin` (somente em dev) — único usuário criado fora do fluxo de sync
- Carrega operadores via `MockERPClient.get_users()` e aplica a mesma lógica de upsert do `sync-users` — role mapeado de `is_admin`
- Carrega condomínios via `MockERPClient.get_condominiums()`; para cada condomínio, o `sync-condominiums` também cria `ProductPrice` a partir das colunas de preço
- Gera as 20 unidades (101–2001) com moradores conforme PoC
- Cria registros `Billing` + `BillingItem` referenciando os produtos acima

#### [BE] Endpoints ERP (usando factory)
- `POST /api/erp/sync-users` — chama `erp.get_users()`, upsert por `username`: novo → cria com `role` mapeado de `is_admin` + senha hasheada (bcrypt); existente → atualiza senha (bcrypt.verify), `full_name`, `email`, `role`; ausente do ERP → `is_active=False`; retorna `{ created, updated, deactivated }`
- `POST /api/erp/sync-condominiums` — chama `erp.get_condominiums()`, upsert em `Condominium` pelo `erp_code`; **também upsert `ProductPrice`** para cada coluna de preço > 0 (`valid_from=hoje`, `source='erp'`); novos condominiums: `onboarding_complete=False`
- ~~`POST /api/erp/sync-products/{condominium_id}`~~ — **removido**: preços agora são sincronizados pelo `sync-condominiums`
- `POST /api/erp/sync-residents/{condominium_id}` — chama `erp.get_residents()` e sincroniza `Unit` + `Resident` no banco
- `POST /api/erp/sync-payments/{condominium_id}/{reference_month}` — chama `erp.get_payment_status()` e atualiza `Billing`
- `POST /api/erp/submit-billing/{condominium_id}/{reference_month}` — consolida `Billing` do mês e chama `erp.submit_billing()`

#### [FE] Indicador de Modo Mock
- Quando `ERP_MODE=mock`, exibir pill âmbar discreto no header: `MODO LOCAL` em vez do indicador verde `Online`
- Ao clicar em "Sincronizar" no Dashboard, exibir toast informando que está em modo simulado

#### [BE] Scheduler de Sync Automático (APScheduler)
- Usar **APScheduler** com `CronTrigger` para sync automático de usuários e condomínios
- Configurável via env var `SYNC_CRON` (default produção: `0 */2 7-21 * *` — a cada 2h, das 07h às 21h)
- Fora da janela configurada: nenhuma execução (sem consumo de recursos na madrugada)
- Jobs: `sync_users_job()` e `sync_condominiums_job()` — reutilizam a mesma lógica dos endpoints manuais
- Scheduler iniciado no `lifespan` do FastAPI; em `ERP_MODE=mock` o scheduler roda mas usa o mock client
- **Fallback manual:** os endpoints `POST /api/erp/sync-users` e `POST /api/erp/sync-condominiums` permitem disparar sync manual quando o agendado falhar ou quando necessário

**Critérios de Aceite**
- `docker compose up` com `ERP_MODE=mock` sobe sistema totalmente funcional com dados da PoC no banco
- Trocar `ERP_MODE=datasnap` levanta `NotImplementedError` com mensagem clara (sem silenciar o erro)
- Todos os endpoints ERP funcionam via MockERPClient sem nenhuma conexão externa
- `submit_billing` mock retorna `erp_invoice_id` e persiste no banco normalmente
- Seed não executa em `ENV=production`
- Scheduler não executa jobs fora da janela definida em `SYNC_CRON`
- Endpoints manuais de sync funcionam independentemente do scheduler (fallback)

---

## Sprint 4b — Descoberta e Integração Real com Retaguarda (ERP DataSnap)

> **Pré-requisito obrigatório:** acesso ao ambiente de homologação da Retaguarda e disponibilidade do responsável técnico pelo ERP para sessão de mapeamento.
> Este sprint não tem data definida — será agendado quando o pré-requisito for atendido.

**Meta:** Mapear os contratos reais da Retaguarda, revisar `ERPClientBase` se necessário, e implementar `DataSnapClient` sem alterar nenhum endpoint ou lógica de negócio do FonteGest.

### Fase 1 — Descoberta (antes de escrever código)

Estas atividades devem ser concluídas e documentadas **antes** de qualquer implementação:

#### [INT] O que já sabemos (descoberto com arquivos PHP reais)

| Operação | Status | Detalhes |
|----------|--------|---------|
| **Protocolo** | ✅ Mapeado | Endpoint único `POST /datasnap/rest/TDMServerM/ExecuteSQLMobile`, payload `{"SQLQuery": "..."}`, resposta `{"result": [[[dados]]]}` — 3 níveis |
| **Decimais** | ✅ Mapeado | Vírgula como separador (`"9,5"`) — converter com `.replace(",", ".")` |
| **Usuários** | ✅ Mapeado | `SELECT * FROM VW_US_ATIVOS` — campos: USU_LOGIN, USU_SENHA (cleartext), USU_NOMECOMPLETO, USU_EMAIL, USU_ADMIN (0/1) |
| **Condomínios + Preços** | ✅ Mapeado | `SELECT * FROM VW_PESSOA_PRECOS` — campos: IDPESSOA (UUID), RAZAOSOCIAL, INDAIA20LT, INDAIA10L, IAIA20L (preços por condomínio) |
| **Catálogo de produtos** | ✅ Mapeado | 3 produtos fixos derivados das colunas: Galão 20L INDAIÁ, Galão 10L INDAIÁ, Galão 20L IAIÁ |
| **Webhooks** | ⏸ Adiado | Avaliar apenas após entrega — polling agendado + sync manual são suficientes |

#### [INT] O que ainda precisa ser descoberto

| Operação | O que descobrir |
|----------|----------------|
| **Moradores** | Nome da view/tabela; campos (unidade, nome, CPF?); como filtrar por IDPESSOA do condomínio |
| **Status de pagamento** | View ou stored proc; campos `status`, `days_overdue`, `erp_invoice_id`; como filtrar por mês e condomínio |
| **Envio de fechamento** | Existe endpoint para submissão? Payload esperado? Campo de retorno (ID do boleto)? Ou é só um registro local? |
| **Autenticação** | DataSnap exige Basic Auth, Bearer token ou nenhuma auth no header? (PHP atual não usa auth) |
| **Encoding** | UTF-8 ou Latin-1? (charset brasileiro pode ser problema em nomes com acento) |

#### [INT] Exploração com Postman/curl no ambiente de homologação
- Confirmar views de moradores e pagamento com exemplos de resposta reais
- Verificar encoding (UTF-8 vs Latin-1) em nomes com acentos
- Testar autenticação (ou ausência dela) na URL base
- Mapear os códigos de erro retornados pela Retaguarda

#### [INT] Documento de Contrato (`docs/erp-contract.md`)
Produzir documento com:
- URL base e método de autenticação
- Exemplo de request e response real para cada endpoint
- Mapeamento dos campos da Retaguarda → campos internos do FonteGest
- Comportamentos de borda descobertos (ex: morador sem CPF, unidade inativa)

**Só avançar para a Fase 2 após o documento de contrato estar revisado e aprovado.**

---

### Fase 2 — Implementação

#### [BE] Revisar `ERPClientBase` se necessário
- Ajustar assinaturas dos métodos e schemas Pydantic conforme contrato real descoberto
- Atualizar `MockERPClient` para refletir os mesmos nomes de campo do ERP real

#### [BE] Cliente Real (`erp/datasnap_client.py`)
- Implementar `DataSnapClient(ERPClientBase)` com `httpx.AsyncClient`
- Variáveis: `ERP_BASE_URL`, `ERP_USER`, `ERP_PASSWORD`, `ERP_TIMEOUT`
- Função `unwrap_datasnap(payload)` — implementar conforme formato real observado na Fase 1
- Em falha de conexão ou timeout, levantar `ERPConnectionError` (capturada globalmente → 503)
- Em resposta de erro da Retaguarda, levantar `ERPBusinessError` com mensagem do ERP

#### [BE] Atualizar Factory
```python
def get_erp_client() -> ERPClientBase:
    if settings.ERP_MODE == "datasnap":
        return DataSnapClient()
    return MockERPClient()
```

#### [BE] Testes de Contrato
- Rodar a mesma suite de testes dos endpoints ERP contra `DataSnapClient` em homologação
- Comparar respostas reais com as do mock — divergências indicam ajuste necessário no contrato

**Critérios de Aceite**
- Documento `docs/erp-contract.md` existe e está aprovado antes da implementação
- Com `ERP_MODE=datasnap`, todos os endpoints retornam dados reais sem alterar contratos do FonteGest
- Indicador do header muda de `MODO LOCAL` (âmbar) para `Online` (verde)
- `MockERPClient` permanece funcional e inalterado para uso em desenvolvimento local

---

## Sprint 5 — Módulo de Lançamento (Operacional)

**Meta:** Tela de lançamento totalmente funcional, conectada à API, replicando e aprimorando a PoC aprovada.

### Tarefas

#### [BE] API de Lançamentos

> **Fluxo de status do `Billing`:**
> `draft` → (operador preenche consumo) → `pending_submission` → (POST submit-billing) → `submitted` → (Retaguarda gera boleto) → `open` → (morador paga) → (sync-payments) → `paid`
> O FonteGest **nunca** transita diretamente para `paid` ou `open` — esses estados vêm exclusivamente do sync com a Retaguarda.
> O status `no_consumption` é derivado automaticamente quando `sum(BillingItem.quantity) == 0` e o mês é fechado.

- `GET /api/billing/{condominium_id}/{reference_month}` — retorna lista de unidades com morador atual, `BillingItem[]` por produto e status; cria `Billing` + `BillingItem` zerados para cada produto ativo se for mês novo
- `PATCH /api/billing/item/{billing_item_id}` — atualiza `quantity` de um `BillingItem`; recalcula `Billing.total_amount`; status retorna a `draft` se necessário
- `PATCH /api/billing/{billing_id}/resident` — atualiza `Resident` e sinaliza `resident_changed=True` no `Billing`
- `POST /api/billing/generate-mesh` — recebe `{condominium_id, unit_start, unit_end, reference_month}` e gera unidades em branco com `BillingItem` por produto ativo
- Lazy activation: edição de `Resident` (CPF/Nome/Tel) bloqueada na API se `sum(BillingItem.quantity) == 0`

> **Não existe endpoint para alterar status manualmente.** `paid`/`open` são escritos apenas pelo sync-payments (`GET /api/erp/sync-payments`). `no_consumption` é calculado ao fechar o mês.

#### [FE] View `LancamentoView.vue`
Replicar e conectar a tabela da PoC:
- Barra de controle: **label somente leitura** com nome do condomínio ativo (trocar de condomínio pelo dropdown do header), seletor de mês/referência, range de apartamento, preços exibidos por produto (vindos de `useProductStore`)
- Tabela principal: colunas fixas (Apto, CPF, Nome, Telefone) + **colunas dinâmicas** geradas por `useProductStore.activeProducts` em ordem `sort_order` + colunas fixas (Total, Status, Ações)
- Cabeçalho de cada coluna de produto exibe nome e preço unitário vigente
- Cabeçalho e rodapé com fundo `bg-slate-800` (fiel à PoC)
- Lazy activation: campos CPF/Nome/Tel bloqueados; desbloqueiam quando qualquer `BillingItem.quantity > 0`
- Chip `NOVO` em âmbar para moradores sem cadastro prévio
- Edição inline via ícone lápis / checkmark (componente `BtnEdit`)
- Coluna Status: **somente leitura** — exibe o valor atual do `Billing.status` com badge colorido; operador não altera status diretamente
  - `draft` → cinza "Em edição"; `pending_submission` → âmbar "Pronto p/ envio"; `submitted` → azul "Enviado ao ERP"; `open` → âmbar "Em Aberto"; `paid` → verde "Pago"; `no_consumption` → cinza "Sem Consumo"
- Linha verde para status `paid`; linha âmbar para `open`; linha cinza para `no_consumption`
- Rodapé da tabela com totais de galões e valor geral
- Barra de resumo inferior: Arrecadado (verde — vem do sync da Retaguarda), Em Aberto (âmbar), Total Faturado (cinza)
- Botão "Finalizar Faturamento" — exige que todos os lançamentos estejam completos, então dispara `POST /api/erp/submit-billing`; transita os `Billing` do mês para `submitted`; exibe banner "Lote enviado à Retaguarda — aguardando confirmação de pagamento"

**Critérios de Aceite**
- Lazy activation bloqueia/desbloqueia campos de morador corretamente com base na soma de BillingItems
- Colunas de produto são geradas dinamicamente; adicionar novo produto no catálogo aparece na tabela sem alterar código
- Alteração de quantidade recalcula total da linha e totais do rodapé em tempo real (computado Vue via `BillingItem`)
- Coluna Status é somente leitura — sem dropdown ou botão para alterar manualmente
- Após "Finalizar Faturamento": banner de confirmação exibido; status das unidades muda para `submitted` na UI sem reload; erro exibe mensagem descritiva
- `paid`/`open` só aparecem na tabela após sync com a Retaguarda (`GET /api/erp/sync-payments`)
- Tabela carrega dados reais da API

---

## Sprint 5b — Painel Gerencial (Admin Home)

**Meta:** Diferenciar a tela Home para administradores, oferecendo uma visão consolidada de todos os condomínios, indicadores totais e atalhos de gestão, enquanto operadores mantêm a visão focada nos condomínios atribuídos.

### Tarefas

#### [BE] API de Overview Gerencial
- O endpoint da Home já existe ou precisa ser criado? Teremos `GET /api/home/overview` (ou similar) que retorna o progresso do mês atual para cada condomínio.
- **Admin**: Retorna todos os condomínios + Totais Globais (Faturado, Arrecadado, Em Aberto, Comissão estimada).
- **Operador**: Retorna apenas os condomínios onde o usuário está em `OperatorAssignment`. Não retorna dados de comissão.

#### [FE] HomeView e Store
- Refatorar `HomeView.vue` usando layout dinâmico (`v-if="auth.isAdmin"`).
- **Visão Admin:**
  - Topo: 4 cards de Resumo Global.
  - Tabela centralizada: lista condomínios com colunas Nome, Progresso (lançadas/total unidades), Faturado, Recebido, Em Aberto, Comissão, Ações.
  - Clicar na linha ativa o condomínio e navega para o contexto.
- **Visão Operador (similar à atual):**
  - Grid de cards grandes.
  - Sem visibilidade de comissão.
- Integrar `condominiumStore` com a API real, removendo os mocks hardcoded atuais.

**Critérios de Aceite**
- Ao logar como Admin, a tela Home exibe painel gerencial agregado em tabela.
- Ao logar como Operador, a Home exibe cards simples.
- Valores na Home vêm do banco via API real `GET /api/home/overview`.

---

## Sprint 5c — Implantação e Migração de Dados (Go-Live)

**Meta:** Permitir que qualquer condomínio novo ingresse no sistema trazendo sua realidade atual: moradores cadastrados, estoque físico existente, inadimplência acumulada e histórico de meses anteriores — tudo oriundo de planilhas Excel/CSV usadas antes do FonteGest.

### Análise da Planilha Real (`ESPELHO 5 AVENIDA.xlsx`)

A planilha de origem foi analisada e revela a estrutura e convenções que o sistema de importação deve respeitar:

**Aba `ESPELHO` (lançamento mensal):**
| Coluna real na planilha | Campo no sistema | Observação |
|------------------------|-----------------|-----------|
| `CLIENTE` | `Resident.name` | Frequentemente em branco para novas unidades |
| `CPF` | `Resident.cpf_masked` | **Sempre em branco na planilha** — campo nunca foi preenchido no fluxo manual |
| `UNIDADE` | `Unit.unit_code` | Único campo obrigatório e sempre preenchido |
| Colunas de quantidade por produto | `BillingItem.quantity` | **N colunas variáveis** — uma por produto cadastrado no catálogo. O importador mapeia pelo nome da coluna ao produto correspondente no banco |
| `TOTAL GERAL` | `Billing.total_amount` | Calculado; não precisa ser importado |

> **Telefone não existe na planilha** — nunca foi registrado nesse fluxo. É campo opcional no sistema.

> **"FECHAR ESTOQUE ANTES"** aparece no cabeçalho da planilha como instrução ao operador. Isso confirma que o fechamento de estoque é um **pré-requisito operacional** para o faturamento — o sistema deve reforçar essa ordem.

**Aba `ASSINATURA`:** Lista de unidades com campo para assinatura de recebimento — folha impressa entregue ao condomínio. Relacionada diretamente ao módulo de Evidências (a assinatura digitalizada/fotografada é a prova de entrega).

**Aba `planilha1`** (histórico): Dados de mai/2021 com preços diferentes (20L=R$10,80; 10L=R$5,00; Crystal=R$6,50). Confirma que o histórico pode ter **múltiplos anos com tabelas de preço variáveis** — a importação deve armazenar o preço unitário praticado em cada mês, não apenas a quantidade.

### Contexto

Ao ativar um novo condomínio, o operador enfrenta os seguintes cenários que o sistema precisa absorver:

| Cenário | Impacto sem onboarding |
|---------|----------------------|
| Moradores já conhecidos (não vêm do DataSnap ainda) | Teria que recadastrar um a um na tela de lançamento |
| CPF em branco na planilha | Importação não pode exigir CPF como campo obrigatório |
| Estoque físico existente | Saldo inicial zerado → alertas antifraude falsos desde o dia 1 |
| Inadimplência acumulada de meses anteriores | Sumia do sistema; operador não teria visão do débito real |
| Histórico com preços diferentes por mês | Import deve preservar preço praticado, não recalcular com preço atual |
| Mês em andamento ao migrar | Consumo parcial já lançado na planilha precisaria entrar no sistema |

### Tarefas

#### [IMP] Wizard de Implantação — Backend

**`POST /api/condominiums/{id}/onboarding/import-residents`**
- Aceita arquivo CSV ou XLSX (`multipart/form-data`)
- Colunas esperadas (tolerante a variações de nome): `unidade`, `cpf`, `nome`, `telefone`
- Cria `Unit` + `Resident` para cada linha válida; linhas com erro são registradas no `OnboardingImport.error_log`
- Não duplica unidades já existentes (upsert por `unit_code`)
- Retorna: total importado, total com erro, lista de erros por linha

**`POST /api/condominiums/{id}/onboarding/stock-opening`**
- Recebe `{ reference_month, items: [{ product_id, quantity }], notes }` — uma entrada por produto do catálogo
- Cria um `StockEntry` com `entry_type='initial'` por produto informado
- Só permite um registro de saldo inicial por produto por mês
- Bloqueia criação se já existirem `StockEntry` do tipo `purchase` para o mesmo produto no mesmo mês

**`POST /api/condominiums/{id}/onboarding/legacy-debts`**
- Aceita CSV/XLSX com colunas: `unidade`, `mes_referencia` (YYYY-MM), `valor`, `descricao`
- Cria registros `LegacyDebt` vinculados à unidade
- Esses registros aparecem no Dashboard como "Débitos Anteriores" com badge visual distinto (`legacy`)

**`POST /api/condominiums/{id}/onboarding/import-history`**
- Aceita CSV/XLSX com histórico de meses anteriores: `unidade`, `mes_referencia`, `produto` (nome), `quantidade`, `preco_unitario`, `status_pgto`
- Formato linha-por-produto: uma linha por `BillingItem`; o campo `produto` é cruzado por nome com o catálogo ativo do condomínio
- Produto não encontrado no catálogo → linha registrada como erro no `OnboardingImport.error_log` (não aborta o lote)
- Cria registros `Billing` + `BillingItem` com `is_legacy=true` — somente leitura, não editáveis pelo fluxo de lançamento
- Permite que o histórico apareça na aba Histórico e alimente gráficos do Dashboard

**`POST /api/condominiums/{id}/onboarding/complete`**
- Marca `Condominium.onboarding_complete = true` e define `go_live_date`
- A partir desse ponto, o fluxo normal de lançamento assume

#### [IMP] Wizard de Implantação — Frontend

**View `ImplantacaoView.vue`** (acessível pelo admin via `/implantacao/{condominium_id}`)

Wizard em 5 etapas com indicador de progresso no topo:

**Etapa 1 — Informações do Condomínio**
- Confirmar nome, endereço, `erp_code`, preço dos galões, tipo de comissionamento
- Definir mês de go-live (`go_live_date`)

**Etapa 2 — Importar Moradores**
- Upload de planilha CSV/Excel com drag-and-drop
- Preview das primeiras linhas antes de confirmar importação
- Tabela de resultado: linhas importadas (verde), linhas com erro (vermelho) com motivo
- Botão "Baixar modelo CSV" com o formato esperado
- Possibilidade de pular (se moradores vierem do DataSnap futuramente)

**Etapa 3 — Saldo Inicial de Estoque**
- Requer que o catálogo de produtos esteja cadastrado (bloqueia etapa se `Product` count == 0 com instrução para cadastrar em Configurações primeiro)
- Formulário dinâmico: mês de referência + uma linha por produto ativo com campo de quantidade
- Instrução visual: "Informe o estoque físico contado no momento da implantação"
- Possibilidade de pular se o estoque começar do zero

**Etapa 4 — Inadimplência Anterior (Débitos Herdados)**
- Upload de planilha com débitos de meses anteriores ao go-live
- Tabela de preview com totais por unidade
- Badge de aviso: "Estes valores serão exibidos no Dashboard mas não gerarão novos boletos pelo sistema"
- Possibilidade de pular

**Etapa 5 — Histórico de Meses Anteriores (Opcional)**
- Upload de planilha com lançamentos de meses já fechados
- Aviso: "Dados históricos são somente leitura e servem apenas para consulta e relatórios"
- Possibilidade de pular

**Tela de Conclusão**
- Resumo do que foi importado em cada etapa
- Botão "Ativar Condomínio" que chama `POST /onboarding/complete`
- Redireciona para o Dashboard com o condomínio já ativo

#### [FE] Integração no fluxo normal
- Dashboard: seção "Débitos Anteriores ao Sistema" com total de `LegacyDebt` por condomínio, badge `LEGADO` em âmbar
- Histórico: meses com `is_legacy=true` exibem ícone de planilha e tooltip "Importado de planilha"
- Estoque: saldo inicial (`entry_type='initial'`) exibido com linha destacada e label "Saldo de Abertura"
- Header: enquanto `onboarding_complete=false`, exibir banner amarelo no topo "Implantação em andamento — complete o wizard para ativar o condomínio"

#### [IMP] Template de planilhas para download
Criar templates CSV com colunas alinhadas à planilha real do cliente:

`template_moradores.csv`:
```
unidade,nome,cpf,telefone
101,Nome do Morador,,
201,,,
```
> CPF e telefone são opcionais — planilha original não os contém.

`template_historico.csv`:
```
unidade,mes_referencia,produto,quantidade,preco_unitario,status_pgto
101,2025-11,Galão 20L,6,13.80,pago
101,2025-11,Galão 10L,2,6.60,pago
```
> Formato linha-por-produto: cada linha representa um `BillingItem`. O campo `produto` é cruzado pelo nome com o catálogo cadastrado no sistema. O preço unitário é preservado por linha pois varia entre meses e entre marcas.

`template_debitos_anteriores.csv`:
```
unidade,mes_referencia,valor,descricao
501,2025-10,27.60,Referente a outubro/2025
```

**Critérios de Aceite**
- Importação de planilha com 100 linhas processa sem timeout; erros por linha são identificados sem abortar o lote
- Saldo inicial de estoque elimina alertas antifraude falsos no primeiro mês
- `LegacyDebt` aparece no Dashboard mas não interfere no fluxo de `Billing`
- Wizard pode ser retomado (etapas já concluídas ficam marcadas; dados já importados não são duplicados)
- Operador sem role admin não acessa `/implantacao`

---

## Sprint 6 — Painel de Trabalho, Dashboard e KPIs

**Meta:** Tela `/home` com visão consolidada de todos os condomínios do usuário + Dashboard analítico por condomínio conectado à API.

### Tarefas

#### [BE] API do Painel de Trabalho (`/home`)
- `GET /api/home/overview/{reference_month}` — retorna lista de todos os condomínios acessíveis ao usuário logado (filtrado por `OperatorAssignment`; admin vê todos), cada um com:
  - `condominium_id`, `name`, `address`
  - `month_status`: `not_started` | `in_progress` | `submitted` | `synced`
    - `not_started` → nenhum `Billing` criado para o mês
    - `in_progress` → existem `Billing` em `draft`
    - `submitted` → todos `submitted` (nenhum em `draft`)
    - `synced` → todos em `paid`/`open`/`no_consumption` (ERP confirmou)
  - `units_launched` / `total_units` — progresso do lançamento
  - `total_billed` — soma dos `Billing.total_amount` com `status != 'draft'`
  - `total_received` — soma onde `status='paid'` (ERP-confirmado)
  - `commission_due` — comissão calculada conforme `commission_type` do condomínio (ver Sprint 8)
  - `has_stock_alert` — `true` se qualquer produto tiver `saldo_atual < 0` no mês
- Para admin: inclui campo `operator_name` em cada card

#### [BE] API de Dashboard

> **Fonte dos dados financeiros:** `total_collected` e `qty_paid` refletem exclusivamente o que a Retaguarda confirmou via `sync-payments`. O Dashboard não calcula pagamentos internamente — lê o estado atual de `Billing.status` que foi escrito pelo sync.

- `GET /api/dashboard/{condominium_id}/{reference_month}` — retorna objeto consolidado:
  - `total_collected` — soma de `Billing.total_amount` onde `status='paid'` (confirmado pela Retaguarda)
  - `total_open` — soma onde `status='open'` ou `status='submitted'`
  - `total_billed` — soma de todos os `Billing` com `status != 'draft'`
  - `qty_paid`, `qty_open`, `qty_submitted`, `qty_billed`
  - `default_rate` (%) — `(qty_open / qty_billed) * 100` considerando apenas `open` (boleto vencido e não pago)
  - `top5` — 5 unidades com maior valor no mês
  - `defaulters` — lista de inadimplentes com nome, consumo, valor, `days_overdue` (vindo da Retaguarda via sync)
- `POST /api/erp/sync-payments/{condominium_id}/{reference_month}` — (já definido no Sprint 4) — chama `erp.get_payment_status()` e atualiza `Billing.status`, `days_overdue`, `erp_invoice_id` em lote; invalidar cache do Dashboard após execução

#### [FE] View `HomeView.vue` — Painel de Trabalho
Tela de entrada pós-login para operadores com múltiplos condomínios:
- Seletor de mês de referência no topo (padrão: mês atual; permite ver mês anterior para fechamentos atrasados)
- **Bloco de KPIs consolidados** (soma de todos os condomínios do operador no mês selecionado):
  - Total Faturado (submetido) — cinza
  - Total Recebido (ERP-confirmado) — verde
  - Taxa de inadimplência geral (%) — âmbar/vermelho
  - Total de comissão devida aos condomínios — azul
  - Comparativo com mês anterior: seta ↑ verde / ↓ vermelho nos totalizadores
- **Grid de cards** `CondominiumCard.vue` — um por condomínio, ordenados por: alertas críticos primeiro (estoque negativo), depois por status (pendente → em andamento → enviado → sincronizado)
- Badge de alerta de estoque no card quando `has_stock_alert=true`: ícone de aviso vermelho
- Admin vê nome do operador responsável em cada card + filtro por operador no topo

#### [FE] View `DashboardView.vue` — Dashboard Analítico por Condomínio
Conectar e manter o visual exato da PoC:
- 4 cards KPI: Total Arrecadado (verde, da Retaguarda), Inadimplência (%), Total em Aberto (âmbar), Consumo do Mês
- Aviso visual quando `qty_submitted > 0`: pill âmbar "N unidades aguardando confirmação da Retaguarda"
- Gráfico Donut (Chart.js): Pagos vs Em Aberto — inicialização/destruição correta ao trocar de aba
- Ranking Top 5: medal badge por posição (ouro/prata/bronze), barra de progresso relativa, nome + consumo
- Tabela Inadimplentes: unidade, morador, consumo, valor, vencimento, badge de status (Atrasado N dias / Pendente), botão "Acionar"
- Botão "Exportar PDF" com ação funcional
- Botão "Sincronizar" chama `POST /api/erp/sync-payments` — atualiza `paid`/`open` vindos da Retaguarda; em modo mock exibe toast "Sincronização simulada — Retaguarda não conectada"

**Critérios de Aceite**
- `/home` exibe todos os condomínios do operador com status correto do mês selecionado
- KPIs consolidados somam corretamente os dados de todos os condomínios
- Trocar mês no seletor do `/home` recarrega todos os cards e KPIs
- Clicar em card define condomínio ativo e navega para `/dashboard`
- Admin vê todos os condomínios com nome do operador responsável
- Dashboard analítico exibe dados corretos após sincronização com a Retaguarda (ou mock)
- `total_collected` só aumenta após sync — nunca ao editar um lançamento
- Donut chart re-renderiza sem duplicação ao navegar entre abas
- Inadimplência % bate com a conta: `(qty_open / qty_billed) * 100`
- Pill "aguardando confirmação" aparece quando há unidades `submitted` e desaparece após sync retornar `paid`/`open`

---

## Sprint 7 — Módulo de Controle de Estoque

**Meta:** Motor de auditoria de estoque com alerta antifraude visual e rastreamento por mês/condomínio.

### Tarefas

#### [BE] API de Estoque
- `GET /api/stock/{condominium_id}/{reference_month}` — retorna por produto: `{ product_id, product_name, saldo_anterior, entradas, consumo_lancado, saldo_atual, is_negative }` onde `saldo_atual = saldo_anterior + entradas - consumo_lancado`
- `POST /api/stock/entries` — registra entrada: `{ condominium_id, reference_month, product_id, quantity, entry_type, notes }`
- `PUT /api/stock/entries/{entry_id}` — edita entrada
- `DELETE /api/stock/entries/{entry_id}` — remove entrada
- Lógica de saldo por produto: `saldo_anterior + entradas - consumo_lancado`; retorna `is_negative: true` quando resultado < 0

#### [FE] View `EstoqueView.vue`
- Cards de saldo por produto (dinâmicos): Saldo Anterior + Entradas - Consumo = Saldo Atual
- Alerta antifraude **por produto**: quando `is_negative=true` para qualquer produto, exibir faixa vermelha piscante com "Divergência de Estoque — [Produto] — Verifique desvios"
- Tabela de entradas do mês: data, produto, tipo, quantidade, observação, ações (editar/excluir)
- Botão "+ Registrar Abastecimento" abre modal com seletor de produto (dropdown dos produtos ativos) + quantidade
- Histórico de saldo por produto e por mês em gráfico de linha (Chart.js) — uma linha por produto

**Critérios de Aceite**
- Alerta vermelho aparece quando `saldo_atual < 0`
- Novo abastecimento recalcula saldo imediatamente
- Saldo anterior do mês M = saldo final do mês M-1

---

## Sprint 8 — Módulo Financeiro e Comissionamento

**Meta:** Dashboard financeiro com KPIs de eficiência de cobrança e cálculo automático de comissão por condomínio.

### Tarefas

#### [BE] Motor de Comissionamento

> **Fonte dos valores financeiros:** `total_received` (base do percentual) usa exclusivamente a soma de `Billing.total_amount` onde `status='paid'` — status escrito pela Retaguarda via sync-payments. O FonteGest não gerencia pagamentos; apenas lê o estado confirmado pelo ERP.

- Endpoint `GET /api/finance/commission/{condominium_id}/{reference_month}` — calcula comissão conforme `commission_type` do condomínio:
  - `fixed`: retorna `commission_value` fixo mensal, independente de volume ou recebimento
  - `percent`: retorna `(total_received * commission_value / 100)` — `total_received` = soma dos `Billing.total_amount` com `status='paid'` no mês (ERP-confirmado)
  - `per_unit`: retorna `SUM(BillingItem.quantity × CommissionRate.value_per_unit)` — soma por produto do mês, usando a `CommissionRate` vigente em `reference_month` (`valid_from <= reference_month`, pega a mais recente); independe de pagamento (comissão gerada no lançamento, não na cobrança)
- Endpoint `GET /api/finance/operator-performance/{reference_month}` — lista todos os condomínios do operador com: total faturado (submetido), total recebido (ERP-confirmado), taxa de sucesso (%), comissão devida (calculada pelo motor acima)
- Endpoint `PUT /api/condominiums/{id}/commission-config` — atualiza `commission_type` e `commission_value` (admin only)
- Endpoint `POST /api/condominiums/{id}/commission-rates` — cria nova `CommissionRate` para um produto com `valid_from` (admin only); usado quando `commission_type='per_unit'`
- Endpoint `GET /api/condominiums/{id}/commission-rates` — lista taxas por produto com histórico

#### [FE] View `FinanceiroView.vue` (dentro do Dashboard ou aba separada)

> Os dados financeiros são **somente leitura** — derivados do estado de pagamento confirmado pela Retaguarda. Nenhum campo é editável nesta tela.

- KPI de eficiência: Total Faturado (submetido) vs Total Recebido (confirmado pela Retaguarda) com percentual de sucesso
- Aviso quando há valores `submitted` ainda não confirmados: "R$ X,XX aguardando confirmação da Retaguarda — sincronize para atualizar"
- Card de comissão: valor configurado, tipo (fixo/percentual), valor calculado sobre o recebimento confirmado do mês
- Tabela de performance por operador (visão admin): condomínio, faturado, recebido (ERP-confirmado), taxa, comissão
- Gráfico de barras (Chart.js): comparativo de arrecadação (recebido ERP) vs inadimplência por mês (últimos 6 meses)

#### [BE] API de Produtos e Preços
- `GET /api/products` — lista produtos ativos com preço atual por condomínio
- `POST /api/products` — cria produto (admin only): nome, capacidade em litros, código ERP (opcional), ordem de exibição
- `PUT /api/products/{id}` — atualiza produto; `is_active=false` desativa sem excluir (preserva histórico)
- `POST /api/products/{id}/prices` — registra nova tabela de preço com data de vigência (`valid_from`)
- `GET /api/products/{id}/prices` — histórico de preços do produto

#### [FE] View `ConfiguracoesView.vue`
- **Seção Produtos** (admin only):
  - Tabela de produtos ativos: nome, capacidade, preço vigente, código ERP, status
  - Botão "+ Novo Produto" abre modal: nome, capacidade (litros), código ERP opcional, ordem na tabela de lançamento
  - Botão "Novo Preço" por produto: valor unitário + data de vigência
  - Histórico de preços expansível por produto
  - Toggle para ativar/desativar produto (desativado some da tela de lançamento mas preserva histórico)
- **Seção de Comissionamento** (admin only):
  - Seletor de tipo: `Fixo Mensal` | `Percentual sobre recebido` | `Por unidade vendida`
  - Para `Fixo`: campo valor mensal (R$)
  - Para `Percentual`: campo alíquota (%)
  - Para `Por unidade`: tabela de taxas por produto ativo — coluna produto, coluna R$/unidade, coluna vigência; botão "Novo Período" cria nova `CommissionRate` com `valid_from`; histórico expansível por produto
  - Exibe prévia do cálculo do mês atual baseado nas taxas configuradas
- Seção de perfil: alterar senha do operador logado

> A tela de lançamento (Sprint 5) gera colunas dinamicamente com base nos produtos ativos, na ordem `sort_order`. Não há colunas hardcoded.
> **Dependência de ordem:** o catálogo de produtos deve ser cadastrado via SQLAdmin (Sprint 2) ou via UI de Configurações (este sprint) **antes** de qualquer go-live de condomínio (Sprint 5b). O wizard de implantação bloqueia a etapa de estoque se não houver produtos cadastrados.

**Critérios de Aceite**
- `per_unit`: comissão = `SUM(qty × rate_per_unit)` usando taxa vigente; não depende de pagamento ERP
- `percent`: comissão calculada sobre `total_received` (ERP-confirmado), retorna 0 sem sync
- `fixed`: comissão retorna valor fixo independente de qualquer outra variável
- Admin cadastra taxas `per_unit` por produto com histórico de vigência; operador recebe 403
- Trocar `commission_type` de `per_unit` para `fixed`/`percent` preserva o histórico de `CommissionRate` (não exclui)
- Gráfico histórico renderiza corretamente com dados de meses anteriores
- Tela Financeiro não tem nenhum campo editável de pagamento

---

## Sprint 9 — Módulo de Evidências (Upload e Armazenamento)

**Meta:** Sistema de upload de imagens como prova de entrega, com compressão automática e servimento estático via Nginx.

### Tarefas

#### [BE] Pipeline de Upload
- `POST /api/condominiums/{id}/evidencias` — aceita `multipart/form-data` com campo `file` e `billing_id`
- Validação de tipo MIME (aceitar apenas `image/*`); rejeitar outros formatos com 422
- Delegar processamento a `BackgroundTask`:
  - Usar Pillow para redimensionar (max-width 1280px, mantendo aspect ratio)
  - Converter para WebP
  - Salvar em `/evidencias/{ano}/{mes}/{condominium_id}/{uuid}.webp`
  - Persistir registro em `Evidence` com `file_path` relativo
- `GET /api/condominiums/{id}/evidencias/{billing_id}` — retorna lista de evidências com URLs

#### [INF] Nginx Static Serving
- Mapear volume `evidencias_data:/evidencias:ro` no contêiner Nginx
- Configurar `location /media/evidencias/` para servir arquivos estáticos diretamente

#### [FE] Componente `EvidenceUpload.vue`
- Botão de upload por linha da tabela de lançamento (ícone câmera)
- Preview da imagem após upload
- Indicador de progresso durante envio
- Exibição das evidências já enviadas em miniatura clicável (lightbox simples)

> **Contexto da planilha real:** A aba `ASSINATURA` do `ESPELHO 5 AVENIDA.xlsx` é uma folha impressa com lista de unidades para assinatura de recebimento. A foto dessa folha assinada é a principal evidência de entrega. O botão de câmera na tabela de lançamento deve ser o ponto de captura desta evidência, tornando o fluxo digital o que hoje é feito em papel.

**Critérios de Aceite**
- Upload de JPEG/PNG resulta em arquivo WebP no volume com max 1280px
- Arquivo com extensão não-imagem retorna 422 com mensagem clara
- Nginx serve o arquivo WebP diretamente sem passar pela API Python
- Tamanho do arquivo reduz > 50% para imagens típicas de campo

---

## Sprint 10 — Histórico de Lançamentos

**Meta:** Aba Histórico completamente funcional com consulta, filtros e reabertura controlada de meses anteriores.

### Tarefas

#### [BE] API de Histórico
- `GET /api/billing/history/{condominium_id}` — lista meses fechados com: mês, total faturado, total recebido, total galões, status (`fechado` | `em_aberto`)
- `GET /api/billing/history/{condominium_id}/{reference_month}` — detalhe completo do mês: todas as unidades, status individual, evidências
- `POST /api/billing/reopen/{condominium_id}/{reference_month}` — reabre mês para correção (admin only); registra log de auditoria

#### [FE] View `HistoricoView.vue`
- Tabela de meses com colunas: Referência, Total Faturado, Arrecadado, Total Unidades (qty por produto agregado no tooltip), Status, Ações
- Clique em mês abre modal/drawer com detalhe das unidades naquele mês
- Botão "Reabrir Mês" visível apenas para admin, com confirmação modal
- Filtro por período (intervalo de meses) e busca por unidade
- Export CSV do histórico selecionado

**Critérios de Aceite**
- Histórico lista apenas meses do condomínio ativo
- Reabertura exige role admin e registra auditoria
- Export CSV gera arquivo correto com todos os campos do mês

---

## Sprint 11 — Testes, Segurança, Polimento e Deploy

**Meta:** Sistema production-ready com cobertura de testes, revisão de segurança e documentação de operação.

### Tarefas

#### [BE] Testes
- Testes unitários (pytest + pytest-asyncio): services de comissionamento, lógica de estoque, `unwrap_datasnap`
- Testes de integração: endpoints críticos (`/login`, `/billing`, `/erp/submit-billing`) com banco em memória (SQLite async) ou PostgreSQL de teste
- Cobertura mínima: 70% no core de negócio

#### [FE] Testes
- Testes de componentes com Vitest + `@vue/test-utils`: `StatCard`, `Badge`, cálculo de total em `LancamentoView`
- Teste de store Pinia: `useBillingStore` cálculo de totais

#### [INF] Segurança
- Revisar headers HTTP no Nginx: `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`
- Rate limiting no Nginx para `/api/auth/login`
- Garantir que `.env` nunca seja commitado (verificar `.gitignore`)
- Revisar todos os endpoints: operadores não acessam dados de condomínios fora do seu vínculo

#### [INF] Polimento e Observabilidade
- Structured logging no FastAPI (`structlog` ou `loguru`) com nível configurável via env
- Endpoint `GET /api/health` com checagem de conectividade ao banco e ao ERP
- Tratamento global de exceções: retornar RFC 7807 (`application/problem+json`) para todos os erros

#### [FE] Polimento
- Skeleton loaders durante carregamento de dados (substituir tela em branco)
- Empty states descritivos em tabelas vazias
- Toast notifications (sucesso, erro, aviso) centralizados via composable `useToast`
- Responsividade validada em mobile (375px) e tablet (768px)

#### [INF] Documentação de Deploy
- `README.md` atualizado com: requisitos, variáveis de ambiente, comandos de deploy
- `docs/RUNBOOK.md`: procedimentos operacionais (backup DB, rotação de secrets, reabrir mês)

**Critérios de Aceite**
- Pipeline CI passa com todos os testes
- `docker compose up` em servidor limpo sobe sistema funcional após `alembic upgrade head`
- Nenhuma rota vaza dados de condomínios cruzados entre operadores

---

## Resumo de Épicos por Sprint

| Sprint | Épico Principal | Entregável Chave |
|--------|----------------|-----------------|
| 0 | Fundação | Repositório + Docker + CI/CD |
| 1 | Dados | Schema DB completo + Migrations + `CommissionRate` |
| 2 | Identidade | JWT + RBAC + Back-office Admin |
| 3 | Frontend Shell | Design system + Layout + Rotas + `/home` + `CondominiumCard` |
| 4 | Mock ERP | Abstração ERP + MockClient + Seed com dados da PoC |
| 4b | Integração ERP | Descoberta DataSnap + DataSnapClient (sem data fixa) |
| 5 | Lançamento | Tabela operacional conectada à API |
| **5b** | **Implantação** | **Wizard go-live + Import CSV/XLSX + Saldo abertura + Débitos herdados** |
| 6 | Painel + Dashboard | `/home` consolidado por operador + KPIs + Charts + Inadimplentes |
| 7 | Estoque | Inventário + Alerta antifraude |
| 8 | Financeiro | Comissão `per_unit`/`fixed`/`percent` + Configurações |
| 9 | Evidências | Upload WebP + Static serving |
| 10 | Histórico | Consulta + Export + Reabertura |
| 11 | Qualidade | Testes + Segurança + Deploy |

---

## Diretrizes de UI — Fidelidade à PoC Aprovada

Todo componente frontend deve seguir os padrões visuais estabelecidos na PoC (`docs/index.html`):

| Token | Valor |
|-------|-------|
| Cor primária | `#2563eb` (blue-600) |
| Fundo da aplicação | `#f8fafc` (slate-50) |
| Cabeçalho/rodapé de tabela | `#1e293b` (slate-800) |
| Border-radius cards | `14px` |
| Borda lateral card KPI | `4px` colorida por status |
| Sombra card | `0 1px 3px rgba(0,0,0,.06), 0 4px 16px rgba(0,0,0,.05)` |
| Font | `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif` |
| Cor pago | `#22c55e` / `bg-green-100 text-green-700` |
| Cor em aberto | `#f59e0b` / `bg-amber-100 text-amber-700` |
| Cor inadimplente | `bg-red-100 text-red-700` |
| Linha nova (row-new) | `#fffbeb` hover `#fef3c7` |
| Animação entrada | `fadeUp 0.25s ease-out` |
