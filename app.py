import base64
import binascii
import cv2
import numpy as np
import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)
from database import (
    init_db,
    cadastrar_servidor,
    listar_servidores_com_face,
    registrar_auditoria,
    listar_auditoria,
    buscar_servidor,
    listar_servidores,
    atualizar_servidor,
    desativar_servidor,
    reativar_servidor,
    excluir_servidor_definitivamente,
    listar_toxinas_autorizadas,
)
from face_engine import FaceEngine
from datetime import timedelta
from functools import wraps


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "chave-local-de-desenvolvimento")
app.permanent_session_lifetime = timedelta(minutes=20)

init_db()
face_engine = FaceEngine()


DESTINOS_ADMIN = ("cadastro", "logs", "gerenciamento_servidores")


def exige_nivel_3(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        servidor_id = session.get("servidor_admin_id")
        servidor = buscar_servidor(servidor_id) if servidor_id else None

        if not servidor_id:
            mensagem = "Faça a identificação facial para acessar esta área."
        elif (
            not servidor
            or servidor["ativo"] != 1
            or servidor["nivel_permissao"] != 3
        ):
            session.clear()
            mensagem = "Sua autorização administrativa não é mais válida."
        else:
            return func(*args, **kwargs)

        if request.method == "GET" and request.endpoint in DESTINOS_ADMIN:
            session["destino_admin"] = request.endpoint

        flash(mensagem)
        return redirect(url_for("autorizar_gerenciamento"))

    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/cadastro", methods=["GET", "POST"])
@exige_nivel_3
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html")

    nome = request.form.get("nome", "").strip()
    cargo = request.form.get("cargo", "").strip()
    departamento = request.form.get("departamento", "").strip()
    nivel = request.form.get("nivel_permissao", "").strip()
    imagem_base64 = request.form.get("imagem", "")

    if not all([nome, cargo, departamento, nivel, imagem_base64]):
        flash("Preencha todos os campos e capture uma imagem.")
        return redirect(url_for("cadastro"))

    try:
        nivel = int(nivel)

        if nivel not in (1, 2, 3):
            raise ValueError("Nível de acesso inválido.")

        if not imagem_base64.startswith("data:image/"):
            raise ValueError("Formato de imagem inválido.")

        _, conteudo = imagem_base64.split(",", 1)
        dados = base64.b64decode(conteudo, validate=True)

        if len(dados) > 5_000_000:
            raise ValueError("A imagem é muito grande.")

        imagem_array = np.frombuffer(dados, dtype=np.uint8)
        imagem = cv2.imdecode(imagem_array, cv2.IMREAD_COLOR)

        if imagem is None:
            raise ValueError("Não foi possível ler a imagem.")

        caracteristicas = face_engine.extrair_caracteristicas(imagem)
        embedding_bytes = caracteristicas.tobytes()

        cadastrar_servidor(
            nome,
            cargo,
            departamento,
            nivel,
            embedding_bytes,
        )

        flash(f"Servidor {nome} cadastrado com sucesso!")
    except (
        ValueError,
        binascii.Error,
        cv2.error,
    ) as erro:
        flash(f"Não foi possível realizar o cadastro: {erro}")
    except Exception:
        app.logger.exception("Erro inesperado ao cadastrar servidor.")
        flash("Ocorreu um erro inesperado. Confira o terminal.")

    return redirect(url_for("cadastro"))



@app.route("/reconhecimento", methods=["GET", "POST"])
def reconhecimento():

    if request.method == "GET":
        return render_template("reconhecimento.html")

    destino = (
        "index"
        if request.form.get("origem") == "inicio"
        else "reconhecimento"
    )

    imagem_base64 = request.form.get("imagem", "")
    servidor_id = None
    score = None
    registro_feito = False

    try:

        if not imagem_base64:
            registrar_auditoria(
                None, "NEGADO",
                "Nenhuma imagem foi enviada."
            )
            registro_feito = True
            flash("Capture uma imagem antes de iniciar o reconhecimento.")
            return redirect(url_for(destino))

        if not imagem_base64.startswith("data:image/"):
            raise ValueError("Formato de imagem inválido.")

        _, conteudo = imagem_base64.split(",", 1)
        dados = base64.b64decode(conteudo, validate=True)

        if len(dados) > 5_000_000:
            raise ValueError("A imagem enviada é muito grande.")

        imagem_array = np.frombuffer(dados, dtype=np.uint8)
        imagem = cv2.imdecode(imagem_array, cv2.IMREAD_COLOR)

        if imagem is None:
            raise ValueError("Não foi possível ler a imagem.")

        servidores = listar_servidores_com_face()

        if not servidores:
            registrar_auditoria(
                None, "NEGADO",
                "Não existem servidores com biometria cadastrada."
            )
            registro_feito = True
            flash("Nenhum servidor com biometria cadastrada.")
            return redirect(url_for(destino))

        servidor, score = face_engine.reconhecer(
            imagem, servidores
        )

        if servidor is not None:

            servidor_id = servidor["id"]
            nome = servidor["nome"]

            servidor_atual = buscar_servidor(servidor_id)

            if not servidor_atual or servidor_atual["ativo"] != 1:

                session.pop("servidor_id", None)

                registrar_auditoria(
                    servidor_id,
                    "NEGADO",
                    "Tentativa de acesso por servidor inativo.",
                    float(score),
                )
                registro_feito = True

                flash("Acesso negado: servidor inativo.")

            else:

                session["servidor_id"] = servidor_id
                session.permanent = True

                registrar_auditoria(
                    servidor_id,
                    "LIBERADO",
                    "Identificação facial e autorização realizadas com sucesso.",
                    float(score),
                )
                registro_feito = True

                flash(
                    f"Identificação realizada com sucesso! "
                    f"Bem-vindo(a), {nome}."
                )

                return redirect(url_for("toxinas"))

        else:

            session.pop("servidor_id", None)

            registrar_auditoria(
                None,
                "NEGADO",
                "Rosto não reconhecido.",
                float(score) if score is not None else None,
            )
            registro_feito = True

            flash("Acesso negado: rosto não reconhecido.")

    except (ValueError, binascii.Error, cv2.error) as erro:

        if not registro_feito:
            registrar_auditoria(
                servidor_id,
                "NEGADO",
                f"Falha no reconhecimento: {erro}",
                float(score) if score is not None else None,
            )

        flash(f"Não foi possível reconhecer o rosto: {erro}")

    except Exception:

        app.logger.exception("Erro durante o reconhecimento facial.")

        if not registro_feito:
            registrar_auditoria(
                servidor_id,
                "NEGADO",
                "Erro interno durante o reconhecimento facial.",
                float(score) if score is not None else None,
            )

        flash("Ocorreu um erro inesperado no reconhecimento.")

    return redirect(url_for(destino))


@app.route("/gerenciamento/autorizar", methods=["GET", "POST"])
def autorizar_gerenciamento():

    if request.method == "GET":
        return render_template("autorizar_gerenciamento.html")

    imagem_base64 = request.form.get("imagem", "")
    servidor_id = None
    score = None

    try:
        if not imagem_base64:
            registrar_auditoria(
                None,
                "NEGADO",
                "Tentativa de gerenciamento sem imagem."
            )
            flash("Capture uma imagem antes de continuar.")
            return redirect(url_for("autorizar_gerenciamento"))

        if not imagem_base64.startswith("data:image/"):
            raise ValueError("Formato de imagem inválido.")

        _, conteudo = imagem_base64.split(",", 1)
        dados = base64.b64decode(conteudo, validate=True)

        if len(dados) > 5_000_000:
            raise ValueError("A imagem é muito grande.")

        imagem_array = np.frombuffer(dados, dtype=np.uint8)
        imagem = cv2.imdecode(imagem_array, cv2.IMREAD_COLOR)

        if imagem is None:
            raise ValueError("Não foi possível ler a imagem.")

        servidores = listar_servidores_com_face()

        if not servidores:
            registrar_auditoria(
                None,
                "NEGADO",
                "Não existem servidores ativos com biometria cadastrada."
            )
            flash("Nenhum servidor com biometria ativa foi encontrado.")
            return redirect(url_for("autorizar_gerenciamento"))

        servidor, score = face_engine.reconhecer(
            imagem,
            servidores
        )

        if servidor is None:
            registrar_auditoria(
                None,
                "NEGADO",
                "Rosto não reconhecido na tentativa de acesso administrativo.",
                float(score) if score is not None else None
            )
            flash("Acesso negado: servidor não reconhecido.")
            return redirect(url_for("autorizar_gerenciamento"))

        servidor_id = servidor["id"]
        nome = servidor["nome"]
        nivel = servidor["nivel_permissao"]

        if nivel != 3:
            registrar_auditoria(
                servidor_id,
                "NEGADO",
                "Servidor identificado, mas sem permissão de gerenciamento. Nível 3 exigido.",
                float(score)
            )
            flash(
                f"Acesso negado, {nome}. "
                "Somente servidores de Nível 3 podem gerenciar cadastros."
            )
            return redirect(url_for("autorizar_gerenciamento"))

        session["servidor_admin_id"] = servidor_id
        session["servidor_admin_nome"] = nome
        session.permanent = True

        registrar_auditoria(
            servidor_id,
            "LIBERADO",
            "Acesso ao gerenciamento de cadastros autorizado para servidor de Nível 3.",
            float(score)
        )

        flash(f"Autorização concedida. Bem-vindo(a), {nome}!")
        return redirect(url_for("gerenciamento_servidores"))

    except (ValueError, binascii.Error, cv2.error) as erro:
        registrar_auditoria(
            servidor_id,
            "NEGADO",
            f"Falha na autorização administrativa: {erro}",
            float(score) if score is not None else None
        )
        flash(f"Não foi possível validar a imagem: {erro}")

    except Exception:
        app.logger.exception("Erro na autorização administrativa.")

        registrar_auditoria(
            servidor_id,
            "NEGADO",
            "Erro interno durante a autorização administrativa.",
            float(score) if score is not None else None
        )

        flash("Ocorreu um erro inesperado. Confira o terminal.")

    return redirect(url_for("autorizar_gerenciamento"))


@app.route("/toxinas")
def toxinas():

    servidor_id = session.get("servidor_id")

    if not servidor_id:
        flash("Realize o reconhecimento facial para acessar o sistema.")
        return redirect(url_for("index"))

    servidor = buscar_servidor(servidor_id)

    if not servidor or servidor["ativo"] != 1:
        session.pop("servidor_id", None)
        flash("Acesso negado: servidor não autorizado ou inativo.")
        return redirect(url_for("index"))

    toxinas = listar_toxinas_autorizadas(
        servidor["nivel_permissao"]
    )

    return render_template(
        "toxinas.html",
        servidor=servidor,
        toxinas=toxinas
    )


@app.route("/logs")
@exige_nivel_3
def logs():
    registros = listar_auditoria()
    return render_template("logs.html", registros=registros)


@app.route("/gerenciamento/servidores")
@exige_nivel_3
def gerenciamento_servidores():
    servidores = listar_servidores()

    return render_template(
        "servidores.html",
        servidores=servidores
    )


@app.route("/gerenciamento/servidores/editar/<int:servidor_id>", methods=["GET", "POST"])
@exige_nivel_3
def editar_servidor(servidor_id):
    servidor = buscar_servidor(servidor_id)

    if not servidor:
        flash("Servidor não encontrado.")
        return redirect(url_for("gerenciamento_servidores"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cargo = request.form.get("cargo", "").strip()
        departamento = request.form.get("departamento", "").strip()

        try:
            nivel = int(request.form.get("nivel_permissao", ""))

            if not nome or not cargo or not departamento:
                raise ValueError

            if nivel not in (1, 2, 3):
                raise ValueError

        except ValueError:
            flash("Preencha todos os campos corretamente.")
            return render_template("editar_servidor.html", servidor=servidor)

        if servidor_id == session.get("servidor_admin_id") and nivel != 3:
            flash("Você não pode reduzir o seu próprio nível de permissão.")
            return render_template("editar_servidor.html", servidor=servidor)

        sucesso = atualizar_servidor(servidor_id, nome, cargo, departamento, nivel)

        if sucesso:
            registrar_auditoria(
                session.get("servidor_admin_id"),
                "LIBERADO",
                f"Administrador editou os dados do servidor ID {servidor_id}."
            )
            flash("Dados do servidor atualizados com sucesso!")
        else:
            registrar_auditoria(
                session.get("servidor_admin_id"),
                "NEGADO",
                f"Falha ao editar o servidor ID {servidor_id}."
            )
            flash("Não foi possível atualizar os dados do servidor.")

        return redirect(url_for("gerenciamento_servidores"))

    return render_template("editar_servidor.html", servidor=servidor)


@app.route("/gerenciamento/servidores/desativar/<int:servidor_id>", methods=["POST"])
@exige_nivel_3
def rota_desativar_servidor(servidor_id):

    if servidor_id == session.get("servidor_admin_id"):
        flash("Não é permitido desativar o próprio cadastro durante a sessão administrativa.")
        return redirect(url_for("gerenciamento_servidores"))

    sucesso = desativar_servidor(servidor_id)

    if sucesso:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "LIBERADO",
            f"Administrador desativou o servidor ID {servidor_id}."
        )

        flash("Servidor desativado com sucesso!")

    else:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "NEGADO",
            f"Falha ao desativar o servidor ID {servidor_id}."
        )

        flash("Não foi possível desativar o servidor.")

    return redirect(url_for("gerenciamento_servidores"))


@app.route("/gerenciamento/servidores/reativar/<int:servidor_id>", methods=["POST"])
@exige_nivel_3
def rota_reativar_servidor(servidor_id):

    sucesso = reativar_servidor(servidor_id)

    if sucesso:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "LIBERADO",
            f"Administrador reativou o servidor ID {servidor_id}."
        )

        flash("Servidor reativado com sucesso!")

    else:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "NEGADO",
            f"Falha ao reativar o servidor ID {servidor_id}."
        )

        flash("Não foi possível reativar o servidor.")

    return redirect(url_for("gerenciamento_servidores"))


@app.route("/gerenciamento/servidores/excluir/<int:servidor_id>", methods=["POST"])
@exige_nivel_3
def rota_excluir_servidor(servidor_id):

    if servidor_id == session.get("servidor_admin_id"):
        flash("Não é permitido excluir o próprio cadastro durante a sessão administrativa.")
        return redirect(url_for("gerenciamento_servidores"))

    sucesso = excluir_servidor_definitivamente(servidor_id)

    if sucesso:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "LIBERADO",
            f"Administrador excluiu definitivamente o servidor ID {servidor_id}."
        )

        flash("Servidor excluído definitivamente com sucesso!")

    else:
        registrar_auditoria(
            session.get("servidor_admin_id"),
            "NEGADO",
            f"Exclusão do servidor ID {servidor_id} bloqueada. "
            "O servidor pode possuir registros de auditoria."
        )

        flash(
            "Não foi possível excluir o servidor. "
            "Verifique se ele possui registros de auditoria."
        )

    return redirect(url_for("gerenciamento_servidores"))


@app.route("/gerenciamento/sair")
def sair_gerenciamento():
    session.clear()

    flash("Sessão administrativa encerrada.")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)