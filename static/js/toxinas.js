const campoBusca = document.getElementById("buscaToxina");
const cards = document.querySelectorAll(".toxina-card");
const contador = document.getElementById("contadorToxinas");
const semResultado = document.getElementById("semResultado");

function normalizar(texto) {
    return texto
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

function filtrar() {
    const termo = normalizar(campoBusca.value.trim());
    let visiveis = 0;

    cards.forEach((card) => {
        const corresponde = normalizar(card.dataset.busca).includes(termo);
        card.hidden = !corresponde;

        if (corresponde) {
            visiveis++;
        }
    });

    contador.textContent =
        `Exibindo ${visiveis} de ${cards.length} substâncias`;
    semResultado.hidden = visiveis !== 0;
}

campoBusca.addEventListener("input", filtrar);