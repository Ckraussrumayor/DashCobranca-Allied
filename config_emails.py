import json
import streamlit as st
from pathlib import Path
from datetime import datetime
import pandas as pd

# Arquivos de configuração
CONFIG_FILE = Path(__file__).parent / "email_config.json"
CONFIG_SMTP_FILE = Path(__file__).parent / "email_config_smtp.json"
AUTH_CONFIG_FILE = Path(__file__).parent / "auth_config.json"

def get_base_path():
    """Retorna o diretório base do aplicativo"""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    else:
        return Path(__file__).parent

BASE_DIR = get_base_path()

def find_aging_file():
    """Procura por arquivos .xlsb no diretório base"""
    xlsb_files = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    if len(xlsb_files) == 1:
        return xlsb_files[0]
    return None

@st.cache_data(ttl=3600, show_spinner="Carregando vendedores...")
def load_vendedores_do_dashboard():
    """Carrega lista de vendedores únicos do arquivo de dados - OTIMIZADO com cache"""
    try:
        aging_file = find_aging_file()
        if aging_file is None:
            return []
        
        # Ler apenas primeiras 10 linhas para detectar header
        df_sample = pd.read_excel(str(aging_file), sheet_name='BaseDados', header=None, 
                                   engine='pyxlsb', nrows=10)
        
        # Procurar headers
        header_row = 3  # Valor padrão
        for idx, row in df_sample.iterrows():
            text_cells = sum(1 for val in row if isinstance(val, str) and len(str(val).strip()) > 0)
            if text_cells >= 5:
                header_row = idx
                break
        
        # Ler arquivo com header correto - única leitura
        # Ler apenas as colunas necessárias para otimizar
        df_base = pd.read_excel(str(aging_file), sheet_name='BaseDados', header=header_row, engine='pyxlsb')
        df_base.columns = df_base.columns.str.strip()
        
        # Filtrar por Diretor = B2B
        if 'Diretor' in df_base.columns:
            df_base = df_base[df_base['Diretor'] == 'B2B']
        
        # Filtrar por Portador Ajustado
        portadores_permitidos = ['Boleto', 'Disponível', 'TED', 'Serviço']
        if 'Portador Ajustado' in df_base.columns:
            df_base = df_base[df_base['Portador Ajustado'].isin(portadores_permitidos)]
        
        # Obter vendedores únicos
        if 'Nome Vendedor' in df_base.columns:
            vendedores = sorted(df_base['Nome Vendedor'].dropna().unique().tolist())
            return vendedores
        
        return []
    except Exception as e:
        return []

def load_email_config():
    """Carrega configurações de email do arquivo"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'_global': {'cc': []}, '_vendedores': {}}
    return {'_global': {'cc': []}, '_vendedores': {}}

def save_email_config(config):
    """Salva configurações de email no arquivo"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configurações: {e}")
        return False

