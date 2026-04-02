import streamlit as st
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
import re

try:
    import win32com.client
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False

# ── Regex pré-compilada para remoção de emojis (compilada UMA vez no import) ─
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed characters
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U00002600-\U000026FF"  # misc symbols (inclui ⚪)
    "\U00002700-\U000027BF"  # dingbats
    "]+",
    flags=re.UNICODE
)

# ── Template HTML do email de boletos ────────────────────────────────────────
EMAIL_TEMPLATE = """
<html>
<head>
<style>
    body {{
        font-family: Arial, sans-serif;
        color: #333;
        margin: 20px;
    }}
    .header {{
        background-color: #0066cc;
        color: white;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
    }}
    .info {{
        background-color: #f0f0f0;
        padding: 10px;
        margin: 10px 0;
        border-left: 4px solid #0066cc;
    }}
    h2 {{
        color: #0066cc;
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>Relatorio de Boletos em Atraso</h1>
    </div>
    
    <div class="info">
        <p><strong>Vendedor:</strong> {vendedor_nome}</p>
        <p><strong>Data de Geracao:</strong> {data_geracao}</p>
        <p><strong>Total de Boletos:</strong> {total_boletos}</p>
        <p><strong>Valor Total:</strong> {valor_total_fmt}</p>
    </div>
    
    <h2>Detalhes dos Boletos</h2>
    {html_tabela}
    
    <br><br>
    <p style="color: #999; font-size: 12px;">
        Este e um email automatico gerado pelo Dashboard Allied.<br>
        Favor nao responder este email.
    </p>
</body>
</html>
"""

try:
    import pythoncom
    PYTHONCOM_AVAILABLE = True
except ImportError:
    PYTHONCOM_AVAILABLE = False


def limpar_emojis(texto):
    """Remove emojis e caracteres especiais Unicode do texto"""
    if not texto:
        return ''
    return _EMOJI_PATTERN.sub('', str(texto)).strip()


def verificar_outlook_aberto():
    """
    Verifica se o Outlook está aberto e acessível
    Retorna: (bool, str) - (está_disponivel, mensagem)
    """
    if not OUTLOOK_AVAILABLE:
        return False, "Biblioteca pywin32 não instalada. Execute: pip install pywin32"
    
    try:
        if PYTHONCOM_AVAILABLE:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass
        
        # Tentar conectar ao Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        # Verificar se há pelo menos uma conta configurada
        if namespace.Accounts.Count == 0:
            return False, "Nenhuma conta de email configurada no Outlook"
        
        return True, "Outlook disponível"
        
    except pythoncom.com_error as e:
        error_code = e.hresult if hasattr(e, 'hresult') else 'desconhecido'
        if error_code == -2147221005:  # CO_E_CLASSSTRING - Outlook não instalado
            return False, "Outlook não está instalado neste computador"
        elif error_code == -2146959355:  # RPC_E_CALL_REJECTED - Outlook ocupado
            return False, "Outlook está ocupado. Feche caixas de diálogo abertas e tente novamente"
        else:
            return False, f"Erro COM ao conectar ao Outlook (código: {error_code})"
    except Exception as e:
        return False, f"Erro ao verificar Outlook: {str(e)}"

