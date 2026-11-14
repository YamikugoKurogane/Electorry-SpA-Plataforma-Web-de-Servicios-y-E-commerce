"""Carrito en sesión. El visitante puede armarlo sin cuenta; para pagar debe registrarse (T1)."""
from apps.ofertas.services import precios_vigentes

from .models import Producto

MAX_POR_PRODUCTO = 50


class Carrito:
    CLAVE = "carrito"

    def __init__(self, request):
        self.session = request.session
        self.usuario = getattr(request, "user", None)  # las ofertas exclusivas dependen de quién mira
        self.items = self.session.get(self.CLAVE, {})

    def _guardar(self):
        self.session[self.CLAVE] = self.items
        self.session.modified = True

    def agregar(self, producto_id, cantidad=1, reemplazar=False):
        clave = str(producto_id)
        actual = 0 if reemplazar else int(self.items.get(clave, 0))
        nueva = max(0, min(MAX_POR_PRODUCTO, actual + int(cantidad)))
        if nueva == 0:
            self.items.pop(clave, None)
        else:
            self.items[clave] = nueva
        self._guardar()

    def quitar(self, producto_id):
        self.items.pop(str(producto_id), None)
        self._guardar()

    def vaciar(self):
        self.items = {}
        self._guardar()

    def lineas(self):
        """Líneas del carrito con precio vigente (con oferta si corresponde). Consultas constantes, sin N+1."""
        ids = [int(i) for i in self.items]
        productos = {p.pk: p for p in Producto.objects.filter(pk__in=ids, activo=True, categoria__activa=True)}
        precios = precios_vigentes(productos.values(), self.usuario)
        resultado = []
        for pid, cantidad in self.items.items():
            p = productos.get(int(pid))
            if p:
                pv, n = precios[p.pk], int(cantidad)
                resultado.append({
                    "producto": p, "cantidad": n, "pv": pv, "precio": pv.precio, "precio_lista": pv.precio_lista,
                    "descuento": pv.descuento, "subtotal": pv.precio * n, "ahorro": (pv.precio_lista - pv.precio) * n,
                })
        return resultado

    def ahorro(self):
        return sum(l["ahorro"] for l in self.lineas())

    def total(self):
        return sum(l["subtotal"] for l in self.lineas())

    def __len__(self):
        return sum(int(c) for c in self.items.values())
