"""Modelos de persistencia.

Importar ambos aquí garantiza que la metadata declarativa conoce las dos tablas antes
de que SQLAlchemy configure los mapeadores. Sin esto, la relación `Usuario.pistas`
—que nombra a `Pista` como cadena— falla al resolverse si el proceso solo importó uno
de los dos módulos.
"""

from app.models.pista import Pista
from app.models.usuario import Usuario

__all__ = ["Pista", "Usuario"]