def enviar_email_outlook(destinatario, assunto, corpo, cc_list=None, cc_global=None, anexos=None):
    """
    Envia email através do Outlook
    cc_global: lista de emails que serão adicionados a todos os envios
    
    Retorna: (sucesso: bool, mensagem: str)
    """
    if not OUTLOOK_AVAILABLE:
        return False, "❌ Biblioteca pywin32 não está instalada.\n\nExecute no terminal:\npip install pywin32"
    
    # Inicializar COM para suportar múltiplas threads (necessário para Streamlit)
    if PYTHONCOM_AVAILABLE:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass  # COM já inicializado
    
    # Validar email destinatário
    if not destinatario or '@' not in str(destinatario):
        return False, f"❌ Email destinatário inválido: {destinatario}"
    
    # Combinar CCs específicos com CCs globais
    todos_ccs = []
    if cc_list:
        todos_ccs.extend([e.strip() for e in cc_list if e.strip()])
    if cc_global:
        todos_ccs.extend([e.strip() for e in cc_global if e.strip()])
    
    # Remover duplicatas e validar
    todos_ccs = list(set(todos_ccs))
    todos_ccs_validos = [e for e in todos_ccs if '@' in e]
    
    try:
        # Conectar ao Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        
    except pythoncom.com_error as e:
        error_code = getattr(e, 'hresult', None)
        if error_code == -2147221005:
            return False, "❌ Outlook não está instalado neste computador.\n\nInstale o Microsoft Outlook ou use o método SMTP."
        elif error_code == -2146959355:
            return False, "❌ Outlook está ocupado.\n\nFeche caixas de diálogo abertas no Outlook e tente novamente."
        else:
            return False, f"❌ Não foi possível conectar ao Outlook.\n\nVerifique se o Outlook está aberto.\n\nErro: {str(e)}"
    except Exception as e:
        return False, f"❌ Erro ao conectar ao Outlook: {str(e)}\n\n🔧 Verifique:\n• Outlook está aberto?\n• Conta de email configurada?"
    
    try:
        # Acessar namespace MAPI
        namespace = outlook.GetNamespace("MAPI")
        
        # Verificar contas
        if namespace.Accounts.Count == 0:
            return False, "❌ Nenhuma conta de email configurada no Outlook.\n\nConfigure uma conta de email no Outlook primeiro."
        
    except Exception as e:
        return False, f"❌ Erro ao acessar conta do Outlook: {str(e)}\n\nVerifique se sua conta está configurada corretamente."
    
    try:
        # Criar mail item
        mail = outlook.CreateItem(0)  # 0 = MailItem
        
        # Configurar email
        mail.To = destinatario
        mail.Subject = assunto
        mail.HTMLBody = corpo
        
        # Adicionar CC (combinado)
        if todos_ccs_validos:
            mail.CC = "; ".join(todos_ccs_validos)
        
        # Definir importância como Normal
        mail.Importance = 1  # 0=baixa, 1=normal, 2=alta
        
        # Adicionar anexos se houver
        if anexos:
            for anexo in anexos:
                if isinstance(anexo, str) and Path(anexo).exists():
                    mail.Attachments.Add(str(Path(anexo).absolute()))
        
    except Exception as e:
        return False, f"❌ Erro ao criar o email: {str(e)}"
    
    try:
        # ENVIAR o email
        mail.Send()
        
        # Construir mensagem de sucesso
        cc_info = f"\n📋 CC: {', '.join(todos_ccs_validos)}" if todos_ccs_validos else ""
        msg_sucesso = f"✅ Email enviado com sucesso!\n\n📧 Para: {destinatario}{cc_info}\n\n💡 Verifique a pasta 'Itens Enviados' no Outlook."
        
        return True, msg_sucesso
        
    except pythoncom.com_error as e:
        error_code = getattr(e, 'hresult', None)
        
        # Erros comuns de envio
        if error_code == -2147467259:  # E_FAIL genérico
            return False, "❌ Falha ao enviar email.\n\n🔧 Possíveis causas:\n• Outlook está offline\n• Problemas de conexão com servidor\n• Email bloqueado por política de segurança"
        elif error_code == -2146959355:  # RPC_E_CALL_REJECTED
            return False, "❌ Outlook recusou a operação.\n\nFeche todas as janelas/diálogos abertos no Outlook e tente novamente."
        else:
            return False, f"❌ Erro ao enviar email.\n\nCódigo: {error_code}\nDetalhes: {str(e)}"
            
    except Exception as e:
        return False, f"❌ Erro inesperado ao enviar: {str(e)}\n\n🔧 Verifique:\n• Outlook está aberto e online\n• Conexão com internet\n• Emails são válidos"

def criar_html_tabela(df):
    """
    Cria HTML formatado para a tabela de boletos
    """
    if df.empty:
        return "<p>Nenhum boleto para exibir.</p>"
    
    # Substituir todos os None/NaN por string vazia antes de gerar HTML
    df_limpo = df.fillna('').copy()
    
    # Limpar emojis e caracteres especiais de todas as colunas de texto
    for col in df_limpo.columns:
        if df_limpo[col].dtype == 'object':
            df_limpo[col] = df_limpo[col].apply(lambda x: limpar_emojis(str(x)) if pd.notna(x) else '')
    
    # Converter dataframe para HTML
    html = df_limpo.to_html(index=False, border=1, justify='center', escape=True)
    
    # Adicionar estilos CSS
    html_formatado = f"""
    <html>
    <head>
    <style>
        table {{
            border-collapse: collapse;
            width: 100%;
            font-family: Arial, sans-serif;
            font-size: 12px;
        }}
        th {{
            background-color: #0066cc;
            color: white;
            padding: 10px;
            text-align: left;
            border: 1px solid #ddd;
        }}
        td {{
            padding: 8px;
            border: 1px solid #ddd;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
    </style>
    </head>
    <body>
    {html}
    </body>
    </html>
    """
    return html_formatado

def criar_corpo_email(vendedor_nome, df_tabela, data_geracao):
    """
    Cria o corpo do email com o relatório de boletos
    """
    html_tabela = criar_html_tabela(df_tabela)
    
    # Calcular valor total - tratar caso já esteja formatado como string
    try:
        if 'Saldo Atual' in df_tabela.columns:
            # Verificar se é string (já formatado) ou número
            primeiro_valor = df_tabela['Saldo Atual'].iloc[0] if len(df_tabela) > 0 else 0
            if isinstance(primeiro_valor, str):
                # Converter de volta para número: "R$ 1.234,56" -> 1234.56
                valores = df_tabela['Saldo Atual'].apply(
                    lambda x: float(str(x).replace('R$', '').replace('.', '').replace(',', '.').strip()) 
                    if pd.notna(x) and str(x).strip() else 0
                )
                valor_total = valores.sum()
            else:
                valor_total = df_tabela['Saldo Atual'].sum()
        else:
            valor_total = 0
    except Exception:
        valor_total = 0
    
    # Formatar valor total
    valor_total_fmt = f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    corpo = EMAIL_TEMPLATE.format(
        vendedor_nome=vendedor_nome,
        data_geracao=data_geracao,
        total_boletos=len(df_tabela),
        valor_total_fmt=valor_total_fmt,
        html_tabela=html_tabela
    )
    
    return corpo


