# 📋 Dashboard Allied — Controle de Cobrança

Dashboard Streamlit para análise e gestão de boletos em atraso da Allied Brasil (B2B).

## Funcionalidades

- **Dashboard de Cobrança** — métricas, gráficos por faixa de atraso, ranking de vendedores, tabela detalhada com seleção de boletos
- **Envio de Email** — relatórios individuais, em massa ou único para todos os vendedores (SMTP / Outlook)
- **Configurações** — cadastro de emails por vendedor, SMTP/IMAP, autenticação 2FA
- **Backup na nuvem** — persistência de dados e configurações via email (IMAP/SMTP)
- **Segurança** — login com 2FA, rate limiting, timeout de sessão

## Execução Local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ou use os arquivos `.bat` incluídos.

## Deploy (Streamlit Cloud)

1. Faça push para o GitHub
2. Conecte o repositório no [Streamlit Cloud](https://share.streamlit.io)
3. Configure os **Secrets** (Settings → Secrets) com o conteúdo de `secrets.toml`

## Tecnologias

- Python 3.10+
- Streamlit
- Pandas / Plotly
- pyxlsb (leitura de `.xlsb`)

---

Desenvolvido por Christian Krauss Rumayor — crumayor@alliedbrasil.com.br

## 📦 Criar Executável- Performance individual de cada vendedor

- Comparativo de resultados

### 1. Instalar PyInstaller- Taxa de conversão por vendedor

```bash- Distribuição de oportunidades

pip install pyinstaller- Análise detalhada com drill-down

```

### ✏️ Gerenciamento de Observações

### 2. Gerar ExecutávelSistema de anotações persistente que **não é perdido** quando a base principal é atualizada:

```bash- Adição de observações personalizadas

pyinstaller dashboard.spec- Sistema de prioridades (Baixa, Normal, Alta, Urgente)

```- Tags customizáveis para categorização

- Controle de próximo contato

O executável será criado em `dist/DashboardZohoCRM.exe`- Ações necessárias

- Histórico de atualizações

### 3. Criar Instalador com Inno Setup

### 📋 Visualização Completa de Dados

1. Baixe e instale o [Inno Setup](https://jrsoftware.org/isdl.php)- Tabela interativa com todos os dados

2. Abra o arquivo `installer.iss` no Inno Setup- Exportação para Excel

3. Clique em "Build" > "Compile"- Estatísticas gerais

4. O instalador será gerado em `Output/DashboardZohoCRM_Setup.exe`- Opções de paginação



## 📂 Estrutura de Arquivos## 🏗️ Arquitetura do Sistema



```### Separação de Dados

DashZoho-Allied/O sistema utiliza **dois arquivos distintos**:

├── app.py                                    # Aplicação principal

├── logo_allied.png                           # Logo da empresa1. **Oportunidades por Vendedores B2B.xlsx** (Base Principal)

├── observacoes_oportunidades.json            # Dados de observações   - Arquivo exportado do Zoho CRM

├── Oportunidades por Vendedores B2B .xlsx    # Base de dados   - Pode ser substituído a qualquer momento

├── requirements.txt                          # Dependências Python   - Contém todas as informações de oportunidades

├── dashboard.spec                            # Configuração PyInstaller

├── installer.iss                             # Script Inno Setup2. **observacoes_oportunidades.json** (Observações Persistentes)

├── INICIAR_DASHBOARD.bat                     # Atalho de inicialização   - Armazena observações, tags, prioridades e anotações

└── .streamlit/   - **Não é sobrescrito** quando a base principal é atualizada

    └── config.toml                           # Configurações Streamlit   - Vinculado pelo número de pedido

```   - Mesclado automaticamente com a base principal na visualização



## 🔧 Requisitos### Fluxo de Atualização

```

- Python 3.8+1. Exportar relatório do Zoho CRM

- Dependências listadas em `requirements.txt`2. Salvar como "Oportunidades por Vendedores B2B.xlsx" (substituindo o anterior)

3. Abrir o dashboard Streamlit

## 📝 Observações4. As observações salvas anteriormente serão automaticamente mescladas

```

- O executável busca os arquivos de dados (Excel, JSON, logo) no mesmo diretório onde está instalado

- Para atualizar a base de dados, substitua o arquivo Excel na pasta de instalação## 🚀 Instalação e Configuração

- As observações são salvas automaticamente no arquivo JSON

### Pré-requisitos

## 🎨 Cores Allied- Python 3.8 ou superior

- pip (gerenciador de pacotes Python)

- Azul Principal: #0066cc

- Laranja Destaque: #ff8c42### Passo 1: Instalar Dependências

- Fundo: #f5faff```bash

pip install -r requirements.txt

## 📧 Suporte```



Para dúvidas ou problemas, entre em contato com o departamento de TI.### Passo 2: Estrutura de Arquivos

Certifique-se de que seu diretório contenha:
```
DashZoho-Allied/
│
├── app.py                                      # Aplicação principal
├── requirements.txt                            # Dependências
├── Oportunidades por Vendedores B2B.xlsx      # Base de dados principal
├── observacoes_oportunidades.json             # Observações (criado automaticamente)
└── .streamlit/
    └── config.toml                            # Configurações do Streamlit
```

### Passo 3: Executar o Dashboard
```bash
streamlit run app.py
```

O dashboard será aberto automaticamente no navegador em `http://localhost:8501`

## 📖 Como Usar

### 1. Navegação por Abas

#### 📈 Visão Geral
- Visualize métricas principais do negócio
- Analise distribuição por status e estágio
- Acompanhe evolução temporal
- Identifique top fabricantes e produtos

#### 👥 Análise por Vendedor
- Compare performance entre vendedores
- Analise detalhes individuais
- Identifique top performers
- Monitore distribuição de oportunidades

#### 🎯 Análise de Oportunidades
- Visualize o funil de vendas
- Analise revendedores
- Identifique motivos de perda
- Monitore valor por estágio

#### ✏️ Gerenciar Observações
1. Selecione uma oportunidade
2. Adicione observações, tags e prioridade
3. Defina próximo contato e ações necessárias
4. Clique em "Salvar Observações"
5. As informações ficarão persistidas mesmo após atualização da base

#### 📋 Dados Completos
- Visualize tabela completa
- Exporte dados para Excel
- Consulte estatísticas gerais

### 2. Utilizando Filtros

Os filtros na barra lateral permitem análises personalizadas:

1. **Período**: Defina data inicial e final
2. **Vendedor**: Selecione um ou mais vendedores
3. **Status**: Filtre por status específicos
4. **Estágio**: Selecione estágios do funil
5. **Revendedor**: Filtre por parceiros
6. **Fabricante**: Analise por fornecedor
7. **Produto**: Foque em produtos específicos
8. **Valor**: Use o slider para definir faixa de valores
9. **Prioridade**: Filtre observações por prioridade

**Dica**: Combine múltiplos filtros para análises mais específicas!

### 3. Atualizando a Base de Dados

Para atualizar os dados do Zoho:

1. Baixe o relatório atualizado do Zoho CRM
2. Salve o arquivo como `Oportunidades por Vendedores B2B.xlsx`
3. Substitua o arquivo existente no diretório do projeto
4. Recarregue a página do Streamlit (F5)
5. ✅ As observações salvas anteriormente serão mantidas!

## 📊 Colunas da Base de Dados

| Coluna | Descrição |
|--------|-----------|
| Nome Negócio | Nome da oportunidade/negócio |
| Data Pedido | Data de criação do pedido |
| Cliente Nome | Nome do cliente |
| Revendedor 1 | Parceiro/revendedor principal |
| Revendedor 2 | Segundo revendedor (quando aplicável) |
| Proprietário do Negócio | Vendedor responsável |
| Número de Pedido | Identificador único do pedido |
| Oportunidade | ID da oportunidade |
| Estágio | Estágio atual no funil de vendas |
| Status da Oportunidade | Status atual (Ganha, Perdida, Em andamento, etc.) |
| Nome Produto | Produto vendido |
| Quantidade | Quantidade de produtos |
| Fabricante | Fabricante do produto |
| Valor do Pedido | Valor total do pedido |
| Descrição do Negócio | Descrição adicional |
| Motivo para a Perda | Motivo quando a oportunidade é perdida |
| Data de Fechamento | Data prevista/real de fechamento |
| Modificado Por | Último usuário que modificou |

## 🎨 Recursos Visuais

### Gráficos Disponíveis
- **Gráficos de Pizza**: Distribuição por status e estágio
- **Gráficos de Barras**: Top vendedores, produtos, fabricantes
- **Funil de Vendas**: Visualização do pipeline
- **Gráfico de Linha**: Evolução temporal
- **Métricas em Cards**: KPIs principais

### Cores e Temas
- Interface limpa e profissional
- Cores consistentes e harmoniosas
- Gráficos interativos com hover
- Design responsivo

## 🔧 Troubleshooting

### Erro ao Carregar Excel
**Problema**: Arquivo Excel não encontrado
**Solução**: Verifique se o arquivo está no diretório correto com o nome exato: `Oportunidades por Vendedores B2B .xlsx`

### Observações Não Aparecem
**Problema**: Observações salvas não aparecem após atualização
**Solução**: Verifique se o arquivo `observacoes_oportunidades.json` está presente no diretório

### Dashboard Não Inicia
**Problema**: Erro ao executar streamlit
**Solução**: 
```bash
# Reinstale as dependências
pip install -r requirements.txt --upgrade

# Execute novamente
streamlit run app.py
```

### Gráficos Não Carregam
**Problema**: Gráficos não aparecem ou estão em branco
**Solução**: Verifique se há dados após aplicar os filtros. Use o botão "Limpar Todos os Filtros" na sidebar.

## 📝 Manutenção

### Backup das Observações
Recomenda-se fazer backup periódico do arquivo `observacoes_oportunidades.json`:
```bash
# Windows PowerShell
Copy-Item "observacoes_oportunidades.json" "observacoes_oportunidades_backup_$(Get-Date -Format 'yyyyMMdd').json"
```

### Limpeza de Cache
Se notar comportamento inesperado, limpe o cache:
- Pressione 'C' no terminal onde o Streamlit está rodando
- Ou adicione `?clear_cache=true` na URL

## 🆘 Suporte

Para questões ou problemas:
1. Verifique se todas as dependências estão instaladas
2. Confirme que o arquivo Excel está no formato correto
3. Revise os logs no terminal para mensagens de erro
4. Certifique-se de estar usando Python 3.8+

## 📈 Próximas Melhorias Possíveis

- [ ] Integração direta com API do Zoho
- [ ] Alertas automáticos por email
- [ ] Dashboard mobile
- [ ] Relatórios PDF automatizados
- [ ] Previsão de vendas com IA
- [ ] Comparativo com períodos anteriores
- [ ] Metas e objetivos por vendedor

## 📄 Licença

Este projeto foi desenvolvido para uso interno da empresa.

---

**Desenvolvido com ❤️ usando Streamlit e Python**

*Última atualização: Novembro 2025*
