"""Semantic embeddings (all-MiniLM-L6-v2 via fastembed/ONNX, runs locally, 384 dims).

Build all embeddings:  .venv\\Scripts\\python -m backend.engine.embeddings
"""
from functools import lru_cache

import numpy as np

from ..config import ARTIFACTS, EMBED_MODEL
from ..db import conn, fetch_all


@lru_cache(maxsize=1)
def model():
    from fastembed import TextEmbedding
    return TextEmbedding(EMBED_MODEL, cache_dir=str(ARTIFACTS / "fastembed"))


def embed(texts: list[str]) -> np.ndarray:
    """Unit-length vectors, so a dot product equals cosine similarity."""
    v = np.array(list(model().embed(texts)), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def to_pg(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def project_text(p) -> str:
    return f"{p['project_name']}. {p['industry']}. {p['project_type']}. {p['description']} Tech: {p['tech_stack']}"


def build_all():
    skills = fetch_all("""SELECT s.skill_id, s.skill_name, s.category, string_agg(a.alias, ', ') AS aliases
                          FROM skills s LEFT JOIN skill_aliases a USING (skill_id) GROUP BY s.skill_id""")
    projects = fetch_all("SELECT project_id, project_name, industry, project_type, description, tech_stack FROM projects")
    people = fetch_all("""SELECT e.employee_id, e.designation, e.primary_skill, e.practice,
                                 string_agg(s.skill_name, ', ' ORDER BY es.proficiency DESC NULLS LAST) AS skills
                          FROM employees e JOIN employee_skills es USING (employee_id) JOIN skills s USING (skill_id)
                          WHERE e.employment_status <> 'Exited' GROUP BY e.employee_id""")
    jobs = [
        ("skill_embeddings", "skill_id", [(s["skill_id"], f"{s['skill_name']} ({s['category']}). Also known as: {s['aliases'] or '-'}") for s in skills]),
        ("project_embeddings", "project_id", [(p["project_id"], project_text(p)) for p in projects]),
        ("employee_profile_embeddings", "employee_id",
         [(e["employee_id"], f"{e['designation']} in {e['practice']}, primary skill {e['primary_skill']}. Skills: {e['skills']}") for e in people]),
    ]
    with conn() as c:
        for table, key, rows in jobs:
            vecs = embed([t for _, t in rows])
            c.execute(f"TRUNCATE {table}")
            has_text = table != "skill_embeddings"
            cols = f"{key}, model, {'source_text, ' if has_text else ''}embedding"
            with c.cursor().copy(f"COPY {table} ({cols}) FROM STDIN") as cp:
                for (k, text), v in zip(rows, vecs):
                    cp.write_row([k, EMBED_MODEL, text, to_pg(v)] if has_text else [k, EMBED_MODEL, to_pg(v)])
            print(f"  {table:30s} {len(rows):>5} vectors")


if __name__ == "__main__":
    build_all()
