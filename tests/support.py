"""Configuração compartilhada dos testes.

Define um banco temporário antes de `main` ser importado, para não tocar no
`var/deciframe.db` de desenvolvimento.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix='deciframe-tests-')
os.environ.setdefault('DECIFRAME_DB_PATH', os.path.join(_TMP, 'deciframe.db'))
