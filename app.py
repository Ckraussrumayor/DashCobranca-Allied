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
    import secrets
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
from utils import get_base_path, BASE_DIR
sys.path.insert(0, str(BASE_DIR))

# Configurar locale para português brasileiro
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except Exception:
    try:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
    except Exception:
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

# ── CONSTANTES DE SEGURANÇA ────────────────────────────────────────────────────
_MAX_LOGIN_ATTEMPTS = 5
_LOCKOUT_MINUTES = 5
_SESSION_TIMEOUT_MINUTES = 60

# ── AUTENTICAÇÃO ──────────────────────────────────────────────────────────────
def _verificar_credenciais(usuario: str, senha: str) -> bool:
    """Compara usuário e senha com os valores configurados nos secrets."""
    try:
        usuario_correto = st.secrets["credentials"]["username"]
        senha_correta   = st.secrets["credentials"]["password"]
    except KeyError:
        # Sem secrets configurados, bloqueia acesso por segurança
        return False
    return usuario.strip() == usuario_correto and senha == senha_correta

def _login_bloqueado() -> bool:
    """Verifica se o login está bloqueado por excesso de tentativas."""
    bloqueado_ate = st.session_state.get('login_bloqueado_ate')
    if bloqueado_ate and datetime.now() < bloqueado_ate:
        return True
    if bloqueado_ate and datetime.now() >= bloqueado_ate:
        st.session_state.login_tentativas = 0
        st.session_state.login_bloqueado_ate = None
    return False

def _registrar_tentativa_falha():
    """Incrementa contador de tentativas falhas e bloqueia se exceder limite."""
    tentativas = st.session_state.get('login_tentativas', 0) + 1
    st.session_state.login_tentativas = tentativas
    if tentativas >= _MAX_LOGIN_ATTEMPTS:
        st.session_state.login_bloqueado_ate = datetime.now() + timedelta(minutes=_LOCKOUT_MINUTES)
        return True  # bloqueou agora
    return False

def _verificar_sessao_expirada() -> bool:
    """Verifica se a sessão autenticada expirou por inatividade."""
    ultima_atividade = st.session_state.get('ultima_atividade')
    if ultima_atividade and datetime.now() - ultima_atividade > timedelta(minutes=_SESSION_TIMEOUT_MINUTES):
        return True
    return False

def _atualizar_atividade():
    """Registra timestamp da última atividade do usuário."""
    st.session_state.ultima_atividade = datetime.now()

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
    return ''.join(secrets.choice(string.digits) for _ in range(6))

