import streamlit as st
import traceback

# Configuração da página PRIMEIRO (permite exibir erros na tela do Cloud)
st.set_page_config(
    page_title="Dashboard Allied - Menu Principal",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    import sys
    import os
    import platform
    from pathlib import Path
    import locale
    import shutil
    import hashlib
    import random
    import string
    from datetime import datetime, timedelta

    from backup_utils import (
        enviar_backup_dados, enviar_backup_configs,
        restaurar_backup_dados, restaurar_backup_configs,
        verificar_backup_disponivel
    )
except Exception as _import_error:
    st.error(f"Erro ao importar módulos: {_import_error}")
    st.code(traceback.format_exc())
    st.stop()

# Função para obter o diretório base do aplicativo
def get_base_path():
    """
    Retorna o diretório base onde o aplicativo está sendo executado.
    Funciona para: script Python, executável PyInstaller e Python embarcado.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller: usa o diretório do executável, não o temporário
        return Path(sys.executable).parent
    else:
        # Script Python ou Python embarcado: usa o diretório do script
        return Path(__file__).parent.resolve()

BASE_DIR = get_base_path()
sys.path.insert(0, str(BASE_DIR))

# Configurar locale para português brasileiro
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
    except:
        pass

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #0066cc;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    .main .block-container {
        background-color: #f5faff;
        padding: 2rem;
        border-radius: 10px;
    }
    
    [data-testid="stSidebar"] {
        background-color: #fff8f0;
        border-right: 3px solid #ff8c42;
        box-shadow: 2px 0 5px rgba(255, 140, 66, 0.2);
    }
    
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #ff8c42;
    }
    
    .nav-button {
        display: block;
        width: 100%;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
        border: none;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .nav-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# Inicializar session state para página atual
if 'page' not in st.session_state:
    st.session_state.page = 'menu'

# ── AUTENTICAÇÃO ──────────────────────────────────────────────────────────────
def _verificar_credenciais(usuario: str, senha: str) -> bool:
    """Compara usuário e senha com os valores configurados nos secrets."""
    try:
        usuario_correto = st.secrets["credentials"]["username"]
        senha_correta   = st.secrets["credentials"]["password"]
    except KeyError:
        usuario_correto = "admin"
        senha_correta   = "123456"
    return usuario.strip() == usuario_correto and senha == senha_correta

def _carregar_config_2fa() -> dict:
    """Carrega config de 2FA: primeiro auth_config.json local, depois secrets."""
    import json
    auth_config_file = BASE_DIR / "auth_config.json"
    if auth_config_file.exists():
        try:
            with open(auth_config_file, 'r', encoding='utf-8') as f:
                return json.load(f).get('two_factor', {})
        except Exception:
            pass
    try:
        return {
            'enabled': st.secrets["two_factor"]["enabled"],
            'email':   st.secrets["two_factor"].get("email", ""),
        }
    except Exception:
        return {'enabled': False, 'email': ''}

def _gerar_token() -> str:
    return ''.join(random.choices(string.digits, k=6))

def _enviar_token(token: str, email_destino: str):
    """Envia o token 2FA via SMTP configurado."""
    try:
        from config_emails import load_smtp_config
        from email_utils import enviar_email_smtp
        smtp = load_smtp_config()
        if not smtp or not smtp.get('usuario'):
            return False, "SMTP não configurado. Acesse ⚙️ Configurações → SMTP."
        corpo = f"""
        <html><body style="font-family:Arial,sans-serif; color:#333; margin:30px;">
        <div style="background:#0066cc; color:white; padding:15px; border-radius:8px; margin-bottom:20px;">
            <h2 style="margin:0;">🔐 Dashboard Allied — Verificação de Acesso</h2>
        </div>
        <p>Seu código de verificação é:</p>
        <div style="background:#f5f5f5; border-left:4px solid #ff6b35; padding:20px; text-align:center; margin:20px 0; border-radius:4px;">
            <span style="letter-spacing:12px; color:#ff6b35; font-size:2.5rem; font-weight:bold;">{token}</span>
        </div>
        <p style="color:#666;">⏱️ Válido por <strong>5 minutos</strong>.</p>
        <p style="color:#999; font-size:12px;">Se você não solicitou este código, ignore este email.</p>
        </body></html>
        """
        return enviar_email_smtp(
            email_destino,
            "🔐 Código de verificação - Dashboard Allied",
            corpo,
            servidor_smtp=smtp.get('servidor'),
            porta=smtp.get('porta', 587),
            usuario=smtp.get('usuario'),
            senha=smtp.get('senha'),
            usar_tls=smtp.get('usar_tls', True)
        )
    except Exception as e:
        return False, f"Erro ao enviar token: {str(e)}"

def _render_login():
    """Renderiza a tela de login com suporte a 2FA."""
    st.markdown("""
    <style>
        .login-title {
            font-size: 2rem;
            font-weight: bold;
            color: #0066cc;
            text-align: center;
            margin-bottom: 0.25rem;
        }
        .login-subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }
    </style>
    <div style="max-width:420px; margin:4rem auto;">
        <div class="login-title">🔐 Dashboard Allied</div>
        <div class="login-subtitle">Acesso restrito — faça login para continuar</div>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:

        # ── ETAPA 2: verificação do token 2FA ──────────────────────────────────
        if st.session_state.get('awaiting_2fa', False):

            if datetime.now() > st.session_state.get('mfa_expires', datetime.min):
                st.error("⏰ Código expirado. Faça login novamente.")
                if st.button("↩️ Voltar ao login", use_container_width=True):
                    st.session_state.awaiting_2fa = False
                    st.rerun()
                st.stop()

            email_destino = st.session_state.get('mfa_email', '')
            partes = email_destino.split('@')
            if len(partes) == 2:
                email_exibido = partes[0][:2] + '***@' + partes[1]
            else:
                email_exibido = "o email configurado"
            st.info(f"📧 Código enviado para **{email_exibido}**. Verifique sua caixa de entrada.")

            with st.form("form_token", clear_on_submit=False):
                st.text_input("Código de verificação", key="token_input",
                              placeholder="000000", max_chars=6)
                col_v, col_b = st.columns(2)
                with col_v:
                    verificar = st.form_submit_button("✅ Verificar", use_container_width=True)
                with col_b:
                    voltar = st.form_submit_button("↩️ Voltar", use_container_width=True)

            if verificar:
                token_digitado = st.session_state.get("token_input", "").strip()
                if token_digitado == st.session_state.get('mfa_token', ''):
                    st.session_state.authenticated = True
                    st.session_state.awaiting_2fa = False
                    st.session_state.pop('mfa_token', None)
                    st.rerun()
                else:
                    st.error("❌ Código incorreto. Tente novamente.")

            if voltar:
                st.session_state.awaiting_2fa = False
                st.rerun()

            st.markdown("---")
            if st.button("🔄 Reenviar código", use_container_width=True):
                config_2fa = _carregar_config_2fa()
                token = _gerar_token()
                st.session_state.mfa_token   = token
                st.session_state.mfa_expires = datetime.now() + timedelta(minutes=5)
                sucesso, msg = _enviar_token(token, config_2fa.get('email', ''))
                if sucesso:
                    st.success("✅ Novo código enviado!")
                else:
                    st.error(f"❌ {msg}")

        # ── ETAPA 1: usuário e senha ────────────────────────────────────────────
        else:
            with st.form("form_login", clear_on_submit=False):
                st.text_input("Usuário", key="login_usuario", placeholder="usuário")
                st.text_input("Senha", type="password", key="login_senha", placeholder="••••••••")
                entrar = st.form_submit_button("Entrar", use_container_width=True)

            if entrar:
                usuario = st.session_state.get("login_usuario", "")
                senha   = st.session_state.get("login_senha", "")
                if _verificar_credenciais(usuario, senha):
                    config_2fa = _carregar_config_2fa()
                    if config_2fa.get('enabled') and config_2fa.get('email'):
                        token = _gerar_token()
                        sucesso, msg = _enviar_token(token, config_2fa['email'])
                        if sucesso:
                            st.session_state.mfa_token   = token
                            st.session_state.mfa_expires = datetime.now() + timedelta(minutes=5)
                            st.session_state.mfa_email   = config_2fa['email']
                            st.session_state.awaiting_2fa = True
                            st.rerun()
                        else:
                            st.error(f"❌ Falha ao enviar o código 2FA: {msg}")
                            st.info("💡 Verifique as configurações de SMTP em ⚙️ Configurações.")
                    else:
                        st.session_state.authenticated = True
                        st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")

