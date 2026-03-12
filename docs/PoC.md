
### Prompt para Geração da Prova de Conceito (PoC)

> **Contexto:**
> Atue como um Desenvolvedor Front-end Sênior e especialista em UI/UX. Preciso que você crie o código de uma Prova de Conceito (PoC) estática para um sistema web de gestão de consumo de água em condomínios. O objetivo desta PoC é ser apresentada aos gestores da empresa para aprovação visual e de fluxo de trabalho.
> **Tecnologias:**
> Utilize um arquivo único em HTML5. Para o design e responsividade, importe o **Tailwind CSS** via CDN. Para a renderização de gráficos, utilize o **Chart.js** via CDN. Opcionalmente, você pode usar Vue.js via CDN se facilitar a reatividade visual da interface. O design deve ser moderno, limpo, corporativo e passar credibilidade (sugestão de paleta: tons de azul, branco e cinza).
> **Base de Dados (Mock):**
> Utilize os dados da planilha de exemplo fornecida [INSERIR AQUI OS DADOS DA PLANILHA OU UM RESUMO DELA] para preencher as tabelas, gráficos e cards. Não use dados genéricos como "Lorem Ipsum"; os dados devem parecer reais.
> **Telas a serem desenvolvidas (podem ser abas navegáveis na mesma página ou seções distintas):**
> **1. Tela de Dashboard (Visão Gerencial):**
> * **Cards de Resumo:** Crie cards em destaque no topo exibindo: "Total Arrecadado (R$)", "Inadimplência (%)", "Total em Aberto (R$)" e "Consumo Total do Mês (m³)".
> * **Gráfico:** Um gráfico de rosca ou pizza mostrando o status de pagamento (Boletos Pagos x Em Aberto).
> * **Ranking:** Uma pequena tabela ou lista exibindo os 5 apartamentos com maior consumo no mês e uma lista de alerta com os moradores inadimplentes.
> 
> 
> **2. Tela de Lançamento de Consumo (Visão Operacional):**
> * **Cabeçalho da Ação:** Um campo de seleção de condomínio e dois inputs para definir a "Faixa de Apartamentos" (Ex: do 101 ao 1001), acompanhados de um botão "Gerar Lista".
> * **Tabela de Lançamento:** Uma tabela limpa e bem espaçada simulando o preenchimento. Colunas: "Apto", "CPF", "Nome do Morador", "Telefone", "Consumo (m³)" e "Valor Total (R$)".
> * **Regra de Negócio Visual:** Para demonstrar o funcionamento, deixe algumas linhas com os dados do morador bloqueados (simulando moradores antigos, apenas com o input de consumo m³ liberado e um ícone de "lápis" para edição do cadastro) e outras linhas com os campos em branco e habilitados (simulando moradores novos).
> 
> 
> **Instruções Finais:**
> O código deve vir completo, comentado e pronto para ser salvo como `index.html` e aberto diretamente no navegador. Foco em usabilidade e em impressionar visualmente os gestores.

---
