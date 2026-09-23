"""Rutas de pistas.

Artículo I.1: el router recibe la petición, delega en `app/services/pistas.py` y traduce
el resultado o la excepción de dominio a HTTP. No compara anchos, no conoce la ecuación y
no decide nada de la norma.
Artículo IV.4: el propietario sale de `get_current_user`, nunca de la ruta, el cuerpo o un
query param.
Artículo V.1: los códigos son los de `contracts/rest-api.md`: 201 al crear, 400 para
error de regla de negocio conocido, 401 sin token y 422 para error de schema.

En esta tarea (T025) se implementa `POST /pistas/`. `POST /pistas/calculo` llega en T029
y el resto del CRUD en T036.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, get_pistas_repo
from app.repositories.pistas import PistasRepo
from app.schemas.pista import PistaCreate, PistaOut
from app.services import pistas as servicio_pistas
from app.services.errores import AnchoInsuficienteError, FueraDeRangoError

router = APIRouter(prefix="/pistas", tags=["pistas"])


@router.post("/", response_model=PistaOut, status_code=status.HTTP_201_CREATED)
def registrar(
    datos: PistaCreate,
    usuario: Annotated[Any, Depends(get_current_user)],
    repo: Annotated[PistasRepo, Depends(get_pistas_repo)],
) -> PistaOut:
    """Registra una pista del usuario autenticado, si cumple la norma.

    `AnchoInsuficienteError` (R1) y `FueraDeRangoError` (R2) son errores de regla de
    negocio conocidos y se traducen a 400 con su detalle, no a 422: el schema ya validó
    la forma de los datos y lo que falla aquí es la norma.
    """
    try:
        pista = servicio_pistas.registrar_pista(datos, usuario.id, repo=repo)
    except (AnchoInsuficienteError, FueraDeRangoError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return PistaOut.model_validate(pista)