if not st.session_state.get("authenticated", False):
    _render_login()
    st.stop()
# ─────────────────────────────────────────────────────────────────────────────

# ── RECUPERAÇÃO DE DADOS E CONFIGS (após hibernação) ─────────────────────
if not st.session_state.get('startup_recovery_done', False):
    st.session_state.startup_recovery_done = True

    xlsb_existente = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    config_json_existente = (BASE_DIR / "email_config.json").exists()

    # Tentar restaurar base de dados do email se não existe localmente
    if not xlsb_existente:
        try:
            ok, resultado = restaurar_backup_dados(str(BASE_DIR))
            if ok:
                st.toast(f"☁️ Base restaurada do backup: {Path(resultado).name}", icon="✅")
        except Exception:
            pass

    # Tentar restaurar configs do email se não existem localmente
    if not config_json_existente:
        try:
            ok, msg = restaurar_backup_configs(str(BASE_DIR))
            if ok:
                st.toast("☁️ Configurações restauradas do backup!", icon="✅")
        except Exception:
            pass

# Verificar se precisa de import manual (sem .xlsb e sem backup)
xlsb_existente = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
config_json_existente = (BASE_DIR / "email_config.json").exists()

_precisa_upload_base = not xlsb_existente
_precisa_import_config = not config_json_existente

