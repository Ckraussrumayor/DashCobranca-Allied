"""
Módulo de backup via email para persistência de dados no Streamlit Cloud.
Usa SMTP para enviar backups e IMAP para recuperar/limpar.
"""
import imaplib
import smtplib
import email as email_lib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
import zipfile
import tempfile

SUBJECT_DADOS = "[ALLIED-BACKUP-DADOS]"
SUBJECT_CONFIG = "[ALLIED-BACKUP-CONFIG]"


def _get_smtp_config():
    """Carrega config SMTP do arquivo local ou secrets (fallback para Cloud)."""
    try:
        from config_emails import load_smtp_config
        config = load_smtp_config()
        if config and config.get('usuario') and config.get('senha'):
            return config
    except Exception:
        pass
    # Fallback: secrets do Streamlit Cloud
    try:
        import streamlit as st
        sec = st.secrets["smtp"]
        return {
            'servidor': sec["servidor"],
            'porta': int(sec.get("porta", 587)),
            'usuario': sec["usuario"],
            'senha': sec["senha"],
            'usar_tls': sec.get("usar_tls", True),
            'servidor_imap': sec.get("servidor_imap", ""),
            'porta_imap': int(sec.get("porta_imap", 993)),
        }
    except Exception:
        return {}


def _inferir_imap(servidor_smtp):
    """Deriva servidor IMAP a partir do SMTP."""
    mapa = {
        'smtp.gmail.com': 'imap.gmail.com',
        'smtp-mail.outlook.com': 'outlook.office365.com',
        'smtp.office365.com': 'outlook.office365.com',
    }
    chave = servidor_smtp.lower().strip()
    return mapa.get(chave, chave.replace('smtp', 'imap', 1))


def _conectar_imap(config):
    """Conecta ao servidor IMAP."""
    servidor = config.get('servidor_imap') or _inferir_imap(config.get('servidor', ''))
    porta = int(config.get('porta_imap', 993))
    conn = imaplib.IMAP4_SSL(servidor, porta, timeout=15)
    conn.login(config['usuario'], config['senha'])
    return conn


# ── ENVIO DE BACKUP ───────────────────────────────────────────────────────────

def enviar_backup_dados(arquivo_path):
    """Envia backup do arquivo de dados (.xlsb) por email."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return False, "SMTP não configurado."
    # Limpar backups anteriores
    limpar_backups('dados')
    return _enviar_email_backup(config, SUBJECT_DADOS, [arquivo_path])


def enviar_backup_configs(base_dir):
    """Empacota os JSONs de configuração em um .zip e envia por email."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return False, "SMTP não configurado."
    base = Path(base_dir)
    jsons = [f for f in base.glob("*.json") if not f.name.startswith("_backup")]
    if not jsons:
        return False, "Nenhum arquivo de configuração encontrado."
    zip_path = base / "_backup_configs.zip"
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for j in jsons:
                zf.write(j, j.name)
        limpar_backups('config')
        resultado = _enviar_email_backup(config, SUBJECT_CONFIG, [zip_path])
    finally:
        if zip_path.exists():
            zip_path.unlink()
    return resultado


def _enviar_email_backup(config, subject_tag, arquivos):
    """Envia email com anexos para o próprio remetente."""
    destinatario = config['usuario']
    msg = MIMEMultipart()
    msg['From'] = config['usuario']
    msg['To'] = destinatario
    msg['Subject'] = f"{subject_tag} Backup Dashboard Allied"
    msg.attach(MIMEText(
        "Backup automático gerado pelo Dashboard Allied.\n"
        "Não apague este email manualmente — o sistema gerencia automaticamente.",
        'plain'
    ))
    for arq in arquivos:
        arq = Path(arq)
        with open(arq, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{arq.name}"')
            msg.attach(part)
    try:
        with smtplib.SMTP(config['servidor'], config.get('porta', 587), timeout=20) as server:
            if config.get('usar_tls', True):
                server.starttls()
            server.login(config['usuario'], config['senha'])
            server.send_message(msg)
        return True, "Backup enviado."
    except Exception as e:
        return False, f"Erro ao enviar backup: {str(e)}"


# ── RECUPERAÇÃO DE BACKUP ─────────────────────────────────────────────────────

def restaurar_backup_dados(destino_dir):
    """Baixa o .xlsb mais recente do email. Retorna (sucesso, caminho_ou_msg)."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return False, "SMTP não configurado."
    return _baixar_anexo(config, SUBJECT_DADOS, destino_dir)


def restaurar_backup_configs(destino_dir):
    """Baixa e extrai o zip de configs do email. Retorna (sucesso, msg)."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return False, "SMTP não configurado."
    ok, resultado = _baixar_anexo(config, SUBJECT_CONFIG, tempfile.gettempdir())
    if not ok:
        return False, resultado
    zip_path = Path(resultado)
    try:
        destino = Path(destino_dir).resolve()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Validar contra path traversal antes de extrair
            for member in zf.namelist():
                member_path = (destino / member).resolve()
                if not str(member_path).startswith(str(destino)):
                    return False, f"Arquivo suspeito no backup: {member}"
            zf.extractall(destino_dir)
        zip_path.unlink()
        return True, "Configurações restauradas do backup."
    except Exception as e:
        return False, f"Erro ao extrair configs: {str(e)}"


def _baixar_anexo(config, subject_tag, destino_dir):
    """Busca o email mais recente com subject_tag e baixa o anexo."""
    try:
        conn = _conectar_imap(config)
        conn.select('INBOX')
        status, data = conn.search(None, f'(SUBJECT "{subject_tag}")')
        if status != 'OK' or not data[0]:
            conn.logout()
            return False, "Nenhum backup encontrado no email."
        ids = data[0].split()
        _, msg_data = conn.fetch(ids[-1], '(RFC822)')
        conn.logout()
        msg = email_lib.message_from_bytes(msg_data[0][1])
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            nome = part.get_filename()
            if nome:
                caminho = Path(destino_dir) / nome
                caminho.write_bytes(part.get_payload(decode=True))
                return True, str(caminho)
        return False, "Email de backup encontrado mas sem anexo."
    except Exception as e:
        return False, f"Erro IMAP: {str(e)}"


# ── LIMPEZA DE BACKUPS ────────────────────────────────────────────────────────

def limpar_backups(tipo='dados'):
    """Remove todos os emails de backup do tipo especificado."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return False, "SMTP não configurado."
    tag = SUBJECT_DADOS if tipo == 'dados' else SUBJECT_CONFIG
    try:
        conn = _conectar_imap(config)
        conn.select('INBOX')
        status, data = conn.search(None, f'(SUBJECT "{tag}")')
        if status == 'OK' and data[0]:
            for mid in data[0].split():
                conn.store(mid, '+FLAGS', '\\Deleted')
            conn.expunge()
        conn.logout()
        return True, "Backups antigos removidos."
    except Exception as e:
        return False, f"Erro ao limpar backups: {str(e)}"


def verificar_backup_disponivel():
    """Verifica quais tipos de backup existem no email."""
    config = _get_smtp_config()
    if not config or not config.get('usuario'):
        return {'dados': False, 'config': False}
    resultado = {'dados': False, 'config': False}
    try:
        conn = _conectar_imap(config)
        conn.select('INBOX')
        for tipo, tag in [('dados', SUBJECT_DADOS), ('config', SUBJECT_CONFIG)]:
            status, data = conn.search(None, f'(SUBJECT "{tag}")')
            if status == 'OK' and data[0]:
                resultado[tipo] = True
        conn.logout()
    except Exception:
        pass
    return resultado
