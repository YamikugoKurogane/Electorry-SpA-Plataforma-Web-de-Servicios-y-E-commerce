"""Interfaz de pasarela de pago (D5, EC-03, S2).

Cambiar de proveedor = escribir un adaptador nuevo que implemente esta interfaz
y registrarlo en `gateways/__init__.py`. El módulo de ventas no se toca.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class PasarelaError(Exception):
    """Falla de comunicación o respuesta inválida del proveedor."""


@dataclass(frozen=True)
class OrdenPago:
    orden_compra: str  # identificador único del intento en el comercio
    monto: int  # pesos chilenos
    sesion: str


@dataclass(frozen=True)
class InicioPago:
    token: str
    url: str  # a dónde redirigir al cliente
    metodo: str = "GET"  # GET o POST (Webpay redirige con POST de formulario)
    campos: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResultadoPago:
    aprobado: bool
    referencia: str = ""
    detalle: dict = field(default_factory=dict)


class PasarelaPago(ABC):
    nombre = "base"

    @abstractmethod
    def iniciar(self, orden: OrdenPago, url_retorno: str) -> InicioPago:
        """Crea la transacción en el proveedor y devuelve cómo redirigir al cliente."""

    @abstractmethod
    def confirmar(self, token: str) -> ResultadoPago:
        """Consulta/confirma el resultado de la transacción con el proveedor."""

    @abstractmethod
    def token_desde_request(self, request) -> tuple:
        """Extrae (token, cancelado) de la petición de retorno del cliente."""
