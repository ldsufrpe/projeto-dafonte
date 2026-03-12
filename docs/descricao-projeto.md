

Para o desenvolvimento deste projeto, uma pilha tecnológica baseada em **FastAPI** (para o back-end local/sincronização) e **Vue.js** (para a interface do usuário) seria uma escolha excelente, garantindo alta performance e reatividade para a listagem dinâmica de condomínios e dashboards.

Abaixo está o detalhamento do projeto.

---

### Visão Geral do Sistema Web

O sistema web tem o objetivo de registrar, calcular e gerenciar o consumo de água de condomínios mensalmente. Ele consumirá dados de uma API de retaguarda e enviará os fechamentos mensais para que a retaguarda processe as cobranças e disparos automáticos.

### 1. Autenticação e Sincronização

* O sistema web deverá possuir uma tela de login com usuário e senha.
* O sistema não dependerá exclusivamente de estar online com a retaguarda o tempo todo; ele deve possuir um banco de dados local para armazenar os dados e sincronizar o status de consumo com o sistema principal.

### 2. Cadastro Inicial e Seleção de Condomínio

* A criação do condomínio e a definição da tabela de preço da água são feitas no sistema de retaguarda.
* Ao iniciar um novo faturamento no sistema web, o usuário deve selecionar o condomínio desejado buscando-o na API.
* Caso o condomínio não tenha moradores cadastrados, o sistema web solicitará uma faixa de apartamentos (ex.: do 101 ao 1001) e gerará a lista na tela automaticamente em branco.
* Se o condomínio já possuir moradores cadastrados na retaguarda, o sistema já trará a lista preenchida.

### 3. Lançamento de Consumo Mensal e Gestão de Moradores

A tela de listagem de apartamentos gerenciará os dados dos moradores e as leituras de consumo.

* **Dados do Morador:** Cada linha de apartamento gerada terá os campos CPF, Nome, Telefone e E-mail (opcional).
* **Primeiro Consumo:** Os campos de identificação ficam inicialmente em branco e só são habilitados/exigidos quando houver o registro do primeiro consumo daquele apartamento.
* **Consumos Seguintes:** Nos meses subsequentes, os campos de moradores que já consumiram virão desabilitados. Haverá um ícone de edição (um "lápis") para permitir a alteração dos dados caso haja mudança de morador ou responsável.
* **Cálculo:** O usuário inserirá a quantidade de consumo do mês e o sistema calculará o valor total automaticamente (Quantidade × Valor Unitário do Condomínio).

### 4. Integração com a Retaguarda (API)

A comunicação entre o sistema web e a retaguarda será a espinha dorsal do faturamento.

* Ao finalizar os lançamentos e salvar, o sistema web enviará os dados processados via formato JSON para a retaguarda.
* A retaguarda será responsável por registrar as cobranças, gerar os boletos e disparar notificações via WhatsApp e E-mail.
* **Controle de Pagamento:** O sistema web terá uma API local para consumir os status de pagamento ou fará atualizações via *webhooks* / rotinas automáticas. O sistema de retaguarda avisará quando um boleto for pago ou não.
* **Alteração Pós-Faturamento:** Se houver necessidade de alterar o consumo de um morador cujo boleto já foi gerado, o sistema web deve identificar que o boleto existe, devolver o número de remessa/boleto para a retaguarda e solicitar a alteração ou baixa do título atual.

### 5. Dashboard de Indicadores

A tela inicial do condomínio no sistema web oferecerá uma visão gerencial do ciclo de faturamento.

* **Status de Pagamento:** Exibição do percentual de faturas pagas versus em aberto no condomínio.
* **Valores:** Demonstração do valor total arrecadado e do valor total em aberto.
* **Ranking de Consumo:** Indicadores mostrando os moradores com o maior consumo, tanto por quantidade de água quanto por valor financeiro.
* **Inadimplência:** Uma lista clicável com os condôminos que estão devendo, permitindo ao usuário abrir os detalhes para acionar possíveis cobranças.

---