def load_smtp_config():
    """Carrega configurações SMTP"""
    if CONFIG_SMTP_FILE.exists():
        try:
            with open(CONFIG_SMTP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_smtp_config(config):
    """Salva configurações SMTP"""
    try:
        with open(CONFIG_SMTP_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar SMTP: {e}")
        return False

def load_auth_config() -> dict:
    """Carrega configuração de autenticação 2FA do arquivo local."""
    if AUTH_CONFIG_FILE.exists():
        try:
            with open(AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_auth_config(config: dict) -> bool:
    """Salva configuração de autenticação 2FA no arquivo local."""
    try:
        with open(AUTH_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar configuração 2FA: {e}")
        return False

def render_configuracoes():
    """Renderiza página de configurações"""
    st.markdown('<h1 style="color: #0066cc; text-align: center;">⚙️ Configurações - Emails</h1>', unsafe_allow_html=True)
    
    # Tabs para diferentes seções
    tab1, tab2, tab3, tab4 = st.tabs(["📧 Vendedores", "📨 SMTP (Alternativo)", "ℹ️ Ajuda", "🔐 Autenticação 2FA"])
    
    # ===== TAB 1: VENDEDORES =====
    with tab1:
        st.markdown("---")
        
        # Carregar configurações existentes
        config = load_email_config()
        config_global = config.get('_global', {'cc': []})
        config_vendedores = config.get('_vendedores', {})
        
        # SEÇÃO GLOBAL
        st.subheader("🌐 Configurações Globais")
        st.write("Estes emails de cópia serão adicionados a **TODOS** os emails enviados:")
        
        emails_cc_global = st.text_area(
            "Emails em Cópia Global (CC) - Um por linha",
            value="\n".join(config_global.get('cc', [])),
            placeholder="gerente@example.com\ndiretoria@example.com",
            key="cc_global",
            height=100
        )
        
        if st.button("💾 Salvar Configurações Globais", use_container_width=True):
            cc_list = [e.strip() for e in emails_cc_global.split('\n') if e.strip()]
            config['_global'] = {'cc': cc_list}
            
            if save_email_config(config):
                st.success("✅ Configurações globais salvas com sucesso!")
                try:
                    from backup_utils import enviar_backup_configs
                    enviar_backup_configs(str(Path(__file__).parent))
                except Exception:
                    pass
                st.rerun()
        
        st.markdown("---")
        
        # SEÇÃO DE VENDEDORES
        st.subheader("📧 Cadastro de Emails por Vendedor")
        
        # Carregar vendedores do dashboard (agora com cache)
        vendedores_dashboard = load_vendedores_do_dashboard()
        
        if not vendedores_dashboard:
            st.warning("⚠️ Nenhum vendedor encontrado no dashboard. Verifique o arquivo de dados.")
            return
        
        # Inicializar session_state para vendedor selecionado se não existir
        if 'vendedor_selecionado_idx' not in st.session_state:
            st.session_state.vendedor_selecionado_idx = 0
        
        # Selectbox para escolher vendedor
        vendedor_selecionado = st.selectbox(
            "Selecione um Vendedor",
            options=vendedores_dashboard,
            index=st.session_state.vendedor_selecionado_idx,
            key="vendedor_select_box"
        )
        
        # Atualizar índice no session_state
        if vendedor_selecionado in vendedores_dashboard:
            st.session_state.vendedor_selecionado_idx = vendedores_dashboard.index(vendedor_selecionado)
        
        # Duas colunas
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📝 Configuração do Vendedor")
            
            if vendedor_selecionado:
                # Dados atuais do vendedor
                vendedor_data = config_vendedores.get(vendedor_selecionado, {})
                
                # Usar form para evitar recarregamentos a cada interação
                with st.form(key=f"form_vendedor"):
                    # Email do vendedor
                    email_vendedor = st.text_input(
                        "Email do Vendedor",
                        value=vendedor_data.get('email', ''),
                        placeholder="vendedor@example.com"
                    )
                    
                    # Emails em CC específicos do vendedor
                    emails_cc_vendedor = st.text_area(
                        f"Emails em Cópia (CC) - Específicos deste vendedor - Um por linha",
                        value="\n".join(vendedor_data.get('cc', [])),
                        placeholder="gerente@example.com\ndiretoria@example.com",
                        height=100
                    )
                    
                    st.info("💡 Além destes emails, também serão adicionados os emails da Configuração Global.")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        salvar_btn = st.form_submit_button("💾 Salvar", use_container_width=True)
                    
                    with col_btn2:
                        deletar_btn = st.form_submit_button("🗑️ Deletar", use_container_width=True)
                
                # Processar ações fora do form
                if salvar_btn:
                    if not email_vendedor:
                        st.error("❌ Email do vendedor é obrigatório!")
                    else:
                        # Processar emails em CC
                        cc_list = [e.strip() for e in emails_cc_vendedor.split('\n') if e.strip()]
                        
                        config_vendedores[vendedor_selecionado] = {
                            'email': email_vendedor.strip(),
                            'cc': cc_list,
                            'atualizado_em': datetime.now().isoformat()
                        }
                        
                        config['_vendedores'] = config_vendedores
                        
                        if save_email_config(config):
                            st.success(f"✅ Configuração de {vendedor_selecionado} salva com sucesso!")
                            try:
                                from backup_utils import enviar_backup_configs
                                enviar_backup_configs(str(Path(__file__).parent))
                            except Exception:
                                pass
                            st.rerun()
                
                if deletar_btn:
                    if vendedor_selecionado in config_vendedores:
                        del config_vendedores[vendedor_selecionado]
                        config['_vendedores'] = config_vendedores
                        if save_email_config(config):
                            st.success(f"✅ Configuração de {vendedor_selecionado} deletada!")
                            try:
                                from backup_utils import enviar_backup_configs
                                enviar_backup_configs(str(Path(__file__).parent))
                            except Exception:
                                pass
                            st.rerun()
        
        with col2:
            st.subheader("📋 Vendedores Cadastrados")
            
            if config_vendedores:
                for vendedor, dados in sorted(config_vendedores.items()):
                    status_icon = "✅" if dados.get('email') else "⚠️"
                    with st.expander(f"{status_icon} {vendedor}"):
                        st.write(f"**Email:** {dados.get('email', '❌ Não cadastrado')}")
                        cc_list = dados.get('cc', [])
                        if cc_list:
                            st.write(f"**CC Específico ({len(cc_list)}):**")
                            for email in cc_list:
                                st.write(f"  • {email}")
                        else:
                            st.write("**CC Específico:** Nenhum")
                        
                        atualizado = dados.get('atualizado_em', 'N/A')
                        if atualizado != 'N/A':
                            dt = datetime.fromisoformat(atualizado)
                            st.write(f"**Atualizado em:** {dt.strftime('%d/%m/%Y %H:%M:%S')}")
            else:
                st.info("📌 Nenhum vendedor configurado ainda. Configure um vendedor à esquerda!")
    
    # ===== TAB 2: SMTP =====
    with tab2:
        st.markdown("---")
        st.subheader("📨 Configuração SMTP (Alternativa ao Outlook)")
        st.info("""
        Se o Outlook não estiver funcionando, você pode usar SMTP como alternativa.
        
        **Opções comuns:**
        - **Gmail**: servidor smtp.gmail.com:587 (use [Senha de App](https://myaccount.google.com/apppasswords))
        - **Outlook.com**: servidor smtp-mail.outlook.com:587
        - **Corporativo**: Solicite ao seu departamento de TI
        """)
        
        smtp_config = load_smtp_config()
        
        col1, col2 = st.columns(2)
        
        with col1:
            servidor = st.text_input(
                "Servidor SMTP",
                value=smtp_config.get('servidor', 'smtp.gmail.com'),
                placeholder="smtp.gmail.com"
            )
            porta = st.number_input(
                "Porta SMTP",
                value=smtp_config.get('porta', 587),
                min_value=1,
                max_value=65535
            )
        
        with col2:
            usuario = st.text_input(
                "Seu Email (usuário SMTP)",
                value=smtp_config.get('usuario', ''),
                placeholder="seu_email@gmail.com"
            )
            senha = st.text_input(
                "Senha ou App Password",
                value=smtp_config.get('senha', ''),
                type="password",
                placeholder="••••••••"
            )
        
        usar_tls = st.checkbox(
            "Usar TLS (geralmente sim)",
            value=smtp_config.get('usar_tls', True)
        )
        
        st.markdown("---")
        st.subheader("📥 Configuração IMAP (para backup por email)")
        st.caption("Usado para recuperar backups de dados e configurações. Auto-detectado se deixado em branco.")
        
        col_imap1, col_imap2 = st.columns(2)
        with col_imap1:
            servidor_imap = st.text_input(
                "Servidor IMAP",
                value=smtp_config.get('servidor_imap', ''),
                placeholder="imap.gmail.com (auto-detectado)",
                help="Deixe vazio para auto-detectar a partir do servidor SMTP"
            )
        with col_imap2:
            porta_imap = st.number_input(
                "Porta IMAP (SSL)",
                value=smtp_config.get('porta_imap', 993),
                min_value=1,
                max_value=65535
            )
        
        st.markdown("---")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            if st.button("💾 Salvar", use_container_width=True):
                if servidor and usuario and senha:
                    novo_config = {
                        'servidor': servidor,
                        'porta': int(porta),
                        'usuario': usuario,
                        'senha': senha,
                        'usar_tls': usar_tls,
                        'servidor_imap': servidor_imap.strip(),
                        'porta_imap': int(porta_imap)
                    }
                    if save_smtp_config(novo_config):
                        st.success("✅ Configuração SMTP/IMAP salva!")
                        # Backup automático das configurações
                        try:
                            from backup_utils import enviar_backup_configs
                            enviar_backup_configs(str(Path(__file__).parent))
                        except Exception:
                            pass
                else:
                    st.error("❌ Preencha todos os campos!")
        
        with col_btn2:
            if st.button("🧪 Testar", use_container_width=True):
                if not servidor or not usuario or not senha:
                    st.error("❌ Preencha todos os campos primeiro!")
                else:
                    with st.spinner("Testando conexão..."):
                        try:
                            import smtplib
                            with smtplib.SMTP(servidor, int(porta), timeout=10) as server:
                                if usar_tls:
                                    server.starttls()
                                server.login(usuario, senha)
                            st.success("✅ Conexão SMTP bem-sucedida!")
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
        
        with col_btn3:
            if st.button("🗑️ Limpar", use_container_width=True):
                if CONFIG_SMTP_FILE.exists():
                    CONFIG_SMTP_FILE.unlink()
                    st.success("✅ Configuração SMTP removida!")
                    st.rerun()
    
    # ===== TAB 3: AJUDA =====
    with tab3:
        st.markdown("---")
        st.subheader("❓ Como Usar")
        
        st.markdown("""
        ### 📧 Opção 1: Outlook (Integrado)
        - **Vantagem**: Usa sua conta do Outlook já configurada
        - **Desvantagem**: Requer Outlook instalado
        - **Como usar**: Configure os emails dos vendedores na aba "Vendedores"
        
        ### 📨 Opção 2: SMTP (Alternativo)
        - **Vantagem**: Funciona com qualquer email (Gmail, Outlook.com, corporativo)
        - **Desvantagem**: Requer configuração adicional
        - **Como usar**: Obtenha credenciais e configure na aba "SMTP (Alternativo)"
        
        ### 🔑 Como Gerar Senha de App no Gmail
        1. Acesse https://myaccount.google.com/apppasswords
        2. Selecione App: Mail, Device: Windows/Mac
        3. Copie a senha gerada
        4. Cole na configuração SMTP
        
        ### ⚠️ Problemas Comuns
        - **Email não sai**: Verifique se o servidor SMTP está acessível
        - **Erro de autenticação**: Confirme usuário/senha
        - **Outlook não encontrado**: Instale Outlook ou use SMTP
        """)

    # ===== TAB 4: AUTENTICAÇÃO 2FA =====
    with tab4:
        st.markdown("---")
        st.subheader("🔐 Autenticação em Dois Fatores (2FA)")
        st.info("""
        Após o login com usuário e senha, um código de 6 dígitos será enviado
        para o email configurado. O código é válido por **5 minutos**.

        **Pré-requisito:** Configure o SMTP na aba “SMTP (Alternativo)” antes de habilitar.
        """)

        auth_config = load_auth_config()
        dois_fatores = auth_config.get('two_factor', {})

        habilitado = st.toggle(
            "Habilitar Autenticação 2FA",
            value=dois_fatores.get('enabled', False),
            key="toggle_2fa"
        )

        email_2fa = st.text_input(
            "Email que receberá o código de verificação",
            value=dois_fatores.get('email', ''),
            placeholder="admin@suaempresa.com.br",
            help="Este email receberá o código toda vez que alguém fizer login"
        )

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("💾 Salvar", use_container_width=True, key="btn_salvar_2fa"):
                if habilitado and not email_2fa.strip():
                    st.error("❌ Informe um email para receber o código 2FA.")
                elif habilitado and '@' not in email_2fa:
                    st.error("❌ Email inválido.")
                else:
                    novo_auth = {
                        'two_factor': {
                            'enabled': habilitado,
                            'email': email_2fa.strip()
                        }
                    }
                    if save_auth_config(novo_auth):
                        if habilitado:
                            st.success(f"✅ 2FA habilitado! Código será enviado para: {email_2fa.strip()}")
                        else:
                            st.success("✅ 2FA desabilitado.")
                        try:
                            from backup_utils import enviar_backup_configs
                            enviar_backup_configs(str(Path(__file__).parent))
                        except Exception:
                            pass

        with col_btn2:
            if st.button("🧪 Testar Envio", use_container_width=True, key="btn_testar_2fa"):
                if not email_2fa.strip() or '@' not in email_2fa:
                    st.error("❌ Informe um email válido antes de testar.")
                else:
                    with st.spinner("Enviando código de teste..."):
                        try:
                            smtp_cfg = load_smtp_config()
                            if not smtp_cfg or not smtp_cfg.get('usuario'):
                                st.error("❌ SMTP não configurado. Configure na aba ‘SMTP (Alternativo)’.")
                            else:
                                from email_utils import enviar_email_smtp
                                import random as _random, string as _string
                                token_teste = ''.join(_random.choices(_string.digits, k=6))
                                corpo_teste = f"""
                                <html><body style="font-family:Arial,sans-serif; color:#333; margin:30px;">
                                <div style="background:#0066cc; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
                                    <h2 style="margin:0;">🔐 Dashboard Allied — Teste de 2FA</h2>
                                </div>
                                <p>Código de teste:</p>
                                <div style="background:#f5f5f5; border-left:4px solid #ff6b35; padding:20px; text-align:center; margin:20px 0; border-radius:4px;">
                                    <span style="letter-spacing:12px; color:#ff6b35; font-size:2.5rem; font-weight:bold;">{token_teste}</span>
                                </div>
                                <p style="color:#999; font-size:12px;">Este é um email de teste do sistema 2FA.</p>
                                </body></html>
                                """
                                sucesso, msg = enviar_email_smtp(
                                    email_2fa.strip(),
                                    "🔐 [TESTE] Código de verificação - Dashboard Allied",
                                    corpo_teste,
                                    servidor_smtp=smtp_cfg.get('servidor'),
                                    porta=smtp_cfg.get('porta', 587),
                                    usuario=smtp_cfg.get('usuario'),
                                    senha=smtp_cfg.get('senha'),
                                    usar_tls=smtp_cfg.get('usar_tls', True)
                                )
                                if sucesso:
                                    st.success(f"✅ Email de teste enviado! Código: **{token_teste}**")
                                else:
                                    st.error(f"❌ {msg}")
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")

        st.markdown("---")
        if dois_fatores.get('enabled'):
            st.success(f"✅ 2FA **habilitado** | Código enviado para: **{dois_fatores.get('email', '')}**")
        else:
            st.warning("⚠️ 2FA **desabilitado** — qualquer pessoa com usuário/senha terá acesso direto.")

        st.markdown("---")
        st.subheader("☁️ Streamlit Cloud")
        st.markdown("""
        No **Streamlit Cloud (versão free)**, adicione em **Settings → Secrets**:
        ```toml
        [two_factor]
        enabled = true
        email = "admin@suaempresa.com.br"
        ```
        O arquivo `auth_config.json` local tem prioridade sobre os secrets.
        """)


