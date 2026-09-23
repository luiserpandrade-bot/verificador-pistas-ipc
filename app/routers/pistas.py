"""Rutas de pistas.

Artículo I.1: el router recibe la petición, delega en `app/services/pistas.py` y traduce
el resultado o la excepción de dominio a HTTP. No compara anchos, no conoce la ecuación y
no decide nada de la norma.
Artículo IV.4: el propietario sale de `get_current_user`, nunca de la ruta, el cuerpo o un
query param.
Artículo V.1: los códigos son los de `contracts/rest-api.md`: 201 al crear, 400 para
error de regla de negocio conocido, 401 sin token y 422 para error de schema.

Implementados los 6 endpoints del contrato: registro, listado, lectura, actualización,
borrado y cálculo.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user, get_pistas_repo
from app.repositories.pistas import PistasRepo
from app.schemas.pista import (
    CalculoIn,
    CalculoOut,
    PaginacionParams,
    PistaCreate,
    PistaOut,
    PistaUpdate,
)
from app.services import pistas as servicio_pistas
from app.services.errores import (
    AnchoInsuficienteError,
    FueraDeRangoError,
    PistaAjenaError,
    PistaNoEncontradaError,
)

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


@router.post("/calculo", response_model=CalculoOut)
def calcular(
    datos: CalculoIn,
    usuario: Annotated[Any, Depends(get_current_user)],
) -> CalculoOut:
    """Devuelve el ancho mínimo que exige IPC-2221 para esos parámetros, sin persistir nada.

    Exige autenticación igual que el resto de `/pistas/` (FR-004), pero no toca la base de
    datos: no pide repositorio. `FueraDeRangoError` (R2) se traduce a 400.
    """
    try:
        minimo_mm = servicio_pistas.calcular_ancho_minimo(datos)
    except FueraDeRangoError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return CalculoOut(ancho_minimo_mm=minimo_mm)


def _http_de_negocio(error: Exception) -> HTTPException:
    """Traduce una excepción de dominio al código que fija `contracts/rest-api.md`.

    Artículo V.1: 400 para regla de negocio conocida, 403 para recurso ajeno identificado
    por `id` explícito y 404 para recurso inexistente. El router solo traduce; quién decide
    que la pista es ajena es el service.
    """
    if isinstance(error, PistaAjenaError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, PistaNoEncontradaError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.get("/", response_model=list[PistaOut])
def listar(
    usuario: Annotated[Any, Depends(get_current_user)],
    repo: Annotated[PistasRepo, Depends(get_pistas_repo)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PistaOut]:
    """Lista las pistas del usuario autenticado, paginadas.

    Nunca devuelve 403: filtra por el `usuario_id` del token y no acepta el de otro
    usuario (Artículo V.1, R4). Una paginación inválida es 422, no 400 (Artículo V.2).
    """
    paginacion = PaginacionParams(skip=skip, limit=limit)
    pistas = servicio_pistas.listar_pistas(
        usuario.id, skip=paginacion.skip, limit=paginacion.limit, repo=repo
    )
    return [PistaOut.model_validate(pista) for pista in pistas]


@router.get("/{pista_id}", response_model=PistaOut)
def obtener(
    pista_id: int,
    usuario: Annotated[Any, Depends(get_current_user)],
    repo: Annotated[PistasRepo, Depends(get_pistas_repo)],
) -> PistaOut:
    """Devuelve una pista propia. Ajena es 403; inexistente, 404."""
    try:
        pista = servicio_pistas.obtener_pista(pista_id, usuario.id, repo=repo)
    except (PistaAjenaError, PistaNoEncontradaError) as error:
        raise _http_de_negocio(error) from error

    return PistaOut.model_validate(pista)


@router.patch("/{pista_id}", response_model=PistaOut)
def actualizar(
    pista_id: int,
    cambios: PistaUpdate,
    usuario: Annotated[Any, Depends(get_current_user)],
    repo: Annotated[PistasRepo, Depends(get_pistas_repo)],
) -> PistaOut:
    """Actualiza una pista propia, revalidando la norma sobre el resultado (R5).

    Si el resultado quedara fuera de norma, la actualización se rechaza completa con 400 y
    la pista conserva sus valores anteriores.
    """
    try:
        pista = servicio_pistas.actualizar_pista(pista_id, cambios, usuario.id, repo=repo)
    except (
        AnchoInsuficienteError,
        FueraDeRangoError,
        PistaAjenaError,
        PistaNoEncontradaError,
    ) as error:
        raise _http_de_negocio(error) from error

    return PistaOut.model_validate(pista)


@router.delete("/{pista_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    pista_id: int,
    usuario: Annotated[Any, Depends(get_current_user)],
    repo: Annotated[PistasRepo, Depends(get_pistas_repo)],
) -> None:
    """Elimina una pista propia. Ajena es 403; inexistente, 404."""
    try:
        servicio_pistas.eliminar_pista(pista_id, usuario.id, repo=repo)
    except (PistaAjenaError, PistaNoEncontradaError) as error:
        raise _http_de_negocio(error) from error
