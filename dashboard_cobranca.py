import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
from config_emails import load_email_config, load_smtp_config, save_smtp_config
from email_utils import enviar_email_outlook, criar_corpo_email, enviar_email_smtp, verificar_smtp_auth
from utils import BASE_DIR


def find_aging_file():
    """Procura por arquivos .xlsb no diretório base, ignorando arquivos temporários do Excel"""
    xlsb_files = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    
    if len(xlsb_files) == 0:
        return None, "Nenhum arquivo Excel (.xlsb) foi encontrado no diretório da aplicação."
    elif len(xlsb_files) > 1:
        arquivos_encontrados = "\n".join([f"  • {f.name}" for f in xlsb_files])
        return None, f"⚠️ Foram encontrados {len(xlsb_files)} arquivos Excel (.xlsb) no diretório.\n\nArquivos encontrados:\n{arquivos_encontrados}\n\nPor favor, mantenha apenas 1 arquivo .xlsb no diretório."
    
    return xlsb_files[0], None


def get_cor_faixa_atraso(faixa):
    """Retorna a cor de fundo e texto baseada na faixa de atraso (amarelo claro → vermelho escuro)"""
    cores = {
        "1 a 3 dias": ("#FFF9C4", "#000000"),       # Amarelo bem claro
        "4 a 15 dias": ("#FFEB3B", "#000000"),      # Amarelo
        "16 a 30 dias": ("#FFC107", "#000000"),     # Âmbar
        "31 a 60 dias": ("#FF9800", "#000000"),     # Laranja
        "61 a 90 dias": ("#FF5722", "#FFFFFF"),     # Laranja escuro
        "91 a 120 dias": ("#F44336", "#FFFFFF"),    # Vermelho
        "121 a 150 dias": ("#E53935", "#FFFFFF"),   # Vermelho escuro
        "151 a 180 dias": ("#C62828", "#FFFFFF"),   # Vermelho mais escuro
        "181 a 365 dias": ("#B71C1C", "#FFFFFF"),   # Vermelho muito escuro
        "+365 dias": ("#880E4F", "#FFFFFF"),        # Bordô/Vinho
    }
    return cores.get(faixa, ("#FFFFFF", "#000000"))


def formatar_faixa_com_cor(faixa):
    """Retorna HTML com a faixa colorida"""
    if pd.isna(faixa) or faixa == '':
        return ''
    cor_fundo, cor_texto = get_cor_faixa_atraso(faixa)
    return f'<span style="background-color:{cor_fundo}; color:{cor_texto}; padding:2px 8px; border-radius:4px; font-weight:bold;">{faixa}</span>'


def get_indicador_faixa(faixa):
    """Retorna um indicador visual (emoji) para a faixa de atraso"""
    indicadores = {
        "1 a 3 dias": "🟡",        # Amarelo
        "4 a 15 dias": "🟡",       # Amarelo
        "16 a 30 dias": "🟠",      # Laranja
        "31 a 60 dias": "🟠",      # Laranja
        "61 a 90 dias": "🔴",      # Vermelho
        "91 a 120 dias": "🔴",     # Vermelho
        "121 a 150 dias": "🔴",    # Vermelho
        "151 a 180 dias": "🔴",    # Vermelho
        "181 a 365 dias": "🔴",    # Vermelho
        "+365 dias": "🟣",         # Roxo/Crítico
    }
    return indicadores.get(faixa, "⚪")


def formatar_faixa_com_indicador(faixa):
    """Retorna a faixa com indicador visual (bolinha colorida)"""
    if pd.isna(faixa) or faixa == '':
        return ''
    indicador = get_indicador_faixa(faixa)
    return f"{indicador} {faixa}"


def limpar_faixa_indicador(faixa_com_indicador):
    """Remove o indicador visual (emoji) da faixa de atraso para uso em emails"""
    if pd.isna(faixa_com_indicador) or faixa_com_indicador == '':
        return ''
    # Remover emojis comuns usados como indicadores
    emojis = ['🟡', '🟠', '🔴', '🟣', '⚪', ' ']
    resultado = str(faixa_com_indicador)
    for emoji in emojis:
        resultado = resultado.replace(emoji, '')
    return resultado.strip()

@st.cache_data(ttl=300, show_spinner="Carregando dados...")
def load_aging_data():
    """Carrega os dados do arquivo de aging - OTIMIZADO para velocidade"""
    aging_file, erro = find_aging_file()
    
    if aging_file is None:
        return pd.DataFrame(), erro
    
    try:
        # Ler apenas as primeiras 10 linhas para detectar header rapidamente
        df_sample = pd.read_excel(str(aging_file), sheet_name='BaseDados', header=None, 
                                   engine='pyxlsb', nrows=10)
        
        # Encontrar linha do header (procura por 'Venc.Atual' ou 'vencimento')
        header_row = 3  # Valor padrão
        for idx, row in df_sample.iterrows():
            row_str = ' '.join(str(v).lower() for v in row if pd.notna(v))
            if 'venc' in row_str and 'atual' in row_str:
                header_row = idx
                break
        
        # Definir colunas necessárias para otimizar leitura
        colunas_necessarias = None  # Ler todas as colunas mas otimizar tipos
        
        # Ler arquivo com header correto - uma única leitura
        df = pd.read_excel(str(aging_file), sheet_name='BaseDados', header=header_row, 
                          engine='pyxlsb')
        
        # Limpar nomes de colunas (remover espaços extras)
        df.columns = df.columns.str.strip()
        
        # Encontrar coluna de vencimento de forma otimizada
        colunas_lower = {str(col).lower().strip(): col for col in df.columns}
        coluna_venc = None
        
        for col_lower, col_original in colunas_lower.items():
            if 'venc' in col_lower and 'atual' in col_lower:
                coluna_venc = col_original
                break
        
        if coluna_venc is None:
            for col_lower, col_original in colunas_lower.items():
                if 'venc' in col_lower:
                    coluna_venc = col_original
                    break
        
        if coluna_venc is None:
            colunas = ", ".join([str(c) for c in df.columns.tolist()])
            return pd.DataFrame(), f"Coluna de vencimento não encontrada. Colunas disponíveis: {colunas}"
        
        # Converter coluna de vencimento para datetime de forma otimizada
        df[coluna_venc] = pd.to_datetime(df[coluna_venc], errors='coerce', unit='D', origin='1899-12-30')
        
        # Renomear para padrão interno
        df = df.rename(columns={coluna_venc: 'Venc.Atual'})
        
        # Remover linhas vazias
        df = df.dropna(subset=['Venc.Atual'], how='all')
        
        # Otimizar tipos de dados para reduzir memória
        for col in df.select_dtypes(include=['object']).columns:
            nunique = df[col].nunique()
            if nunique < len(df) * 0.1:  # Se menos de 10% são únicos
                df[col] = df[col].astype('category')
        
        return df, None
    except Exception as e:
        import traceback
        erro_detalhado = traceback.format_exc()
        return pd.DataFrame(), f"Erro ao carregar arquivo: {str(e)}\n\nDetalhes: {erro_detalhado}"

