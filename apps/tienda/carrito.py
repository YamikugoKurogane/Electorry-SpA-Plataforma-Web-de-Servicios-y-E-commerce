"""Carrito en sesión. El visitante puede armarlo sin cuenta; para pagar debe registrarse (T1)."""
from .models import Producto

MAX_POR_PRODUCTO = 50


class Carrito:
    CLAVE = "carrito"

    def __init__(self, request):
        self.session = request.session
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
        """Lista de (producto, cantidad, subtotal) con una sola consulta."""
        ids = [int(i) for i in self.items]
        productos = {p.pk: p for p in Producto.objects.filter(pk__in=ids, activo=True, categoria__activa=True)}
        resultado = []
        for pid, cantidad in self.items.items():
            p = productos.get(int(pid))
            if p:
                resultado.append({"producto": p, "cantidad": int(cantidad), "subtotal": p.precio * int(cantidad)})
        return resultado

    def total(self):
        return sum(l["subtotal"] for l in self.lineas())

    def __len__(self):
        return sum(int(c) for c in self.items.values())