if _precisa_upload_base or _precisa_import_config:
    st.markdown('<h2 style="text-align:center; color:#0066cc;">📦 Configuração Inicial</h2>', unsafe_allow_html=True)
    st.markdown("---")

    if _precisa_upload_base:
        st.warning("⚠️ Nenhuma base de dados (.xlsb) encontrada.")
        arquivo_inicial = st.file_uploader(
            "📂 Faça upload do arquivo .xlsb",
            type=["xlsb"],
            key="upload_inicial_xlsb"
        )
        if arquivo_inicial is not None:
            # Salvar arquivo
            caminho = BASE_DIR / arquivo_inicial.name
            caminho.write_bytes(arquivo_inicial.getvalue())
            st.cache_data.clear()
            # Backup no email
            try:
                ok, msg = enviar_backup_dados(str(caminho))
                if ok:
                    st.success(f"✅ Base carregada e backup enviado por email!")
                else:
                    st.success("✅ Base carregada!")
                    st.caption(f"⚠️ Backup não enviado: {msg}")
            except Exception:
                st.success("✅ Base carregada!")
            st.rerun()

    if _precisa_import_config:
        st.warning("⚠️ Nenhuma configuração de emails encontrada.")
        st.caption("💡 Importe os arquivos JSON de configuração da sua máquina.")
        arquivos_json = st.file_uploader(
            "📂 Selecione os arquivos JSON (email_config.json, email_config_smtp.json, auth_config.json)",
            type=["json"],
            accept_multiple_files=True,
            key="upload_inicial_json"
        )
        if arquivos_json:
            for arq in arquivos_json:
                (BASE_DIR / arq.name).write_bytes(arq.getvalue())
            try:
                ok, msg = enviar_backup_configs(str(BASE_DIR))
                if ok:
                    st.success("✅ Configurações importadas e backup enviado por email!")
                else:
                    st.success("✅ Configurações importadas!")
                    st.caption(f"⚠️ Backup não enviado: {msg}")
            except Exception:
                st.success("✅ Configurações importadas!")
            st.rerun()

    if _precisa_upload_base:
        st.stop()