def calcular_dias_atraso(data_vencimento, data_referencia=None):
    """Calcula o número de dias em atraso
    
    Args:
        data_vencimento: Data de vencimento
        data_referencia: Data para calcular atraso (padrão: data atual)
    """
    if pd.isna(data_vencimento):
        return None
    
    if data_referencia is None:
        data_referencia = datetime.now().date()
    elif isinstance(data_referencia, datetime):
        data_referencia = data_referencia.date()
    
    data_venc = pd.to_datetime(data_vencimento).date()
    dias = (data_referencia - data_venc).days
    
    return dias if dias > 0 else None

def classificar_atraso(dias_atraso):
    """Classifica o atraso em faixas"""
    if dias_atraso is None:
        return None
    
    if 1 <= dias_atraso <= 3:
        return "1 a 3 dias"
    elif 4 <= dias_atraso <= 15:
        return "4 a 15 dias"
    elif 16 <= dias_atraso <= 30:
        return "16 a 30 dias"
    elif 31 <= dias_atraso <= 60:
        return "31 a 60 dias"
    elif 61 <= dias_atraso <= 90:
        return "61 a 90 dias"
    elif 91 <= dias_atraso <= 120:
        return "91 a 120 dias"
    elif 121 <= dias_atraso <= 150:
        return "121 a 150 dias"
    elif 151 <= dias_atraso <= 180:
        return "151 a 180 dias"
    elif 181 <= dias_atraso <= 365:
        return "181 a 365 dias"
    else:
        return "+365 dias"

@st.cache_data(ttl=300, show_spinner=False)
def load_observacoes_atrasos():
    """Carrega observações da aba 'Atrasos' para cruzamento por Grupo Cliente - OTIMIZADO"""
    aging_file, _ = find_aging_file()
    
    if aging_file is None:
        return {}
    
    try:
        # Ler apenas as primeiras 10 linhas para detectar header
        df_sample = pd.read_excel(str(aging_file), sheet_name='Atrasos', header=None, 
                                   engine='pyxlsb', nrows=10)
        
        # Encontrar linha do header
        header_row = 3  # Valor padrão
        for idx, row in df_sample.iterrows():
            row_str = ' '.join(str(v).lower() for v in row if pd.notna(v))
            if ('grupo' in row_str or 'cliente' in row_str) and ('observacao' in row_str or 'obs' in row_str):
                header_row = idx
                break
        
        # Ler arquivo com header correto - única leitura
        df_atrasos = pd.read_excel(str(aging_file), sheet_name='Atrasos', header=header_row, engine='pyxlsb')
        
        # Encontrar colunas de Grupo Cliente e Observação
        col_grupo = None
        col_obs = None
        
        for col in df_atrasos.columns:
            col_lower = str(col).lower().strip()
            if 'grupo' in col_lower or 'cliente' in col_lower:
                col_grupo = col
            if 'observacao' in col_lower or 'obs' in col_lower:
                col_obs = col
        
        if col_grupo is None or col_obs is None:
            # Fallback: usar as colunas por índice (B e R)
            cols = df_atrasos.columns.tolist()
            if len(cols) >= 18:
                col_grupo = cols[1]  # Coluna B = índice 1
                col_obs = cols[17]   # Coluna R = índice 17
            else:
                return {}
        
        # Selecionar colunas e normalizar
        df_obs = df_atrasos[[col_grupo, col_obs]].copy()
        df_obs.columns = ['Grupo_Cliente', 'Observacao']
        
        # Remover NaN
        df_obs = df_obs.dropna()
        
        # Normalizar
        df_obs['Grupo_Cliente'] = df_obs['Grupo_Cliente'].astype(str).str.strip().str.lower()
        df_obs['Observacao'] = df_obs['Observacao'].astype(str).str.strip()
        
        # Remover vazios
        df_obs = df_obs[(df_obs['Grupo_Cliente'].str.len() > 0) & (df_obs['Observacao'].str.len() > 0)]
        
        # Converter para dicionário
        observacoes_dict = dict(df_obs.drop_duplicates(subset=['Grupo_Cliente'], keep='last').values)
        
        return observacoes_dict
    except Exception as e:
        return {}

def buscar_observacao(grupo_cliente):
    """
    Busca observação baseada em Grupo Cliente
    """
    observacoes = load_observacoes_atrasos()
    
    if not observacoes or pd.isna(grupo_cliente):
        return None
    
    # Normalizar Grupo Cliente
    grupo_cliente_str = str(grupo_cliente).strip().lower()
    
    if not grupo_cliente_str:
        return None
    
    # Buscar correspondência exata (case-insensitive)
    if grupo_cliente_str in observacoes:
        return observacoes[grupo_cliente_str]
    
    return None

def formatar_moeda_br(valor):
    """Formata valor em moeda brasileira"""
    if pd.isna(valor) or valor == 0:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def formatar_titulo(titulo):
    """Remove vírgula do título e exibe como número inteiro (sem '.0')"""
    if pd.isna(titulo):
        return ""
    titulo_str = str(titulo).replace(',', '').strip()
    if '.' in titulo_str:
        try:
            titulo_str = str(int(float(titulo_str)))
        except (ValueError, OverflowError):
            titulo_str = titulo_str.split('.')[0]
    return titulo_str

def formatar_dias_atraso(dias):
    """Formata dias de atraso substituindo vírgula por ponto"""
    if pd.isna(dias):
        return ""
    return str(int(dias)).replace(',', '.')

def formatar_cnpj_cpf(valor):
    """Formata CNPJ/CPF, removendo sufixo float '.0' e completando zeros à esquerda"""
    if pd.isna(valor):
        return ""
    valor_str = str(valor).strip()
    # Remover parte decimal do float (ex: '12345678000195.0' -> '12345678000195')
    if '.' in valor_str:
        try:
            valor_str = str(int(float(valor_str)))
        except (ValueError, OverflowError):
            valor_str = valor_str.split('.')[0]
    # Extrair apenas dígitos
    apenas_numeros = ''.join(c for c in valor_str if c.isdigit())
    if not apenas_numeros:
        return ""
    # Preencher zeros à esquerda conforme o documento
    # Mais de 11 dígitos → CNPJ (14 dígitos); até 11 → CPF (11 dígitos)
    if len(apenas_numeros) > 11:
        apenas_numeros = apenas_numeros.zfill(14)
    else:
        apenas_numeros = apenas_numeros.zfill(11)
    if len(apenas_numeros) == 11:  # CPF
        return f"{apenas_numeros[:3]}.{apenas_numeros[3:6]}.{apenas_numeros[6:9]}-{apenas_numeros[9:11]}"
    elif len(apenas_numeros) == 14:  # CNPJ
        return f"{apenas_numeros[:2]}.{apenas_numeros[2:5]}.{apenas_numeros[5:8]}/{apenas_numeros[8:12]}-{apenas_numeros[12:14]}"
    else:
        return apenas_numeros

