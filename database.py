import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "cofre_mma.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servidores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cargo TEXT NOT NULL,
                departamento TEXT NOT NULL,
                nivel_permissao INTEGER NOT NULL
                    CHECK (nivel_permissao IN (1, 2, 3)),
                face_embedding BLOB,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS auditoria_acessos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                servidor_id INTEGER,
                status TEXT NOT NULL
                    CHECK (status IN ('LIBERADO', 'NEGADO')),
                motivo TEXT NOT NULL,
                score_similaridade REAL,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (servidor_id)
                    REFERENCES servidores(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS toxinas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                categoria_acesso INTEGER NOT NULL
                    CHECK (categoria_acesso IN (1, 2, 3)),
                descricao TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        toxinas_iniciais = [
            (
                "TOX-001",
                "Toxina botulínica",
                1,
                "Toxina de origem bacteriana conhecida por seus efeitos "
                "sobre a transmissão neuromuscular."
            ),
            (
                "TOX-002",
                "Ricina",
                1,
                "Substância tóxica de origem vegetal encontrada nas "
                "sementes da mamona."
            ),
            (
                "TOX-003",
                "Saxitoxina",
                2,
                "Neurotoxina associada a determinadas espécies de "
                "organismos aquáticos e a eventos de maré vermelha."
            ),
            (
                "TOX-004",
                "Tetrodotoxina",
                2,
                "Neurotoxina encontrada em algumas espécies de animais "
                "marinhos e conhecida por seus efeitos no sistema nervoso."
            ),
            (
                "TOX-005",
                "Xênon-Delta",
                3,
                "Substância fictícia de classificação restrita, criada "
                "para fins de demonstração do sistema."
            ),
            (
                "TOX-006",
                "Ômega-9",
                3,
                "Composto fictício de classificação restrita, utilizado "
                "para simular registros de acesso especial."
            ),
            (
                "TOX-007",
                "Microcistina",
                1,
                "Toxina produzida por cianobactérias, associada à "
                "contaminação de reservatórios durante florações de algas."
            ),
            (
                "TOX-008",
                "Aflatoxina",
                1,
                "Toxina produzida por fungos do gênero Aspergillus, que "
                "pode contaminar grãos e alimentos armazenados."
            ),
            (
                "TOX-009",
                "Ácido domoico",
                2,
                "Neurotoxina produzida por algumas microalgas marinhas, "
                "associada à contaminação de moluscos e peixes."
            ),
            (
                "TOX-010",
                "Brevetoxina",
                2,
                "Toxina produzida por dinoflagelados em eventos de maré "
                "vermelha, com efeitos sobre a fauna marinha."
            ),
            (
                "TOX-011",
                "Palitoxina",
                3,
                "Toxina marinha associada a corais do gênero Palythoa, "
                "de manuseio restrito."
            ),
            (
                "TOX-012",
                "Batracotoxina",
                3,
                "Alcaloide presente na pele de certas rãs da América "
                "Central e do Sul, estudado em pesquisas sobre canais iônicos."
            )
        ]

        conn.executemany("""
            INSERT OR IGNORE INTO toxinas
                (codigo, nome, categoria_acesso, descricao)
            VALUES (?, ?, ?, ?)
        """, toxinas_iniciais)

        colunas = conn.execute(
            "PRAGMA table_info(servidores)"
        ).fetchall()

        nomes_colunas = [coluna["name"] for coluna in colunas]

        if "ativo" not in nomes_colunas:
            conn.execute("""
                ALTER TABLE servidores
                ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1
            """)


def cadastrar_servidor(
    nome, cargo, departamento, nivel_permissao, face_embedding
):
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO servidores
                (nome, cargo, departamento, nivel_permissao, face_embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                nome,
                cargo,
                departamento,
                nivel_permissao,
                face_embedding,
            ),
        )
        return cursor.lastrowid

def listar_servidores_com_face():
    with get_db() as conn:
        servidores = conn.execute("""
            SELECT
                id,
                nome,
                cargo,
                departamento,
                nivel_permissao,
                face_embedding,
                ativo
            FROM servidores
            WHERE face_embedding IS NOT NULL
              AND ativo = 1
        """).fetchall()

    return servidores


