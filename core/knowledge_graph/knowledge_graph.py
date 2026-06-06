"""
AMRIT RESEARCH OS v3.0
core/knowledge_graph/knowledge_graph.py

Knowledge Graph:
- NetworkX based entity relationship graph
- Concept discovery
- Entity linking
- SQLite persistence for graph data
"""

import sqlite3
import os
import json


class KnowledgeGraph:

    def __init__(self, db_path: str = "data/knowledge_graph.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._nodes = {}   # node_id -> label
        self._edges = []   # list of (source, target, relation)
        self._create_tables()
        self._load_from_db()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id    TEXT PRIMARY KEY,
                label TEXT,
                type  TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                source   TEXT REFERENCES nodes(id),
                target   TEXT REFERENCES nodes(id),
                relation TEXT,
                weight   REAL DEFAULT 1.0
            )
        """)
        self.conn.commit()

    def _load_from_db(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, label FROM nodes")
        for row in cur.fetchall():
            self._nodes[row[0]] = row[1]
        cur.execute("SELECT source, target, relation FROM edges")
        for row in cur.fetchall():
            self._edges.append(tuple(row))

    # ─────────────────── Add / Query ───────────────────

    def add_node(self, node_id: str, label: str, node_type: str = "concept"):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO nodes (id, label, type) VALUES (?,?,?)",
            (node_id, label, node_type),
        )
        self.conn.commit()
        self._nodes[node_id] = label

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str = "related_to",
        weight: float = 1.0,
    ):
        # Auto-create nodes if missing
        if source not in self._nodes:
            self.add_node(source, source)
        if target not in self._nodes:
            self.add_node(target, target)

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO edges (source, target, relation, weight) VALUES (?,?,?,?)",
            (source, target, relation, weight),
        )
        self.conn.commit()
        self._edges.append((source, target, relation))

    def get_neighbors(self, node_id: str) -> list:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT target, relation FROM edges WHERE source=?", (node_id,)
        )
        return cur.fetchall()

    def build_from_hypothesis(self, hypothesis: str, domain: str = ""):
        """Automatically extract concepts from hypothesis and add to graph."""
        # Simple keyword extraction
        stop_words = {
            "are", "is", "a", "an", "the", "in", "on", "at", "to", "for",
            "of", "and", "or", "but", "with", "across", "between", "whether",
            "does", "can", "do", "be", "not", "that", "this", "there",
        }
        words = [
            w.strip("?,.'\"").lower()
            for w in hypothesis.split()
            if w.strip("?,.'\"").lower() not in stop_words and len(w) > 3
        ]

        if domain:
            self.add_node(domain, domain, "domain")

        prev = domain if domain else None
        for word in words:
            self.add_node(word, word, "concept")
            if prev:
                self.add_edge(prev, word, "related_to")
            prev = word

    def node_count(self) -> int:
        return len(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def summary(self) -> dict:
        return {
            "nodes": self.node_count(),
            "edges": self.edge_count(),
            "top_concepts": list(self._nodes.values())[:10],
        }

    def export_json(self, path: str = "reports/json/knowledge_graph.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "nodes": [
                {"id": k, "label": v} for k, v in self._nodes.items()
            ],
            "edges": [
                {"source": s, "target": t, "relation": r}
                for s, t, r in self._edges
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path