def verificar_smtp_auth(servidor_smtp=None, porta=587, usuario=None, senha=None, usar_tls=True):
    """
    Testa conexão e autenticação SMTP SEM enviar email.
    Retorna: (valido: bool, mensagem: str)
    """
    if not servidor_smtp or not usuario or not senha:
        return False, "SMTP não configurado. Configure em ⚙️ Configurações → SMTP."
    try:
        with smtplib.SMTP(servidor_smtp, porta, timeout=10) as server:
            if usar_tls:
                server.starttls()
            server.login(usuario, senha)
        return True, "Autenticação SMTP válida."
    except smtplib.SMTPAuthenticationError:
        return False, "Senha SMTP expirada ou inválida. Atualize a senha nas configurações."
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {str(e)}"
    except Exception as e:
        return False, f"Erro de conexão: {str(e)}"


def enviar_email_smtp(destinatario, assunto, corpo, cc_list=None, cc_global=None, anexos=None, 
                      servidor_smtp=None, porta=587, usuario=None, senha=None, usar_tls=True):
    """
    Envia email através de SMTP (alternativa mais confiável ao Outlook)
    
    Para Gmail:
    - servidor_smtp: "smtp.gmail.com"
    - porta: 587
    - usuario: seu_email@gmail.com
    - senha: senha_app (gerar em: https://myaccount.google.com/apppasswords)
    
    Para Outlook.com:
    - servidor_smtp: "smtp-mail.outlook.com"
    - porta: 587
    - usuario: seu_email@outlook.com
    - senha: sua_senha
    """
    
    try:
        if not servidor_smtp or not usuario or not senha:
            return False, "❌ Configure servidor SMTP, usuário e senha"
        
        # Validações
        if not destinatario or '@' not in destinatario:
            return False, f"Email destinatário inválido: {destinatario}"
        
        # Combinar CCs
        todos_ccs = []
        if cc_list:
            todos_ccs.extend([e.strip() for e in cc_list if e.strip() and '@' in e])
        if cc_global:
            todos_ccs.extend([e.strip() for e in cc_global if e.strip() and '@' in e])
        todos_ccs = list(set(todos_ccs))
        
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['From'] = usuario
        msg['To'] = destinatario
        msg['Subject'] = Header(assunto, 'utf-8')
        if todos_ccs:
            msg['Cc'] = ', '.join(todos_ccs)
        
        # Adicionar corpo HTML
        msg.attach(MIMEText(corpo, 'html', 'utf-8'))
        
        # Adicionar anexos
        if anexos:
            for anexo in anexos:
                if isinstance(anexo, str) and Path(anexo).exists():
                    try:
                        with open(anexo, 'rb') as attachment:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header('Content-Disposition', f'attachment; filename= {Path(anexo).name}')
                            msg.attach(part)
                    except Exception:
                        pass  # Ignorar anexos que falhem
        
        # Conectar e enviar
        with smtplib.SMTP(servidor_smtp, porta, timeout=10) as server:
            if usar_tls:
                server.starttls()
            server.login(usuario, senha)
            
            destinatarios_completo = [destinatario] + todos_ccs
            server.send_message(msg)
        
        cc_info = f"\nCC: {', '.join(todos_ccs)}" if todos_ccs else ""
        return True, f"✅ Email enviado com sucesso!\n\nPara: {destinatario}{cc_info}\nVia: SMTP ({servidor_smtp})"
        
    except smtplib.SMTPAuthenticationError:
        usuario_masked = usuario if usuario else '(vazio)'
        senha_preview = f"{senha[:4]}...{senha[-4:]}" if senha and len(senha) > 8 else '****'
        return False, (
            f"❌ Erro de autenticação SMTP\n\n"
            f"Conta: {usuario_masked}\n"
            f"Servidor: {servidor_smtp}:{porta}\n"
            f"Senha (prévia): {senha_preview}\n\n"
            f"Dica: Verifique usuário/senha\n"
            f"Para Gmail: use senha de app (https://myaccount.google.com/apppasswords)\n"
            f"⚠️ A senha de app deve ser gerada especificamente para esta conta Google."
        )
    except smtplib.SMTPException as e:
        return False, f"❌ Erro SMTP: {str(e)}"
    except Exception as e:
        return False, f"❌ Erro ao enviar: {str(e)}"
