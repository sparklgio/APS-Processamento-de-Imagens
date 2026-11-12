const formulario = document.querySelector("form[data-etapa]");
const video = document.getElementById("webcam");
const canvas = document.getElementById("snapshot");
const moldura = document.getElementById("cameraFrame");
const botaoCamera = document.getElementById("btnCamera");
const botaoCaptura = document.getElementById("btnCapturar");
const botaoEnviar = formulario.querySelector('button[type="submit"]');
const campoImagem = document.getElementById("imagem");
const statusCamera = document.getElementById("statusCamera");

let stream = null;

function definirEtapa(etapa) {
    formulario.dataset.etapa = etapa;
}

botaoCamera.addEventListener("click", async () => {
    try {
        statusCamera.textContent = "Solicitando acesso à câmera...";
        botaoCamera.disabled = true;

        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user" },
            audio: false
        });

        video.srcObject = stream;
        await video.play();

        moldura.classList.add("ativa");
        definirEtapa(2);
        botaoCaptura.disabled = false;
        statusCamera.textContent =
            "Câmera ativada! Posicione seu rosto no centro.";
    } catch (erro) {
        statusCamera.textContent =
            "Não foi possível ativar a câmera. Verifique as permissões do navegador.";
        console.error("Erro ao acessar a câmera:", erro);
    } finally {
        botaoCamera.disabled = false;
    }
});

botaoCaptura.addEventListener("click", () => {
    if (!video.videoWidth || !video.videoHeight) {
        statusCamera.textContent = "Aguarde a câmera iniciar antes de capturar.";
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

    campoImagem.value = canvas.toDataURL("image/jpeg", 0.9);
    botaoEnviar.disabled = false;
    definirEtapa(3);
    statusCamera.textContent = "Imagem capturada com sucesso! Agora você pode continuar.";
});

formulario.addEventListener("submit", (evento) => {
    if (!campoImagem.value) {
        evento.preventDefault();
        statusCamera.textContent = "Ative a câmera e capture uma imagem primeiro.";
        return;
    }

    const textoEnviando = formulario.dataset.textoEnviando;
    if (textoEnviando) {
        botaoEnviar.disabled = true;
        botaoEnviar.textContent = textoEnviando;
    }
});

window.addEventListener("beforeunload", () => {
    if (stream) {
        stream.getTracks().forEach((track) => track.stop());
    }
});