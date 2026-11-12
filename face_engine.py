from pathlib import Path
import cv2
import numpy as np


PASTA_MODELOS = Path(__file__).resolve().parent / "models"

MODELO_DETECCAO = PASTA_MODELOS / "face_detection_yunet_2023mar.onnx"
MODELO_RECONHECIMENTO = (
    PASTA_MODELOS / "face_recognition_sface_2021dec.onnx"
)


class FaceEngine:
    def __init__(self):
        if not MODELO_DETECCAO.is_file():
            raise FileNotFoundError(
                f"Modelo YuNet não encontrado: {MODELO_DETECCAO}"
            )

        if not MODELO_RECONHECIMENTO.is_file():
            raise FileNotFoundError(
                f"Modelo SFace não encontrado: {MODELO_RECONHECIMENTO}"
            )

        self.detector = cv2.FaceDetectorYN.create(
            str(MODELO_DETECCAO),
            "",
            (320, 320),
            0.9,
            0.3,
            5000
        )

        self.reconhecedor = cv2.FaceRecognizerSF.create(
            str(MODELO_RECONHECIMENTO),
            ""
        )
         
    def extrair_caracteristicas(self, imagem):
        if imagem is None or imagem.size == 0:
            raise ValueError("A imagem está vazia ou é inválida.")

        altura, largura = imagem.shape[:2]

        self.detector.setInputSize((largura, altura))
        _, rostos = self.detector.detect(imagem)

        if rostos is None or len(rostos) == 0:
            raise ValueError(
                "Nenhum rosto foi detectado. "
                "Posicione seu rosto em frente à câmera."
            )

        if len(rostos) > 1:
            raise ValueError(
                "Mais de um rosto foi detectado. "
                "Deixe apenas uma pessoa na imagem."
            )

        rosto_alinhado = self.reconhecedor.alignCrop(
            imagem, rostos[0]
        )

        caracteristicas = self.reconhecedor.feature(rosto_alinhado)

        return caracteristicas.astype(np.float32)

    def comparar(self, caracteristicas_a, caracteristicas_b):
        similaridade = self.reconhecedor.match(
            caracteristicas_a,
            caracteristicas_b,
            cv2.FaceRecognizerSF_FR_COSINE
        )

        return float(similaridade)

    def reconhecer(self, imagem, servidores, limite_similaridade=0.363):
        caracteristicas_capturadas = self.extrair_caracteristicas(imagem)

        melhor_servidor = None
        melhor_similaridade = -1.0

        for servidor in servidores:
            embedding_salvo = servidor["face_embedding"]

            if not embedding_salvo:
                continue

            caracteristicas_salvas = np.frombuffer(
                embedding_salvo,
                dtype=np.float32
            ).reshape(1, -1)

            similaridade = self.comparar(
                caracteristicas_capturadas,
                caracteristicas_salvas
            )

            if similaridade > melhor_similaridade:
                melhor_similaridade = similaridade
                melhor_servidor = servidor

        if melhor_servidor is not None and (
            melhor_similaridade >= limite_similaridade
        ):
            return melhor_servidor, melhor_similaridade

        return None, melhor_similaridade


if __name__ == "__main__":
    engine = FaceEngine()
    print("Modelos YuNet e SFace carregados com sucesso!")