def formatar_telefone(telefone):
    """Formata telefone adicionando / quando existe espaço"""
    if pd.isna(telefone):
        return ""
    telefone_str = str(telefone).strip()
    # Se há espaço e não há barra, adicionar barra no espaço
    if ' ' in telefone_str and '/' not in telefone_str:
        return telefone_str.replace(' ', '/')
    return telefone_str

def formatar_pedido_cliente(pedido):
    """Remove vírgula do pedido cliente"""
    if pd.isna(pedido):
        return ""
    return str(pedido).replace(',', '').strip()

def formatar_texto_simples(texto):
    """Formata texto simples substituindo None/NaN por vazio"""
    if pd.isna(texto) or texto is None:
        return ""
    return str(texto).strip()

def render_dashboard_cobranca():
    """Renderiza o dashboard de cobrança"""

    # ---- widget de atualização de senha SMTP (aparece quando a senha expirou) ----
    if st.session_state.get('smtp_senha_expirada', False):
        st.warning("⚠️ A senha SMTP está expirada ou inválida. Atualize abaixo para continuar enviando por SMTP.")
        with st.form("form_atualizar_senha_smtp", clear_on_submit=True):
            nova_senha = st.text_input("Nova senha SMTP", type="password", placeholder="Cole a nova senha aqui")
            atualizar = st.form_submit_button("🔑 Atualizar Senha e Reenviar", use_container_width=True)
        if atualizar:
            if not nova_senha.strip():
                st.error("❌ Informe a nova senha.")
            else:
                smtp_cfg = load_smtp_config()
                smtp_cfg['senha'] = nova_senha.strip()
                save_smtp_config(smtp_cfg)
                # Re-testar a nova senha
                valido, msg = verificar_smtp_auth(
                    servidor_smtp=smtp_cfg.get('servidor'),
                    porta=smtp_cfg.get('porta', 587),
                    usuario=smtp_cfg.get('usuario'),
                    senha=nova_senha.strip(),
                    usar_tls=smtp_cfg.get('usar_tls', True)
                )
                if valido:
                    st.success("✅ Senha atualizada e validada com sucesso!")
                    st.session_state.smtp_senha_expirada = False
                    st.rerun()
                else:
                    st.error(f"❌ A nova senha também não funcionou: {msg}")
        st.markdown("---")
    
    # Carregar dados
    df = st.session_state.get('df_aging', pd.DataFrame())
    erro_carregamento = st.session_state.get('erro_aging', None)
    
    if erro_carregamento:
        st.error(f"❌ {erro_carregamento}")
        st.info(f"📂 Diretório: {BASE_DIR}")
        return
    
    if df.empty:
        df, erro = load_aging_data()
        st.session_state.df_aging = df
        st.session_state.erro_aging = erro
        
        if erro:
            st.error(f"❌ {erro}")
            return
    
    # Filtrar apenas Diretor = "B2B" (caso a coluna exista)
    if 'Diretor' in df.columns:
        df = df[df['Diretor'] == 'B2B'].copy()
    
    # Filtrar apenas Portador Ajustado com valores específicos
    portadores_permitidos = ['Boleto', 'Disponível', 'TED', 'Serviço']
    if 'Portador Ajustado' in df.columns:
        df = df[df['Portador Ajustado'].isin(portadores_permitidos)].copy()
    
    if df.empty:
        st.warning("⚠️ Nenhum dado disponível após filtros (Diretor 'B2B' e Portadores: Boleto, Disponível, TED, Serviço)")
        return
    
    # Verificar colunas obrigatórias
    colunas_obrigatorias = ['Venc.Atual', 'Cliente', 'Saldo Atual', 'Nome Vendedor']
    colunas_faltando = [col for col in colunas_obrigatorias if col not in df.columns]
    
    if colunas_faltando:
        st.error(f"❌ Colunas obrigatórias faltando: {', '.join(colunas_faltando)}")
        return
    
    # Título
    st.markdown('<h1 style="color: #ff6b35; text-align: center;">📋 Dashboard Controle de Cobrança</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Sidebar - Data de Referência (para cálculo de atrasos)
    st.sidebar.title("📅 Data de Referência")
    usar_data_customizada = st.sidebar.checkbox("Usar data customizada para calcular atrasos?", value=False)
    
    if usar_data_customizada:
        data_referencia = st.sidebar.date_input(
            "Escolha a data de referência:",
            value=datetime.now().date(),
            format="DD/MM/YYYY",
            help="Selecione a data que deseja usar para calcular os dias em atraso"
        )
    else:
        data_referencia = datetime.now().date()
        st.sidebar.info(f"📆 Usando data atual: **{data_referencia.strftime('%d/%m/%Y')}**")
    
    st.sidebar.markdown("---")
    
    # Recalcular dias em atraso com a data escolhida - OTIMIZADO (vetorizado)
    df['Dias_Atraso'] = (pd.to_datetime(data_referencia) - df['Venc.Atual']).dt.days
    df.loc[df['Dias_Atraso'] <= 0, 'Dias_Atraso'] = None  # Atrasos positivos apenas
    
    df['Faixa_Atraso'] = df['Dias_Atraso'].apply(classificar_atraso)
    
    # Carregar observações UMA VEZ e buscar em batch (SUPER OTIMIZADO)
    observacoes = load_observacoes_atrasos()
    df['Observacao'] = df['Grupo Cliente'].apply(
        lambda x: observacoes.get(str(x).strip().lower(), None) if pd.notna(x) and observacoes else None
    )
    
    # Filtrar apenas registros em atraso
    df_atraso = df[df['Dias_Atraso'].notna()].copy()
    
    if df_atraso.empty:
        st.success("✅ Nenhum boleto em atraso encontrado!")
        return
    
    # Sidebar - Filtros
    st.sidebar.title("🔍 Filtros")
    
    # Mostrar arquivo carregado
    aging_file, _ = find_aging_file()
    if aging_file:
        st.sidebar.caption(f"📁 **Arquivo:** {aging_file.name}")
        st.sidebar.markdown("---")
    
    # Obter vendedores únicos
    vendedores = sorted(df_atraso['Nome Vendedor'].dropna().unique().tolist())
    
    vendedor_selecionado = st.sidebar.selectbox(
        "Selecione o Vendedor",
        options=["TODOS"] + vendedores,
        index=0
    )
    
    # Filtrar por vendedor
    if vendedor_selecionado != "TODOS":
        df_filtrado = df_atraso[df_atraso['Nome Vendedor'] == vendedor_selecionado].copy()
    else:
        df_filtrado = df_atraso.copy()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_boletos = len(df_filtrado)
        st.metric("📊 Total de Boletos", total_boletos, delta=None)
    
    with col2:
        valor_total_atraso = df_filtrado['Saldo Atual'].sum()
        st.metric("💰 Valor Total em Atraso", formatar_moeda_br(valor_total_atraso), delta=None)
    
    with col3:
        media_dias_atraso = df_filtrado['Dias_Atraso'].mean()
        st.metric("📅 Média de Dias em Atraso", f"{media_dias_atraso:.0f} dias", delta=None)
    
    with col4:
        ticket_medio = df_filtrado['Saldo Atual'].mean()
        st.metric("🎟️ Ticket Médio", formatar_moeda_br(ticket_medio), delta=None)
    
    st.markdown("---")
    
    # Tabs principais
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumo por Faixa de Atraso", "📈 Análises", "📋 Detalhes dos Boletos", "🎯 Por Cliente"])
    
    # TAB 1: Resumo por Faixa de Atraso
    with tab1:
        st.subheader("Resumo de Boletos por Faixa de Atraso")
        
        # Ordenar faixas corretamente
        ordem_faixas = [
            "1 a 3 dias", "4 a 15 dias", "16 a 30 dias",
            "31 a 60 dias", "61 a 90 dias", "91 a 120 dias",
            "121 a 150 dias", "151 a 180 dias", "181 a 365 dias", "+365 dias"
        ]
        
        resumo_faixa = df_filtrado.groupby('Faixa_Atraso').agg({
            'Título': 'count',
            'Saldo Atual': 'sum',
            'Dias_Atraso': 'mean'
        }).rename(columns={
            'Título': 'Qtd. Boletos',
            'Saldo Atual': 'Valor Total',
            'Dias_Atraso': 'Dias Médios'
        })
        
        # Reindexar para ordem correta
        resumo_faixa = resumo_faixa.reindex([f for f in ordem_faixas if f in resumo_faixa.index])
        
        # Formatar valores
        resumo_faixa_display = resumo_faixa.copy()
        resumo_faixa_display['Valor Total'] = resumo_faixa_display['Valor Total'].apply(formatar_moeda_br)
        resumo_faixa_display['Dias Médios'] = resumo_faixa_display['Dias Médios'].apply(lambda x: f"{x:.0f}")
        
        # Função para aplicar cores nas linhas baseado no índice (faixa de atraso)
        def colorir_linha_por_faixa(row):
            faixa = row.name  # O índice é a faixa de atraso
            cor_fundo, cor_texto = get_cor_faixa_atraso(faixa)
            return [f'background-color: {cor_fundo}; color: {cor_texto}; font-weight: bold'] * len(row)
        
        # Aplicar estilo e exibir tabela
        styled_df = resumo_faixa_display.style.apply(colorir_linha_por_faixa, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Gráfico de boletos por faixa
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            dados_grafico = df_filtrado.groupby('Faixa_Atraso')['Título'].count().reindex(
                [f for f in ordem_faixas if f in df_filtrado['Faixa_Atraso'].unique()]
            )
            
            fig = px.bar(
                x=dados_grafico.index,
                y=dados_grafico.values,
                labels={'x': 'Faixa de Atraso', 'y': 'Quantidade'},
                title="Quantidade de Boletos por Faixa de Atraso",
                color=dados_grafico.values,
                color_continuous_scale="Reds"
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col_chart2:
            dados_valor = df_filtrado.groupby('Faixa_Atraso')['Saldo Atual'].sum().reindex(
                [f for f in ordem_faixas if f in df_filtrado['Faixa_Atraso'].unique()]
            )
            
            fig = px.bar(
                x=dados_valor.index,
                y=dados_valor.values,
                labels={'x': 'Faixa de Atraso', 'y': 'Valor (R$)'},
                title="Valor Total por Faixa de Atraso",
                color=dados_valor.values,
                color_continuous_scale="Oranges"
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 2: Análises
    with tab2:
        st.subheader("Análises Detalhadas")
        
        col_a1, col_a2 = st.columns(2)
        
        # Ranking de vendedores por valor em atraso (usa apenas vendedores do filtro sidebar)
        with col_a1:
            # Usar apenas os vendedores que existem na lista do sidebar (resolve problema de categorias fantasmas)
            df_ranking = df_atraso[df_atraso['Nome Vendedor'].isin(vendedores)].copy()
            df_ranking['Nome Vendedor'] = df_ranking['Nome Vendedor'].astype(str)
            
            dados_vendedor = df_ranking.groupby('Nome Vendedor').agg({
                'Título': 'count',
                'Saldo Atual': 'sum'
            }).rename(columns={'Título': 'Qtd_Boletos', 'Saldo Atual': 'Valor_Total'})
            dados_vendedor = dados_vendedor.sort_values('Valor_Total', ascending=True)
            
            # Texto formatado para exibir no gráfico
            dados_vendedor['Valor_Fmt'] = dados_vendedor['Valor_Total'].apply(formatar_moeda_br)
            dados_vendedor['Label'] = dados_vendedor.apply(
                lambda r: f"{r['Valor_Fmt']}  ({int(r['Qtd_Boletos'])} {'boleto' if r['Qtd_Boletos'] == 1 else 'boletos'})", axis=1
            )
            
            # Cores em gradiente laranja (combinando com o tema do dashboard)
            n = len(dados_vendedor)
            if vendedor_selecionado == "TODOS":
                cores = [f"rgba(255, {200 - int(i * 130 / max(n-1, 1))}, {100 - int(i * 80 / max(n-1, 1))}, 0.9)" for i in range(n)]
            else:
                cores = [
                    'rgba(255, 107, 53, 0.95)' if nome == vendedor_selecionado else 'rgba(200, 200, 200, 0.5)'
                    for nome in dados_vendedor.index
                ]
            
            # Cor do texto: escuro para outside, branco para barras coloridas
            cores_texto = []
            for i, nome in enumerate(dados_vendedor.index):
                if vendedor_selecionado != "TODOS" and nome != vendedor_selecionado:
                    cores_texto.append('rgba(100,100,100,0.8)')
                else:
                    cores_texto.append('rgba(80,80,80,1)')
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=dados_vendedor.index,
                x=dados_vendedor['Valor_Total'],
                orientation='h',
                text=dados_vendedor['Label'],
                textposition='outside',
                textfont=dict(size=11, color=cores_texto, family='Arial'),
                marker=dict(color=cores, line=dict(color='rgba(0,0,0,0.15)', width=1)),
                hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>'
            ))
            
            titulo_grafico = "🏆 Ranking - Valor em Atraso por Vendedor"
            if vendedor_selecionado != "TODOS":
                titulo_grafico += f"  (destaque: {vendedor_selecionado})"
            
            max_valor = dados_vendedor['Valor_Total'].max() if len(dados_vendedor) > 0 else 0
            
            fig.update_layout(
                title=dict(text=titulo_grafico, font=dict(size=15)),
                height=max(400, n * 40 + 100),
                xaxis=dict(
                    title="Valor em Atraso (R$)", 
                    showgrid=True, 
                    gridcolor='rgba(0,0,0,0.08)',
                    range=[0, max_valor * 1.45]  # Espaço extra para labels outside
                ),
                yaxis=dict(title="", tickfont=dict(size=11)),
                plot_bgcolor='rgba(250,250,252,1)',
                margin=dict(l=10, r=20, t=50, b=40),
                bargap=0.25
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Boletos por condição de pagamento
        with col_a2:
            if 'Cond.Pagamento' in df_filtrado.columns:
                dados_cond = df_filtrado.groupby('Cond.Pagamento').agg({
                    'Título': 'count',
                    'Saldo Atual': 'sum'
                }).sort_values('Saldo Atual', ascending=False).head(10)
                
                fig = px.pie(
                    values=dados_cond['Saldo Atual'],
                    names=dados_cond.index,
                    title="Distribuição por Condição de Pagamento",
                    hole=0.4
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
    
    # TAB 3: Detalhes dos Boletos
    with tab3:
        st.subheader("Lista Detalhada de Boletos em Atraso")
        
        # Colunas para exibição - ordem definida pelo usuário
        colunas_exibir = [
            'Cliente', 'CNPJ/CPF', 'Revenda', 'Título', 'Saldo Atual',
            'Cond.Pagamento', 'Venc.Atual', 'Dias_Atraso', 'Faixa_Atraso', 'Observacao', 
            'Última Ocorrência', 'Pedido Cliente', 'Pedido', 'Telefone Cliente',
            'Nome Vendedor'
        ]
        
        colunas_existentes = [col for col in colunas_exibir if col in df_filtrado.columns]
        df_exibir = df_filtrado[colunas_existentes].copy()
        
        # Formatar colunas
        if 'Venc.Atual' in df_exibir.columns:
            df_exibir['Venc.Atual'] = df_exibir['Venc.Atual'].dt.strftime('%d/%m/%Y')
        
        if 'Título' in df_exibir.columns:
            df_exibir['Título'] = df_exibir['Título'].apply(formatar_titulo)
        
        if 'Dias_Atraso' in df_exibir.columns:
            df_exibir['Dias_Atraso'] = df_exibir['Dias_Atraso'].apply(formatar_dias_atraso)
        
        if 'CNPJ/CPF' in df_exibir.columns:
            df_exibir['CNPJ/CPF'] = df_exibir['CNPJ/CPF'].apply(formatar_cnpj_cpf)
        
        if 'Telefone Cliente' in df_exibir.columns:
            df_exibir['Telefone Cliente'] = df_exibir['Telefone Cliente'].apply(formatar_telefone)
        
        if 'Pedido Cliente' in df_exibir.columns:
            df_exibir['Pedido Cliente'] = df_exibir['Pedido Cliente'].apply(formatar_pedido_cliente)
        
        if 'Pedido' in df_exibir.columns:
            df_exibir['Pedido'] = df_exibir['Pedido'].apply(formatar_pedido_cliente)
        
        # Aplicar indicador visual (bolinha colorida) na coluna Faixa_Atraso
        if 'Faixa_Atraso' in df_exibir.columns:
            df_exibir['Faixa_Atraso'] = df_exibir['Faixa_Atraso'].apply(formatar_faixa_com_indicador)
        
        if 'Saldo Atual' in df_exibir.columns:
            df_exibir['Saldo Atual'] = df_exibir['Saldo Atual'].apply(formatar_moeda_br)
        
        if 'Última Ocorrência' in df_exibir.columns:
            _dt_temp = pd.to_datetime(df_exibir['Última Ocorrência'], errors='coerce')
            df_exibir['Última Ocorrência'] = _dt_temp.apply(lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else '')
        
        # Substituir todos os None/NaN por string vazia em todas as colunas de texto
        # Primeiro converter Categorical para string para evitar erro de categoria
        colunas_texto = ['Cliente', 'Revenda', 'Cond.Pagamento', 'Observacao', 'Nome Vendedor']
        for col in colunas_texto:
            if col in df_exibir.columns:
                # Converter para string antes de fillna (resolve problema com Categorical)
                df_exibir[col] = df_exibir[col].astype(str).replace({'nan': '', 'None': '', '<NA>': ''})
        
        # Ordenar por dias em atraso (decrescente)
        if 'Dias_Atraso' in df_exibir.columns:
            df_exibir = df_exibir.sort_values('Dias_Atraso', ascending=False, key=pd.to_numeric, na_position='last')
        
        # Resetar índice para evitar problemas
        df_exibir = df_exibir.reset_index(drop=True)
        
        # Converter todo o DataFrame para string e substituir NaN/None/NaT por vazio
        for col in df_exibir.columns:
            if df_exibir[col].dtype.name == 'category':
                df_exibir[col] = df_exibir[col].astype(str)
        df_exibir = df_exibir.fillna('').replace({'nan': '', 'None': '', 'NaT': '', '<NA>': ''})
        
        # Adicionar coluna de seleção (checkbox) - por padrão todos selecionados
        df_exibir.insert(0, '✓', True)
        
        # Botões de seleção rápida
        col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 4])
        with col_sel1:
            if st.button("✅ Selecionar Todos", use_container_width=True, key="btn_sel_todos"):
                st.session_state.df_selecao_todos = True
                st.rerun()
        with col_sel2:
            if st.button("❌ Desmarcar Todos", use_container_width=True, key="btn_desel_todos"):
                st.session_state.df_selecao_todos = False
                st.rerun()
        
        # Aplicar seleção em massa se solicitado
        if 'df_selecao_todos' in st.session_state:
            df_exibir['✓'] = st.session_state.df_selecao_todos
            del st.session_state.df_selecao_todos
        
        # Usar data_editor para permitir seleção (altura fixa para melhor navegação)
        df_editado = st.data_editor(
            df_exibir,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "✓": st.column_config.CheckboxColumn(
                    "Enviar",
                    help="Marque os boletos que deseja incluir no email",
                    default=True,
                    width="small"
                )
            },
            disabled=[col for col in df_exibir.columns if col != '✓'],  # Só permite editar checkbox
            key="data_editor_boletos"
        )
        
        # Contar selecionados
        total_boletos = len(df_editado)
        selecionados = df_editado['✓'].sum()
        st.caption(f"📊 **{selecionados}** de **{total_boletos}** boletos selecionados para envio")
        
        # Filtrar apenas os selecionados para uso posterior
        df_selecionados = df_editado[df_editado['✓'] == True].drop(columns=['✓'])
        
        # Seção de download e envio de email
        st.markdown("---")
        col_download, col_email = st.columns(2)
        
        with col_download:
            # Download dos dados (apenas selecionados)
            csv = df_selecionados.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label=f"📥 Baixar CSV ({len(df_selecionados)} boletos)",
                data=csv,
                file_name=f"boletos_atraso_{vendedor_selecionado}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_email:
            # Inicializar session_state para controle do modal de email
            if 'mostrar_preview_email' not in st.session_state:
                st.session_state.mostrar_preview_email = False
            if 'email_resultado' not in st.session_state:
                st.session_state.email_resultado = None
            
            # Verificar se há boletos selecionados
            if selecionados == 0:
                st.warning("⚠️ Selecione pelo menos 1 boleto")
            elif st.button(f"📧 Enviar por Email ({selecionados} boletos)", use_container_width=True, key="btn_abrir_email"):
                st.session_state.mostrar_preview_email = True
                st.session_state.email_resultado = None
        
        # Exibir resultado do último envio se houver
        if st.session_state.email_resultado:
            resultado = st.session_state.email_resultado
            if resultado['sucesso']:
                st.success(resultado['mensagem'])
            else:
                st.error(resultado['mensagem'])
        
        # Mostrar preview do email se o botão foi clicado
        if st.session_state.mostrar_preview_email:
            # Carregar configurações de email
            email_config = load_email_config()
            config_vendedores = email_config.get('_vendedores', {})
            config_global = email_config.get('_global', {})
            cc_global = config_global.get('cc', [])
            
            # Verificar se é "TODOS" os vendedores
            if vendedor_selecionado == "TODOS":
                # Coletar todos os emails dos vendedores cadastrados
                emails_todos_vendedores = []
                vendedores_sem_email = []
                
                for vendedor, config in config_vendedores.items():
                    email_vend = config.get('email', '')
                    if email_vend and '@' in str(email_vend):
                        emails_todos_vendedores.append(email_vend.strip())
                    else:
                        vendedores_sem_email.append(vendedor)
                
                if not emails_todos_vendedores:
                    st.error("❌ Nenhum vendedor possui email configurado. Acesse ⚙️ Configurações.")
                    if st.button("❌ Fechar", key="btn_fechar_erro_todos"):
                        st.session_state.mostrar_preview_email = False
                        st.rerun()
                else:
                    # Remover duplicatas
                    emails_todos_vendedores = list(set(emails_todos_vendedores))
                    email_dest = "; ".join(emails_todos_vendedores)
                    cc_list = []  # Para TODOS, não usa CC específico de vendedor
                    
                    # Alertar sobre vendedores sem email
                    if vendedores_sem_email:
                        st.warning(f"⚠️ Vendedores sem email configurado: {', '.join(vendedores_sem_email)}")
                    
                    # Criar preview do email
                    st.info("📋 Preview do Email - TODOS OS VENDEDORES")
                    
                    # Preparar dataframe para email (limpar emojis da Faixa_Atraso)
                    df_email = df_selecionados.copy()
                    if 'Faixa_Atraso' in df_email.columns:
                        df_email['Faixa_Atraso'] = df_email['Faixa_Atraso'].apply(limpar_faixa_indicador)
                    
                    if len(df_email) == 0:
                        st.warning("⚠️ Nenhum boleto selecionado. Marque pelo menos um boleto na tabela acima.")
                        if st.button("❌ Fechar", key="btn_fechar_vazio_todos"):
                            st.session_state.mostrar_preview_email = False
                            st.rerun()
                    else:
                        # Exibir informações dos destinatários
                        st.write(f"**Vendedores com email ({len(emails_todos_vendedores)}):**")
                        for email in emails_todos_vendedores:
                            st.write(f"  • {email}")
                        
                        # Mostrar CCs globais
                        if cc_global:
                            st.write(f"**CC Global:** {', '.join(cc_global)}")
                        
                        st.write(f"**Total de Boletos:** {len(df_email)} registros selecionados")
                        
                        st.markdown("---")
                        
                        # OPÇÃO DE TIPO DE ENVIO
                        st.subheader("📤 Escolha o Tipo de Envio")
                        
                        tipo_envio = st.radio(
                            "Como deseja enviar?",
                            [
                                "📧 Email Único - Todos recebem o mesmo email (todos no campo 'Para')",
                                "📨 Envio em Massa - Cada vendedor recebe email individual com seus boletos"
                            ],
                            key="tipo_envio_todos"
                        )
                        
                        st.markdown("---")
                        
                        if "Email Único" in tipo_envio:
                            # === ENVIO ÚNICO (comportamento anterior) ===
                            st.info("📋 Preview do Email Único")
                            
                            corpo_email = criar_corpo_email(
                                "TODOS OS VENDEDORES",
                                df_email,
                                datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                            )
                            
                            st.components.v1.html(corpo_email, height=400, scrolling=True)
                            
                            with st.form(key="form_envio_email_todos_unico"):
                                metodo_envio = st.radio(
                                    "Método de Envio",
                                    ["📮 SMTP", "📧 Outlook"],
                                    horizontal=True
                                )
                                
                                col_confirm, col_cancel = st.columns(2)
                                with col_confirm:
                                    enviar_btn = st.form_submit_button("✅ Enviar Email Único", use_container_width=True)
                                with col_cancel:
                                    cancelar_btn = st.form_submit_button("❌ Cancelar", use_container_width=True)
                            
                            if enviar_btn:
                                sucesso = False
                                mensagem = ""
                                email_dest = "; ".join(emails_todos_vendedores)
                                
                                with st.spinner("Enviando email único para todos os vendedores..."):
                                    if metodo_envio == "📧 Outlook":
                                        try:
                                            sucesso, mensagem = enviar_email_outlook(
                                                email_dest,
                                                "Relatório de Boletos em Atraso",
                                                corpo_email,
                                                cc_list=None,
                                                cc_global=cc_global if cc_global else None
                                            )
                                        except Exception as e:
                                            sucesso = False
                                            mensagem = f"❌ Erro inesperado ao enviar via Outlook: {str(e)}"
                                    else:
                                        smtp_config = load_smtp_config()
                                        if not smtp_config or not smtp_config.get('usuario'):
                                            sucesso = False
                                            mensagem = "❌ SMTP não configurado."
                                        else:
                                            # Pré-checagem de autenticação
                                            valido, msg_auth = verificar_smtp_auth(
                                                servidor_smtp=smtp_config.get('servidor'),
                                                porta=smtp_config.get('porta', 587),
                                                usuario=smtp_config.get('usuario'),
                                                senha=smtp_config.get('senha'),
                                                usar_tls=smtp_config.get('usar_tls', True)
                                            )
                                            if not valido:
                                                sucesso = False
                                                mensagem = f"❌ {msg_auth}\n\n🔑 Atualize a senha no topo da página."
                                                st.session_state.smtp_senha_expirada = True
                                            else:
                                                try:
                                                    sucesso, mensagem = enviar_email_smtp(
                                                        email_dest,
                                                        "Relatório de Boletos em Atraso",
                                                        corpo_email,
                                                        cc_list=None,
                                                        cc_global=cc_global if cc_global else None,
                                                        servidor_smtp=smtp_config.get('servidor'),
                                                        porta=smtp_config.get('porta', 587),
                                                        usuario=smtp_config.get('usuario'),
                                                        senha=smtp_config.get('senha'),
                                                        usar_tls=smtp_config.get('usar_tls', True)
                                                    )
                                                except Exception as e:
                                                    sucesso = False
                                                    mensagem = f"❌ Erro ao enviar via SMTP: {str(e)}"
                                
                                st.session_state.email_resultado = {'sucesso': sucesso, 'mensagem': mensagem}
                                st.session_state.mostrar_preview_email = False
                                st.rerun()
                            
                            if cancelar_btn:
                                st.session_state.mostrar_preview_email = False
                                st.session_state.email_resultado = None
                                st.rerun()
                        
                        else:
                            # === ENVIO EM MASSA (novo) ===
                            st.info("📋 Envio em Massa - Cada vendedor receberá apenas seus boletos")
                            
                            # Agrupar boletos por vendedor
                            vendedores_com_boletos = df_email.groupby('Nome Vendedor').size().to_dict() if 'Nome Vendedor' in df_email.columns else {}
                            
                            # Mostrar resumo
                            st.write("**Resumo do Envio em Massa:**")
                            emails_a_enviar = []
                            
                            for vendedor, config in config_vendedores.items():
                                email_vend = config.get('email', '')
                                if email_vend and '@' in str(email_vend):
                                    qtd_boletos = vendedores_com_boletos.get(vendedor, 0)
                                    if qtd_boletos > 0:
                                        emails_a_enviar.append({
                                            'vendedor': vendedor,
                                            'email': email_vend,
                                            'cc': config.get('cc', []),
                                            'qtd_boletos': qtd_boletos
                                        })
                                        st.write(f"  ✅ **{vendedor}** → {email_vend} ({qtd_boletos} boletos)")
                                    else:
                                        st.write(f"  ⚪ **{vendedor}** → Sem boletos selecionados")
                            
                            if not emails_a_enviar:
                                st.warning("⚠️ Nenhum vendedor com boletos selecionados possui email configurado.")
                            else:
                                st.write(f"\n**Total:** {len(emails_a_enviar)} emails serão enviados")
                                
                                with st.form(key="form_envio_email_massa"):
                                    metodo_envio = st.radio(
                                        "Método de Envio",
                                        ["📮 SMTP", "📧 Outlook"],
                                        horizontal=True
                                    )
                                    
                                    confirmar_massa = st.checkbox(
                                        f"⚠️ Confirmo o envio de **{len(emails_a_enviar)} emails** para os vendedores listados acima",
                                        value=False
                                    )
                                    
                                    col_confirm, col_cancel = st.columns(2)
                                    with col_confirm:
                                        enviar_massa_btn = st.form_submit_button(f"✅ Enviar {len(emails_a_enviar)} Emails", use_container_width=True)
                                    with col_cancel:
                                        cancelar_massa_btn = st.form_submit_button("❌ Cancelar", use_container_width=True)
                                
                                if enviar_massa_btn:
                                    if not confirmar_massa:
                                        st.error("❌ Marque a caixa de confirmação antes de enviar em massa.")
                                    else:
                                        # Pré-checagem SMTP antes do envio em massa
                                        smtp_ok = True
                                        if metodo_envio != "📧 Outlook":
                                            smtp_config = load_smtp_config()
                                            if not smtp_config or not smtp_config.get('usuario'):
                                                st.session_state.email_resultado = {'sucesso': False, 'mensagem': '❌ SMTP não configurado.'}
                                                st.session_state.mostrar_preview_email = False
                                                st.rerun()
                                            valido, msg_auth = verificar_smtp_auth(
                                                servidor_smtp=smtp_config.get('servidor'),
                                                porta=smtp_config.get('porta', 587),
                                                usuario=smtp_config.get('usuario'),
                                                senha=smtp_config.get('senha'),
                                                usar_tls=smtp_config.get('usar_tls', True)
                                            )
                                            if not valido:
                                                st.session_state.smtp_senha_expirada = True
                                                st.session_state.email_resultado = {'sucesso': False, 'mensagem': f'❌ {msg_auth}\n\n🔑 Atualize a senha no topo da página.'}
                                                st.session_state.mostrar_preview_email = False
                                                st.rerun()

                                        # Enviar para cada vendedor
                                        resultados = []
                                        progress_bar = st.progress(0)
                                        status_text = st.empty()
                                        
                                        for idx, info in enumerate(emails_a_enviar):
                                            vendedor = info['vendedor']
                                            email_vend = info['email']
                                            cc_vend = info['cc']
                                            
                                            status_text.text(f"Enviando para {vendedor}... ({idx+1}/{len(emails_a_enviar)})")
                                            
                                            # Filtrar boletos deste vendedor
                                            df_vendedor = df_email[df_email['Nome Vendedor'] == vendedor].copy()
                                            
                                            # Criar corpo do email para este vendedor
                                            corpo_vendedor = criar_corpo_email(
                                                vendedor,
                                                df_vendedor,
                                                datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                                            )
                                            
                                            # Enviar
                                            try:
                                                if metodo_envio == "📧 Outlook":
                                                    sucesso, msg = enviar_email_outlook(
                                                        email_vend,
                                                        "Relatório de Boletos em Atraso",
                                                        corpo_vendedor,
                                                        cc_list=cc_vend if cc_vend else None,
                                                        cc_global=cc_global if cc_global else None
                                                    )
                                                else:
                                                    sucesso, msg = enviar_email_smtp(
                                                        email_vend,
                                                        "Relatório de Boletos em Atraso",
                                                        corpo_vendedor,
                                                        cc_list=cc_vend if cc_vend else None,
                                                        cc_global=cc_global if cc_global else None,
                                                        servidor_smtp=smtp_config.get('servidor'),
                                                        porta=smtp_config.get('porta', 587),
                                                        usuario=smtp_config.get('usuario'),
                                                        senha=smtp_config.get('senha'),
                                                        usar_tls=smtp_config.get('usar_tls', True)
                                                    )
                                                
                                                resultados.append({'vendedor': vendedor, 'sucesso': sucesso, 'msg': msg})
                                            except Exception as e:
                                                resultados.append({'vendedor': vendedor, 'sucesso': False, 'msg': str(e)})
                                            
                                            progress_bar.progress((idx + 1) / len(emails_a_enviar))
                                        
                                        status_text.empty()
                                        progress_bar.empty()
                                        
                                        # Resumo dos resultados
                                        enviados_ok = sum(1 for r in resultados if r['sucesso'])
                                        enviados_erro = len(resultados) - enviados_ok
                                        
                                        mensagem_resultado = f"📊 **Resultado do Envio em Massa:**\n\n"
                                        mensagem_resultado += f"✅ Enviados com sucesso: {enviados_ok}\n"
                                        mensagem_resultado += f"❌ Com erro: {enviados_erro}\n\n"
                                        
                                        for r in resultados:
                                            if r['sucesso']:
                                                mensagem_resultado += f"✅ {r['vendedor']}\n"
                                            else:
                                                mensagem_resultado += f"❌ {r['vendedor']}: {r['msg'][:50]}...\n"
                                        
                                        st.session_state.email_resultado = {
                                            'sucesso': enviados_ok > 0,
                                            'mensagem': mensagem_resultado
                                        }
                                        st.session_state.mostrar_preview_email = False
                                        st.rerun()
                                
                                if cancelar_massa_btn:
                                    st.session_state.mostrar_preview_email = False
                                    st.session_state.email_resultado = None
                                    st.rerun()
            
            elif vendedor_selecionado not in config_vendedores:
                st.error(f"❌ Email não configurado para {vendedor_selecionado}. Acesse ⚙️ Configurações.")
                if st.button("❌ Fechar", key="btn_fechar_erro"):
                    st.session_state.mostrar_preview_email = False
                    st.rerun()
            else:
                config_vendedor = config_vendedores[vendedor_selecionado]
                email_dest = config_vendedor.get('email')
                cc_list = config_vendedor.get('cc', [])
                
                # Validação de email
                if not email_dest or '@' not in str(email_dest):
                    st.error(f"❌ Email inválido para {vendedor_selecionado}: {email_dest}")
                    st.info("💡 Configure um email válido em ⚙️ Configurações")
                    if st.button("❌ Fechar", key="btn_fechar_invalido"):
                        st.session_state.mostrar_preview_email = False
                        st.rerun()
                else:
                    # Criar preview do email
                    st.info("📋 Preview do Email")
                    
                    # Preparar dataframe para email - usar df_selecionados (apenas boletos marcados)
                    df_email = df_selecionados.copy()
                    # Limpar emojis da Faixa_Atraso para o email
                    if 'Faixa_Atraso' in df_email.columns:
                        df_email['Faixa_Atraso'] = df_email['Faixa_Atraso'].apply(limpar_faixa_indicador)
                    
                    # Verificar se há boletos selecionados
                    if len(df_email) == 0:
                        st.warning("⚠️ Nenhum boleto selecionado. Marque pelo menos um boleto na tabela acima.")
                        if st.button("❌ Fechar", key="btn_fechar_vazio"):
                            st.session_state.mostrar_preview_email = False
                            st.rerun()
                    else:
                        # Criar corpo do email
                        corpo_email = criar_corpo_email(
                            vendedor_selecionado,
                            df_email,
                            datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                        )
                        
                        # Exibir preview com validação
                        st.write(f"**Para:** {email_dest}")
                        
                        # Mostrar CCs (específicos + globais)
                        todos_ccs = []
                        if cc_list:
                            todos_ccs.extend(cc_list)
                        if cc_global:
                            todos_ccs.extend(cc_global)
                        todos_ccs = list(set(todos_ccs))  # remover duplicatas
                        
                        if todos_ccs:
                            st.write(f"**CC:** {', '.join(todos_ccs)}")
                            st.caption("💡 Nota: Globais + Específicos do vendedor")
                        
                        st.write("**Assunto:** Relatório de Boletos em Atraso")
                        st.write(f"**Boletos:** {len(df_email)} registros selecionados")
                        
                        # Mostrar HTML em iframe
                        st.components.v1.html(corpo_email, height=600, scrolling=True)
                        
                        st.markdown("---")
                    
                        # OPÇÃO DE ENVIO - usar form para evitar reset
                        with st.form(key="form_envio_email"):
                            metodo_envio = st.radio(
                                "Método de Envio",
                                ["📮 SMTP", "📧 Outlook"],
                                horizontal=True
                            )
                            
                            # Botões de ação
                            col_confirm, col_cancel = st.columns(2)
                            
                            with col_confirm:
                                enviar_btn = st.form_submit_button("✅ Enviar Email", use_container_width=True)
                            
                            with col_cancel:
                                cancelar_btn = st.form_submit_button("❌ Cancelar", use_container_width=True)
                        
                        # Processar ações
                        if enviar_btn:
                            sucesso = False
                            mensagem = ""
                            
                            with st.spinner("Enviando email..."):
                                if metodo_envio == "📧 Outlook":
                                    try:
                                        sucesso, mensagem = enviar_email_outlook(
                                            email_dest,
                                            "Relatório de Boletos em Atraso",
                                            corpo_email,
                                            cc_list=cc_list if cc_list else None,
                                            cc_global=cc_global if cc_global else None
                                        )
                                    except Exception as e:
                                        sucesso = False
                                        mensagem = f"❌ Erro inesperado ao enviar via Outlook: {str(e)}"
                                else:
                                    smtp_config = load_smtp_config()
                                    if not smtp_config or not smtp_config.get('usuario'):
                                        sucesso = False
                                        mensagem = "❌ SMTP não configurado.\n\nAcesse ⚙️ Configurações → SMTP para configurar."
                                    else:
                                        # Pré-checagem de autenticação
                                        valido, msg_auth = verificar_smtp_auth(
                                            servidor_smtp=smtp_config.get('servidor'),
                                            porta=smtp_config.get('porta', 587),
                                            usuario=smtp_config.get('usuario'),
                                            senha=smtp_config.get('senha'),
                                            usar_tls=smtp_config.get('usar_tls', True)
                                        )
                                        if not valido:
                                            sucesso = False
                                            mensagem = f"❌ {msg_auth}\n\n🔑 Atualize a senha no topo da página."
                                            st.session_state.smtp_senha_expirada = True
                                        else:
                                            try:
                                                sucesso, mensagem = enviar_email_smtp(
                                                    email_dest,
                                                    "Relatório de Boletos em Atraso",
                                                    corpo_email,
                                                    cc_list=cc_list if cc_list else None,
                                                    cc_global=cc_global if cc_global else None,
                                                    servidor_smtp=smtp_config.get('servidor'),
                                                    porta=smtp_config.get('porta', 587),
                                                    usuario=smtp_config.get('usuario'),
                                                    senha=smtp_config.get('senha'),
                                                    usar_tls=smtp_config.get('usar_tls', True)
                                                )
                                            except Exception as e:
                                                sucesso = False
                                                mensagem = f"❌ Erro ao enviar via SMTP: {str(e)}"
                            
                            st.session_state.email_resultado = {
                                'sucesso': sucesso,
                                'mensagem': mensagem
                            }
                            st.session_state.mostrar_preview_email = False
                            st.rerun()
                        
                        if cancelar_btn:
                            st.session_state.mostrar_preview_email = False
                            st.session_state.email_resultado = None
                            st.rerun()

    
    # TAB 4: Por Cliente
    with tab4:
        st.subheader("Análise por Cliente")
        
        resumo_cliente = df_filtrado.groupby('Cliente').agg({
            'Título': 'count',
            'Saldo Atual': 'sum',
            'Dias_Atraso': 'max',
            'Nome Vendedor': 'first'
        }).rename(columns={
            'Título': 'Qtd. Boletos',
            'Saldo Atual': 'Valor Total',
            'Dias_Atraso': 'Maior Atraso (dias)',
            'Nome Vendedor': 'Vendedor'
        }).sort_values('Valor Total', ascending=False)
        
        resumo_cliente['Valor Total'] = resumo_cliente['Valor Total'].apply(formatar_moeda_br)
        resumo_cliente['Maior Atraso (dias)'] = resumo_cliente['Maior Atraso (dias)'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")
        
        st.dataframe(resumo_cliente, use_container_width=True)
    
    # Assinatura discreta no sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="text-align: center; font-size: 10px; color: #888; padding: 10px 0;">
            <p style="margin: 0;">Desenvolvido por</p>
            <p style="margin: 2px 0; font-weight: 500;">Christian Krauss Rumayor</p>
            <p style="margin: 0; font-size: 9px;">
                <a href="mailto:crumayor@alliedbrasil.com.br" style="color: #666;">crumayor@alliedbrasil.com.br</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