def listar_servidores():
    """Lista todos os servidores, ativos e inativos."""
    with get_db() as conn:
        return conn.execute("""
            SELECT
                id, nome, cargo, departamento,
                nivel_permissao, data_cadastro, ativo
            FROM servidores
            ORDER BY nome COLLATE NOCASE
        """).fetchall()


def buscar_servidor(servidor_id):
    """Busca um servidor pelo identificador."""
    with get_db() as conn:
        return conn.execute("""
            SELECT *
            FROM servidores
            WHERE id = ?
        """, (servidor_id,)).fetchone()


def atualizar_servidor(
    servidor_id, nome, cargo, departamento, nivel_permissao
):
    """Atualiza os dados sem alterar a biometria cadastrada."""
    with get_db() as conn:
        cursor = conn.execute("""
            UPDATE servidores
            SET nome = ?,
                cargo = ?,
                departamento = ?,
                nivel_permissao = ?
            WHERE id = ?
        """, (
            nome,
            cargo,
            departamento,
            nivel_permissao,
            servidor_id
        ))

        return cursor.rowcount > 0


def desativar_servidor(servidor_id):
    """Desativa o cadastro sem apagar seu histórico."""
    with get_db() as conn:
        cursor = conn.execute("""
            UPDATE servidores
            SET ativo = 0
            WHERE id = ? AND ativo = 1
        """, (servidor_id,))

        return cursor.rowcount > 0


def reativar_servidor(servidor_id):
    """Reativa um cadastro existente."""
    with get_db() as conn:
        cursor = conn.execute("""
            UPDATE servidores
            SET ativo = 1
            WHERE id = ? AND ativo = 0
        """, (servidor_id,))

        return cursor.rowcount > 0


def excluir_servidor_definitivamente(servidor_id):
    """
    Exclui permanentemente somente se não houver
    registros de auditoria vinculados ao servidor.
    """
    with get_db() as conn:
        auditoria = conn.execute("""
            SELECT 1
            FROM auditoria_acessos
            WHERE servidor_id = ?
            LIMIT 1
        """, (servidor_id,)).fetchone()

        if auditoria:
            return False

        cursor = conn.execute("""
            DELETE FROM servidores
            WHERE id = ?
        """, (servidor_id,))

        return cursor.rowcount > 0


if __name__ == "__main__":
    init_db()
    print("Banco de dados inicializado com sucesso!")


def registrar_auditoria(servidor_id, status, motivo, score_similaridade=None):
    """Registra uma tentativa de acesso no histórico."""
    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO auditoria_acessos
                (servidor_id, status, motivo, score_similaridade)
            VALUES (?, ?, ?, ?)
            """,
            (servidor_id, status, motivo, score_similaridade)
        )
        conn.commit()
    finally:
        conn.close()


def listar_auditoria():
    """Retorna o histórico de acessos, do mais recente ao mais antigo."""
    conn = get_db()

    try:
        registros = conn.execute(
            """
            SELECT
                a.id,
                a.data_hora,
                a.status,
                a.motivo,
                a.score_similaridade,
                COALESCE(s.nome, 'Não identificado') AS nome_servidor,
                s.cargo,
                s.nivel_permissao
            FROM auditoria_acessos AS a
            LEFT JOIN servidores AS s
                ON a.servidor_id = s.id
            ORDER BY a.data_hora DESC, a.id DESC
            """
        ).fetchall()

        return registros
    finally:
        conn.close()


def listar_toxinas_autorizadas(nivel_permissao):
    """
    Lista as toxinas ativas autorizadas para determinado nível.
    Níveis superiores também podem acessar categorias inferiores.
    """
    if nivel_permissao not in (1, 2, 3):
        return []

    with get_db() as conn:
        return conn.execute("""
            SELECT
                id,
                codigo,
                nome,
                categoria_acesso,
                descricao
            FROM toxinas
            WHERE ativo = 1
              AND categoria_acesso <= ?
            ORDER BY codigo
        """, (nivel_permissao,)).fetchall()