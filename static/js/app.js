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
  //    IMPORTANTE: no se deshabilita ningún botón. Un botón deshabilitado NO envía su name/value,
  //    y formularios como «Aceptar / Rechazar cotización» dependen de ese valor.
  document.querySelectorAll("form[data-once]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (f.dataset.enviando) { e.preventDefault(); return; }
      f.dataset.enviando = "1";
      f.querySelectorAll("button[type=submit]").forEach(function (b) { b.classList.add("is-busy"); });
    });
  });
  // Al volver con el botón «Atrás» el navegador restaura la página: se libera el formulario.
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-once]").forEach(function (f) {
      delete f.dataset.enviando;
      f.querySelectorAll("button[type=submit]").forEach(function (b) { b.classList.remove("is-busy"); });
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
