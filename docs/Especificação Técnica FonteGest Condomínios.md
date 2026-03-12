# **Documento de Especificação Técnica e Escopo de Engenharia**

**Projeto:** FonteGest Condomínios

**Objetivo:** Fornecer diretrizes arquiteturais e funcionais completas para fatiamento em épicos e sprints pelas equipes de Gerenciamento de Projetos e Engenharia de Software.

## ---

**1\. Visão Arquitetural e Stack Tecnológica**

O **FonteGest Condomínios** é uma plataforma de gestão operacional e financeira *API-First*. O sistema atua como interface ágil para operação de campo e sincroniza os dados processados com o ERP principal (Retaguarda).

* **Front-end (SPA):** Vue.js 3 (Composition API), Vite, TypeScript, Tailwind CSS e Chart.js.  
* **Back-end (API RESTful):** FastAPI (Python) nativamente assíncrono.  
* **Banco de Dados & ORM:** PostgreSQL em conjunto com SQLAlchemy 2.0 (modo async) e Pydantic para validação de dados.  
* **Gestão Administrativa (Back-office):** Implementação via SQLAdmin (ou FastAPI Amis Admin) protegida por dependências do FastAPI.  
* **Infraestrutura:** Docker e Docker Compose com pipeline CI/CD via GitHub Actions e GitHub Container Registry (GHCR).

## ---

**2\. Topologia de Rede e Infraestrutura (Docker)**

A infraestrutura deve garantir isolamento, segurança de rede e automação de deploys em ambiente de servidor compartilhado.

* **Isolamento de Banco de Dados:** O contêiner do PostgreSQL deve operar exclusivamente em uma rede Docker interna (ex: hidrogest\_network), sem mapeamento de portas (ex: 5432\) para o host.  
* **Automação de Migrations:** O *entrypoint* do contêiner da API deve executar compulsoriamente o comando alembic upgrade head antes de iniciar o servidor Uvicorn, garantindo a consistência do schema em atualizações.  
* **Proxy Reverso Interno:** O front-end Vue.js será servido por um contêiner Nginx. Este Nginx interceptará rotas /api e fará o proxy\_pass para o contêiner do FastAPI, eliminando regras de CORS e expondo apenas uma porta HTTP (ex: 8080\) para o proxy principal do host.

## ---

**3\. Integração com ERP Master (Retaguarda)**

A retaguarda é a única fonte da verdade para dados comerciais e cobranças. O back-end FastAPI atuará como middleware orquestrador.

* **Protocolo de Comunicação:** Integração via padrão REST/DataSnap (Delphi). O cliente HTTP utilizado no FastAPI deve ser o httpx (assíncrono) para evitar bloqueio de I/O.  
* **Tratamento de Payload:** A API deve aplicar rotinas de *unwrapping* para nivelar as respostas JSON encapsuladas características do DataSnap (ex: remoção de listas aninhadas em {"result": \[\[...\]\]}).  
* **Consumo de Dados (Inbound):** O web app solicitará à retaguarda a tabela de preços vigente (valores de galões de 10L e 20L), a lista de moradores ativos e o status de pagamento (faturas em aberto ou liquidadas).  
* **Envio de Lotes (Outbound):** Após o fechamento mensal, o sistema web enviará um payload (JSON) consolidado. A retaguarda assume a geração de boletos/remessas e os disparos de notificações (WhatsApp/E-mail).

## ---

**4\. Gestão de Identidade e Multi-Tenancy (RBAC)**

O sistema exige controle rigoroso de visualização de dados operacionais.

* **Nível Administrador:** Acesso integral ao back-office. Responsável por mapear e cadastrar os condomínios, associar operadores e definir os parâmetros de preço e comissionamento.  
* **Nível Operador:** Acesso restrito ao front-end de lançamentos. O login cruzará o token JWT com a base de dados, retornando estritamente a lista de condomínios associados ao operador logado.

## ---

**5\. Módulo Operacional e Lançamentos**

Interface focada em produtividade e consistência do banco de dados local.

* **Geração de Malha Lógica:** Para condomínios recém-cadastrados, o operador informará a numeração inicial e final (ex: 101 a 1801). A API gerará os registros correspondentes em branco.  
* **Ativação Tardia (Lazy Activation):** Campos de qualificação (CPF, Nome, Telefone) de novas unidades permanecerão bloqueados na UI. A edição só será habilitada se a quantidade de consumo informada for maior que zero.  
* **Edição de Responsabilidade:** Unidades com histórico poderão ter o titular alterado via interface (ícone de edição). A alteração será sinalizada no lote de fechamento para atualização da fatura na retaguarda.  
* **Consumo de Áreas Comuns:** Funcionalidade dedicada para registro de uso interno (zeladoria, portaria, eventos). Este volume deduzirá o estoque físico, mas não comporá o faturamento dos condôminos.

## ---

**6\. Módulo de Controle de Estoque (Auditoria)**

Motor lógico preventivo contra furtos e desvios operacionais.

* **Saldo Inicial de Implantação:** Cadastro do estoque físico presente no momento do *go-live* do condomínio.  
* **Lógica de Inventário:** Cálculo automatizado considerando: (Saldo Anterior \+ Entradas/Abastecimentos) \- Consumo Lançado.  
* **Alerta Antifraude:** O sistema não utilizará *hard lock* para lançamentos acima do estoque. Contudo, se a equação resultar em valor negativo, a interface exibirá um alerta visual de alta criticidade (linha vermelha/piscante) indicando divergência ou desvio de mercadoria.

## ---

**7\. Módulo Financeiro e Comissionamento**

Geração de KPIs de negócio para monitoramento tático.

* **Eficiência de Cobrança:** Dashboard consolidando Total Faturado versus Total Recebido (baixas da retaguarda). O cálculo da taxa percentual de sucesso avaliará a performance individual de cada operador.  
* **Motor de Comissionamento Contratual:** A API executará o cálculo da remuneração devida ao condomínio em dois regimes configuráveis por local:  
  1. **Valor Fixo:** Remuneração estática mensal (ex: 120 BRL).  
  2. **Percentual:** Alíquota calculada sobre o montante financeiro total consumido e faturado na competência.  
* **Indicadores Visuais:** Gráficos de inadimplência (Pagos x Em Aberto) e listagem nominal dos 5 maiores devedores.

## ---

**8\. Módulo de Evidências (Storage e Otimização)**

Sistema de anexos para resolução de contestações faturais, projetado para armazenamento contínuo por retenção de 5 anos.

* **Pipeline de Upload Assíncrono:** O endpoint de upload (/api/condominios/{id}/evidencias) aceitará imagens via multipart/form-data e delegará o processamento a uma BackgroundTask do FastAPI.  
* **Compressão e Higienização:** Utilização da biblioteca Pillow (Python) para redimensionar a imagem (max-width: 1280px) e convertê-la obrigatoriamente para o formato WebP. Arquivos não reconhecidos como imagens seguras serão rejeitados.  
* **Armazenamento de Alta Densidade (On-Premise):** Os arquivos processados serão persistidos em um Volume Docker (evidencias\_data) atrelado ao *host*. A organização do path seguirá particionamento hierárquico lógico (/ano/mes/condominio\_id/).  
* **Entrega de Arquivos (Static Serving):** O Nginx mapeará o diretório do volume em modo *read-only* (ro). A exibição das fotos no front-end ocorrerá com acesso direto ao servidor estático, eliminando requisições de leitura na API Python.