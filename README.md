# 🛡️ PNCP Collector & Analyzer (Mestrado Lab)

Aplicação web completa e intuitiva desenvolvida para **captura, mineração e análise de editais de compras públicas governamentais** no [Portal Nacional de Contratações Públicas (PNCP)](https://pncp.gov.br) no âmbito da Nova Lei de Licitações (Lei nº 14.133/2021).

Projetada especialmente para pesquisas acadêmicas (dissertações de mestrado e teses de doutorado) nas áreas de **Cibersegurança**, **Segurança da Informação**, **Tecnologia da Informação** e **Governança Pública**.

---

## 🌟 Principais Recursos

- **Busca Textual Completa com Operadores Booleanos:**
  - Suporta aspas duplas para termos exatos: `"segurança da informação"`, `"proteção de dados"`.
  - Suporta operadores lógicos: `cibersegurança OR cybersecurity`, `"tecnologia da informação" AND segurança`.
- **Atalhos Rápidos com 1 Clique (Presets):**
  - 🛡️ Cibersegurança & SOC
  - 🔒 Segurança da Informação & LGPD
  - 🌐 Redes & Firewall (WAF, IDS/IPS, VPN)
  - 💻 Software & Nuvem (SaaS, Cloud)
  - 🖥️ Servidores & Hardware
  - 🎓 Tecnologia da Informação em Geral
- **Feedback e Métricas em Tempo Real (via Server-Sent Events - SSE):**
  - **Cronômetro:** Tempo decorrido com precisão.
  - **Velocidade de Download:** Quantidade de editais processados por segundo.
  - **Previsão de Término (ETA):** Tempo estimado restante calculado dinamicamente.
  - **Barra de Progresso com Porcentagem.**
  - **Terminal de Logs:** Visualização das requisições técnicas em tempo real.
- **Explorador Interativo de Resultados:**
  - Tabela paginada com busca local instantânea.
  - **Ver Itens da Licitação:** Consulta a API do PNCP para exibir cada item individual, quantidade, unidade, descrição detalhada e valor unitário estimado.
  - **Ver Arquivos / PDFs:** Consulta os anexos oficiais da compra com links diretos para download do Edital e Termo de Referência.
  - **Visualizador de Objeto Completo:** Modal para leitura do texto integral do edital.
- **Dashboard e Estatísticas Automáticas:**
  - Gráfico de distribuição por Esfera (Federal, Estadual, Municipal).
  - Gráfico dos Estados (UFs) com maior volume de compras.
  - Soma total do volume financeiro estimado das licitações.
- **Exportação em 1 Clique:**
  - 📥 **JSON Completo:** Formato hierárquico bruto, pronto para análise em Python (Pandas/Jupyter), R, MongoDB ou mineração de texto/NLP.
  - 📊 **Planilha Excel (CSV):** Gerado com **BOM UTF-8** para abrir perfeitamente no Microsoft Excel sem corromper caracteres acentuados ou cedilhas.

---

## 🚀 Como Executar

A aplicação foi desenvolvida em **Python 3 puro** e utiliza Tailwind CSS / Chart.js via CDN. **Não é necessário instalar nenhum pacote via `pip` nem configurar ambiente virtual (`venv`)**!

### Passo 1: Acesse a pasta do projeto
```bash
cd ~/src/lab/pncp-collector
# ou
cd ~/scr/lab/pncp-collector
```

### Passo 2: Inicie o servidor
Basta executar o script de inicialização:
```bash
./iniciar.sh
```
Ou diretamente com Python:
```bash
python3 app.py
```

### Passo 3: Acesse no seu navegador
Abra o navegador em:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🔬 Entendendo os Endpoints do PNCP

Durante o desenvolvimento e análise do manual oficial (`Manual PNCP API Consultas – Versão 1.0.pdf`), identificamos duas APIs distintas:

1. **API Oficial de Consultas (`/api/consulta`):**
   - É a API documentada no manual em PDF.
   - **Limitação:** Não aceita busca textual (`q=...`). Exige `dataInicial`, `dataFinal` e código de modalidade da contratação. É voltada para sincronização massiva de dados brutos por data.
2. **API de Busca do Portal (`/api/search/`):**
   - É a API que alimenta a barra de busca de [pncp.gov.br/app/editais](https://pncp.gov.br/app/editais).
   - Suporta busca textual em Elasticsearch, filtros de UF, esfera, status e intervalos de publicação (`AAAA-MM-DD`).
   - O PNCP limita a paginação em 10.000 resultados por consulta (`pagina * tam_pagina <= 10000`), razão pela qual o portal web exibia 9.990 itens. Para contornar esse teto em termos muito amplos, basta aplicar filtros de datas menores na aplicação.
3. **API de Detalhes dos Itens (`/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens`):**
   - Retorna a lista dos itens da compra com CATMAT/CATSER, especificações e valores unitários.
4. **API de Anexos/Documentos (`/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`):**
   - Retorna os links para os PDFs oficiais do Edital e Termo de Referência.

---

## 📁 Estrutura de Arquivos

```
pncp-collector/
├── app.py              # Servidor backend Python (Proxy, SSE Streaming, Exportador)
├── iniciar.sh          # Script de execução em 1 comando
├── README.md           # Documentação completa
├── .gitignore          # Arquivos ignorados pelo Git
├── static/
│   └── index.html      # Interface frontend moderna (Tailwind, Chart.js, Lucide)
└── exports/            # Pasta temporária para armazenamento de exportações
```

---

## 🎓 Dica para a Metodologia do Mestrado

Para garantir a **reprodutibilidade científica** da sua dissertação:
1. Registre os parâmetros exatos utilizados na busca (termo `q`, período de datas e data/hora da coleta).
2. Salve o arquivo `.json` gerado na pasta do seu projeto de pesquisa. Ele contém todos os metadados brutos fornecidos pelo Governo Federal.
3. Se for citar a fonte dos dados:
   > BRASIL. Ministério da Gestão e da Inovação em Serviços Públicos. *Portal Nacional de Contratações Públicas (PNCP)*. Dados abertos governamentais estruturados conforme a Lei nº 14.133/2021. Disponível em: <https://pncp.gov.br>. Acesso em: [Data da Coleta].