# ─────────────────────────────────────────────────────────────────────────────

# Importar módulos dos dashboards
try:
    from dashboard_cobranca import render_dashboard_cobranca
    cobranca_disponivel = True
except Exception as e:
    st.error(f"Erro ao importar dashboard_cobranca: {e}")
    st.code(traceback.format_exc())
    cobranca_disponivel = False

try:
    from config_emails import render_configuracoes
    config_disponivel = True
except Exception as e:
    st.error(f"Erro ao importar config_emails: {e}")
    st.code(traceback.format_exc())
    config_disponivel = False

# Botão de logout na sidebar (visível em todas as páginas após login)
with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True, help="Encerrar sessão"):
        st.session_state.authenticated = False
        st.session_state.page = 'menu'
        st.rerun()

# Menu Principal
if st.session_state.page == 'menu':
    st.markdown('<h1 class="main-header">🏢 Dashboard Allied - Menu Principal</h1>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📋 Dashboard Controle\nde Cobrança", use_container_width=True, help="Acesse o dashboard de controle de boletos em atraso"):
            st.session_state.page = 'cobranca'
            st.rerun()
    
    with col2:
        if st.button("⚙️ Configurações\nEmails de Vendedores", use_container_width=True, help="Configure emails de vendedores para envio de relatórios"):
            st.session_state.page = 'config'
            st.rerun()
    
    st.markdown("---")
    
    st.info("""
    ### 📌 Bem-vindo ao Dashboard Allied
    
    Escolha um dos dashboards acima para visualizar os dados:
    
    **📋 Dashboard de Cobrança:**
    - Análise de boletos em atraso
    - Distribuição por faixa de atraso
    - Análise por vendedor e cliente
    - Filtros dinâmicos para melhor visualização
    - Envio de relatórios por email
    
    **⚙️ Configurações:**
    - Configure emails de vendedores
    - Adicione emails em cópia (CC)
    - Gerencie as configurações de envio
    """)

# Dashboard Cobrança
elif st.session_state.page == 'cobranca':
    st.sidebar.title("🔙 Navegação")
    if st.sidebar.button("← Voltar ao Menu Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Importar / Atualizar base de dados
    st.sidebar.subheader("🔄 Atualizar Base de Dados")
    
    arquivo_upload = st.sidebar.file_uploader(
        "Selecione o novo arquivo .xlsb",
        type=["xlsb"],
        key="upload_cobranca",
        help="Selecione um arquivo .xlsb para substituir a base atual"
    )
    
    if arquivo_upload is not None:
        # Verificar se este arquivo já foi processado (evita loop infinito no rerun)
        file_id = f"{arquivo_upload.name}_{arquivo_upload.size}"
        if st.session_state.get('last_uploaded_cobranca') != file_id:
            # Remover arquivo(s) .xlsb atual(is) da pasta do app
            for f in BASE_DIR.glob("*.xlsb"):
                if not f.name.startswith("~$"):
                    f.unlink()
            
            # Salvar novo arquivo na pasta do app
            novo_caminho = BASE_DIR / arquivo_upload.name
            novo_caminho.write_bytes(arquivo_upload.getvalue())
            
            # Limpar cache e session state de dados antigos
            st.cache_data.clear()
            if 'df_aging' in st.session_state:
                del st.session_state['df_aging']
            if 'erro_aging' in st.session_state:
                del st.session_state['erro_aging']
            
            # Marcar arquivo como já processado
            st.session_state['last_uploaded_cobranca'] = file_id
            
            st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo_upload.name}")
            
            # Backup automático no email
            try:
                ok_bkp, msg_bkp = enviar_backup_dados(str(novo_caminho))
                if ok_bkp:
                    st.sidebar.caption("☁️ Backup atualizado no email")
                else:
                    st.sidebar.caption(f"⚠️ Backup: {msg_bkp}")
            except Exception:
                pass
            
            st.rerun()
        else:
            st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo_upload.name}")
    
    # Mostrar arquivo atual
    xlsb_atual = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    if xlsb_atual:
        st.sidebar.caption(f"📂 Atual: **{xlsb_atual[0].name}**")
    else:
        st.sidebar.warning("⚠️ Nenhuma base carregada")
    
    st.sidebar.markdown("---")
    
    if cobranca_disponivel:
        render_dashboard_cobranca()
    else:
        st.error("❌ Não foi possível carregar o dashboard de Cobrança")
    
    # Botão encerrar no fim do sidebar (apenas local/Windows)
    if platform.system() == 'Windows':
        st.sidebar.markdown("---")
        if st.sidebar.button("⛔ Encerrar Dashboard", use_container_width=True, help="Encerra a aplicação e libera a porta"):
            st.sidebar.warning("Encerrando o Dashboard...")
            import signal
            os.kill(os.getpid(), signal.SIGTERM)

