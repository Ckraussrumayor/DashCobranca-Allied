"""Utilitários compartilhados entre os módulos do Dashboard Allied."""
import sys
from pathlib import Path


def get_base_path() -> Path:
    """
    Retorna o diretório base onde o aplicativo está sendo executado.
    Funciona para: script Python, executável PyInstaller e Python embarcado.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.resolve()


BASE_DIR = get_base_path()
