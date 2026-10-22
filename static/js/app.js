// Mejoras progresivas: la aplicación funciona sin JavaScript; esto solo agrega comodidad (EC-04).
(function () {
  // 1) Validación de adjuntos en el navegador (la validación real se hace en el servidor).
  var MAX = 5 * 1024 * 1024, EXT = ["jpg", "jpeg", "png", "pdf"];
  document.querySelectorAll('input[type=file][multiple]').forEach(function (input) {
    input.addEventListener("change", function () {
      var errores = [];
      Array.prototype.forEach.call(input.files, function (f) {
        var ext = f.name.split(".").pop().toLowerCase();
        if (EXT.indexOf(ext) === -1) errores.push(f.name + ": tipo no permitido");
        else if (f.size > MAX) errores.push(f.name + ": supera 5 MB");
      });
      var aviso = input.parentNode.querySelector(".js-error");
      if (!aviso) { aviso = document.createElement("div"); aviso.className = "errors js-error"; input.parentNode.appendChild(aviso); }
      aviso.textContent = errores.join(" · ");
      if (errores.length) input.value = "";
    });
  });
  // 2) Evitar doble envío de formularios.
  document.querySelectorAll("form[data-once]").forEach(function (f) {
    f.addEventListener("submit", function () {
      var b = f.querySelector("button[type=submit]"); if (b) { b.disabled = true; b.textContent = "Procesando…"; }
    });
  });
  // 3) Agregar líneas a un formset (cotizaciones).
  var add = document.getElementById("add-linea");
  if (add) {
    add.addEventListener("click", function () {
      var total = document.getElementById("id_lineas-TOTAL_FORMS"), n = parseInt(total.value, 10);
      var plantilla = document.getElementById("linea-vacia").innerHTML.replace(/__prefix__/g, n);
      document.getElementById("lineas").insertAdjacentHTML("beforeend", plantilla);
      total.value = n + 1;
    });
  }
})();