def _enviar_token(token: str, email_destino):
    """Envia o token 2FA via SMTP. email_destino pode ser string única ou lista."""
    try:
        from config_emails import load_smtp_config
        from email_utils import enviar_email_smtp

        # Normalizar para lista de emails
        if isinstance(email_destino, str):
            emails = [e.strip() for e in email_destino.replace(';', ',').replace('\n', ',').split(',') if e.strip() and '@' in e.strip()]
        else:
            emails = [e.strip() for e in email_destino if e.strip() and '@' in e.strip()]

        if not emails:
            return False, "Nenhum email válido configurado para receber o código 2FA."

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

        erros = []
        for email in emails:
            sucesso, msg = enviar_email_smtp(
                email,
                "🔐 Código de verificação - Dashboard Allied",
                corpo,
                servidor_smtp=smtp.get('servidor'),
                porta=smtp.get('porta', 587),
                usuario=smtp.get('usuario'),
                senha=smtp.get('senha'),
                usar_tls=smtp.get('usar_tls', True)
            )
            if not sucesso:
                erros.append(f"{email}: {msg}")

        if erros:
            return False, "\n".join(erros)
        return True, f"Código enviado para: {', '.join(emails)}"

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
            # Mascarar emails para exibição (suporte a múltiplos)
            emails_lista = [e.strip() for e in str(email_destino).replace(';', ',').replace('\n', ',').split(',') if e.strip() and '@' in e.strip()]
            def _mascarar(e):
                partes = e.split('@')
                return partes[0][:2] + '***@' + partes[1] if len(partes) == 2 else e
            email_exibido = ', '.join(_mascarar(e) for e in emails_lista) if emails_lista else "o email configurado"

            if st.session_state.get('mfa_smtp_erro'):
                st.error(
                    "❌ Falha ao enviar o código por email. "
                    "Verifique as configurações de SMTP em ⚙️ Configurações → SMTP."
                )
            else:
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
                    _atualizar_atividade()
                    st.rerun()
                else:
                    st.error("❌ Código incorreto. Tente novamente.")

            if voltar:
                st.session_state.awaiting_2fa = False
                st.rerun()

            st.markdown("---")
            ultimo_envio = st.session_state.get('mfa_ultimo_envio')
            segundos_restantes = max(0, 30 - int((datetime.now() - ultimo_envio).total_seconds())) if ultimo_envio else 0
            reenviar_desabilitado = segundos_restantes > 0
            label_reenviar = f"🔄 Aguarde {segundos_restantes}s para reenviar" if reenviar_desabilitado else "🔄 Reenviar código"
            if st.button(label_reenviar, use_container_width=True, disabled=reenviar_desabilitado):
                config_2fa = _carregar_config_2fa()
                token = _gerar_token()
                st.session_state.mfa_token   = token
                st.session_state.mfa_expires = datetime.now() + timedelta(minutes=5)
                sucesso, msg = _enviar_token(token, config_2fa.get('email', ''))
                st.session_state.mfa_smtp_erro = not sucesso
                st.session_state.mfa_ultimo_envio = datetime.now()
                st.rerun()

        # ── ETAPA 1: usuário e senha ────────────────────────────────────────────
        else:
            # Verificar bloqueio por tentativas excessivas
            if _login_bloqueado():
                bloqueado_ate = st.session_state.get('login_bloqueado_ate')
                restante = (bloqueado_ate - datetime.now()).seconds // 60 + 1
                st.error(f"🔒 Login bloqueado por excesso de tentativas. Tente novamente em {restante} minuto(s).")
                st.stop()

            with st.form("form_login", clear_on_submit=False):
                st.text_input("Usuário", key="login_usuario", placeholder="usuário")
                st.text_input("Senha", type="password", key="login_senha", placeholder="••••••••")
                entrar = st.form_submit_button("Entrar", use_container_width=True)

            if entrar:
                usuario = st.session_state.get("login_usuario", "")
                senha   = st.session_state.get("login_senha", "")
                if _verificar_credenciais(usuario, senha):
                    # Reset tentativas após login bem-sucedido
                    st.session_state.login_tentativas = 0
                    st.session_state.login_bloqueado_ate = None
                    config_2fa = _carregar_config_2fa()
                    if config_2fa.get('enabled') and config_2fa.get('email'):
                        # Throttle: evitar envios duplicados ao clicar várias vezes (instabilidade de rede).
                        # Os flags são gravados ANTES do envio SMTP para que qualquer rerun subsequente
                        # já encontre awaiting_2fa=True e pule o envio, mesmo que o script seja
                        # interrompido durante a chamada bloqueante ao servidor de e-mail.
                        ultimo_envio = st.session_state.get('mfa_ultimo_envio')
                        if not ultimo_envio or (datetime.now() - ultimo_envio).total_seconds() > 30:
                            token = _gerar_token()
                            # Gravar flags PRIMEIRO — impede reenvio se o rerun for interrompido
                            st.session_state.mfa_token         = token
                            st.session_state.mfa_expires       = datetime.now() + timedelta(minutes=5)
                            st.session_state.mfa_email         = config_2fa['email']
                            st.session_state.mfa_ultimo_envio  = datetime.now()
                            st.session_state.awaiting_2fa      = True
                            st.session_state.mfa_smtp_erro     = False
                            sucesso, msg = _enviar_token(token, config_2fa['email'])
                            st.session_state.mfa_smtp_erro     = not sucesso
                        else:
                            # Token já enviado recentemente: apenas navega para a tela do código
                            st.session_state.awaiting_2fa = True
                        st.rerun()
                    else:
                        st.session_state.authenticated = True
                        _atualizar_atividade()
                        st.rerun()
                else:
                    bloqueou = _registrar_tentativa_falha()
                    restantes = _MAX_LOGIN_ATTEMPTS - st.session_state.get('login_tentativas', 0)
                    if bloqueou:
                        st.error(f"🔒 Login bloqueado por {_LOCKOUT_MINUTES} minutos após {_MAX_LOGIN_ATTEMPTS} tentativas falhas.")
                        st.rerun()
                    else:
                        st.error(f"❌ Usuário ou senha incorretos. ({restantes} tentativa(s) restante(s))")

if not st.session_state.get("authenticated", False):
    _render_login()
    st.stop()

# ── TIMEOUT DE SESSÃO ─────────────────────────────────────────────────────────
if _verificar_sessao_expirada():
    st.session_state.authenticated = False
    st.session_state.page = 'menu'
    st.warning("⏰ Sessão expirada por inatividade. Faça login novamente.")
    _render_login()
    st.stop()