# Configurações
elif st.session_state.page == 'config':
    st.sidebar.title("🔙 Navegação")
    if st.sidebar.button("← Voltar ao Menu Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Importar / Atualizar base de dados
    st.sidebar.subheader("🔄 Atualizar Base de Dados")
    
    arquivo_upload_cfg = st.sidebar.file_uploader(
        "Selecione o novo arquivo .xlsb",
        type=["xlsb"],
        key="upload_config",
        help="Selecione um arquivo .xlsb para substituir a base atual"
    )
    
    if arquivo_upload_cfg is not None:
        # Verificar se este arquivo já foi processado (evita loop infinito no rerun)
        file_id_cfg = f"{arquivo_upload_cfg.name}_{arquivo_upload_cfg.size}"
        if st.session_state.get('last_uploaded_config') != file_id_cfg:
            for f in BASE_DIR.glob("*.xlsb"):
                if not f.name.startswith("~$"):
                    f.unlink()
            
            novo_caminho = BASE_DIR / arquivo_upload_cfg.name
            novo_caminho.write_bytes(arquivo_upload_cfg.getvalue())
            
            st.cache_data.clear()
            if 'df_aging' in st.session_state:
                del st.session_state['df_aging']
            if 'erro_aging' in st.session_state:
                del st.session_state['erro_aging']
            
            # Marcar arquivo como já processado
            st.session_state['last_uploaded_config'] = file_id_cfg
            
            st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo_upload_cfg.name}")
            
            # Backup automático no email
            try:
                ok_bkp, msg_bkp = enviar_backup_dados(str(novo_caminho))
                if ok_bkp:
                    st.sidebar.caption("☁️ Backup atualizado no email")
                else:
                    st.sidebar.caption(f"⚠️ Backup: {msg_bkp}")
            except Exception:
                pass
            
            st.rerun()
        else:
            st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo_upload_cfg.name}")
    
    xlsb_atual = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    if xlsb_atual:
        st.sidebar.caption(f"📂 Atual: **{xlsb_atual[0].name}**")
    else:
        st.sidebar.warning("⚠️ Nenhuma base carregada")
    
    st.sidebar.markdown("---")
    
    if config_disponivel:
        render_configuracoes()
    else:
        st.error("❌ Não foi possível carregar a página de configurações")
    
    # Botão encerrar no fim do sidebar (apenas local/Windows)
    if platform.system() == 'Windows':
        st.sidebar.markdown("---")
        if st.sidebar.button("⛔ Encerrar Dashboard", use_container_width=True, help="Encerra a aplicação e libera a porta"):
            st.sidebar.warning("Encerrando o Dashboard...")
            import signal
            os.kill(os.getpid(), signal.SIGTERM)