_atualizar_atividade()
# ─────────────────────────────────────────────────────────────────────────────

# ── RECUPERAÇÃO DE DADOS E CONFIGS (após hibernação) ─────────────────────
if not st.session_state.get('startup_recovery_done', False):
    st.session_state.startup_recovery_done = True

    xlsb_existente = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    config_json_existente = (BASE_DIR / "email_config.json").exists()

    # Tentar restaurar base de dados do email se não existe localmente
    if not xlsb_existente:
        with st.spinner("☁️ Restaurando base de dados do backup..."):
            try:
                ok, resultado = restaurar_backup_dados(str(BASE_DIR))
                if ok:
                    st.toast(f"☁️ Base restaurada do backup: {Path(resultado).name}", icon="✅")
                else:
                    st.toast(f"⚠️ Backup de dados não disponível: {resultado}", icon="⚠️")
            except Exception as e:
                st.toast(f"❌ Falha ao restaurar backup de dados: {e}", icon="❌")

    # Tentar restaurar configs do email se não existem localmente
    if not config_json_existente:
        with st.spinner("☁️ Restaurando configurações do backup..."):
            try:
                ok, msg = restaurar_backup_configs(str(BASE_DIR))
                if ok:
                    st.toast("☁️ Configurações restauradas do backup!", icon="✅")
                else:
                    st.toast(f"⚠️ Backup de configs não disponível: {msg}", icon="⚠️")
            except Exception as e:
                st.toast(f"❌ Falha ao restaurar backup de configs: {e}", icon="❌")

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

# ── Botão encerrar reutilizável (apenas local/Windows) ──────────────────────
def _render_encerrar_button():
    if platform.system() == 'Windows':
        st.sidebar.markdown("---")
        if st.sidebar.button("⛔ Encerrar Dashboard", use_container_width=True, help="Encerra a aplicação e libera a porta"):
            st.sidebar.warning("Encerrando o Dashboard...")
            import signal
            os.kill(os.getpid(), signal.SIGTERM)

# ── Função reutilizável de upload de base .xlsb na sidebar ──────────────────
def _render_sidebar_upload(uploader_key: str):
    """Renderiza o bloco de upload + status da base .xlsb na sidebar."""
    _MAX_UPLOAD_MB = 50
    st.sidebar.subheader("🔄 Atualizar Base de Dados")
    arquivo = st.sidebar.file_uploader(
        "Selecione o novo arquivo .xlsb",
        type=["xlsb"],
        key=uploader_key,
        help="Selecione um arquivo .xlsb para substituir a base atual"
    )
    if arquivo is not None:
        tamanho_mb = arquivo.size / (1024 * 1024)
        if tamanho_mb > _MAX_UPLOAD_MB:
            st.sidebar.error(f"❌ Arquivo muito grande ({tamanho_mb:.1f} MB). Limite: {_MAX_UPLOAD_MB} MB.")
        else:
            file_id = f"{arquivo.name}_{arquivo.size}"
            state_key = f"last_uploaded_{uploader_key}"
            if st.session_state.get(state_key) != file_id:
                for f in BASE_DIR.glob("*.xlsb"):
                    if not f.name.startswith("~$"):
                        f.unlink()
                novo_caminho = BASE_DIR / arquivo.name
                novo_caminho.write_bytes(arquivo.getvalue())
                st.cache_data.clear()
                st.session_state.pop('df_aging', None)
                st.session_state.pop('erro_aging', None)
                st.session_state[state_key] = file_id
                st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo.name}")
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
                st.sidebar.success(f"✅ Base atualizada!\n📁 {arquivo.name}")
    xlsb_atual = [f for f in BASE_DIR.glob("*.xlsb") if not f.name.startswith("~$")]
    if xlsb_atual:
        st.sidebar.caption(f"📂 Atual: **{xlsb_atual[0].name}**")
    else:
        st.sidebar.warning("⚠️ Nenhuma base carregada")
    st.sidebar.markdown("---")

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
    
    _render_sidebar_upload("upload_cobranca")
    
    if cobranca_disponivel:
        render_dashboard_cobranca()
    else:
        st.error("❌ Não foi possível carregar o dashboard de Cobrança")
    
    _render_encerrar_button()

# Configurações
elif st.session_state.page == 'config':
    st.sidebar.title("🔙 Navegação")
    if st.sidebar.button("← Voltar ao Menu Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    
    st.sidebar.markdown("---")
    
    _render_sidebar_upload("upload_config")
    
    if config_disponivel:
        render_configuracoes()
    else:
        st.error("❌ Não foi possível carregar a página de configurações")
    
    _render_encerrar_button()
