"""
tools/knowledge_graph.py — Persistent knowledge graph (NetworkX + SQLite).
Stores entities and relationships. Supports add, query, path, export.
"""
import json
import logging
import os
import sqlite3
from contextlib import contextmanager

log = logging.getLogger(__name__)

NAME        = "knowledge_graph"
DESCRIPTION = (
    "Store and query a knowledge graph of entities and relationships. "
    "Actions: add_entity, add_relation, query, shortest_path, neighbors, stats, export"
)
CATEGORY = "memory"
ICON     = "🕸️"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [
         {"value": "add_entity",    "label": "Add entity"},
         {"value": "add_relation",  "label": "Add relationship"},
         {"value": "query",         "label": "Find entities / relations"},
         {"value": "shortest_path", "label": "Shortest path between two entities"},
         {"value": "neighbors",     "label": "Get neighbors of entity"},
         {"value": "stats",         "label": "Graph statistics"},
         {"value": "export",        "label": "Export graph JSON"},
     ], "required": True},
    {"name": "entity",       "label": "Entity name",       "type": "text", "placeholder": "Python"},
    {"name": "entity_type",  "label": "Entity type",       "type": "text", "placeholder": "language"},
    {"name": "source",       "label": "Source entity",     "type": "text", "placeholder": "Python"},
    {"name": "target",       "label": "Target entity",     "type": "text", "placeholder": "Flask"},
    {"name": "relation",     "label": "Relationship type", "type": "text", "placeholder": "used_in"},
    {"name": "query",        "label": "Search query",      "type": "text", "placeholder": "web framework"},
    {"name": "username",     "label": "Username",          "type": "text"},
]

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS kg_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                entity_type TEXT DEFAULT '',
                attributes TEXT DEFAULT '{}',
                created_at INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(username, name)
            )""")
        con.execute("""
            CREATE TABLE IF NOT EXISTS kg_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_kg_src ON kg_relations(username, source)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_kg_tgt ON kg_relations(username, target)")
        con.commit()
        yield con
        con.commit()
    finally:
        con.close()


def _build_graph(username: str):
    try:
        import networkx as nx
    except ImportError:
        return None
    G = nx.DiGraph()
    with _conn() as con:
        for row in con.execute("SELECT name, entity_type FROM kg_entities WHERE username=?", (username,)):
            G.add_node(row["name"], type=row["entity_type"])
        for row in con.execute("SELECT source, target, relation, weight FROM kg_relations WHERE username=?", (username,)):
            G.add_edge(row["source"], row["target"], relation=row["relation"], weight=row["weight"])
    return G


def run(
    action:      str = "stats",
    entity:      str = "",
    entity_type: str = "",
    source:      str = "",
    target:      str = "",
    relation:    str = "",
    query:       str = "",
    username:    str = "default",
) -> dict:
    username = username or "default"
    action   = (action or "stats").strip().lower()

    if action == "add_entity":
        if not entity:
            return {"error": "entity name required"}
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO kg_entities(username,name,entity_type) VALUES(?,?,?)",
                (username, entity.strip(), entity_type.strip())
            )
        return {"result": f"Entity '{entity}' added.", "entity": entity}

    if action == "add_relation":
        if not source or not target or not relation:
            return {"error": "source, target, and relation are all required"}
        with _conn() as con:
            # auto-add entities if missing
            for e in (source, target):
                con.execute("INSERT OR IGNORE INTO kg_entities(username,name) VALUES(?,?)", (username, e.strip()))
            con.execute(
                "INSERT INTO kg_relations(username,source,target,relation) VALUES(?,?,?,?)",
                (username, source.strip(), target.strip(), relation.strip())
            )
        return {"result": f"Relation '{source} —[{relation}]→ {target}' added."}

    if action == "query":
        if not query:
            return {"error": "query string required"}
        q = f"%{query.lower()}%"
        with _conn() as con:
            entities = [dict(r) for r in con.execute(
                "SELECT name, entity_type FROM kg_entities WHERE username=? AND (lower(name) LIKE ? OR lower(entity_type) LIKE ?)",
                (username, q, q)
            )]
            relations = [dict(r) for r in con.execute(
                "SELECT source, target, relation FROM kg_relations WHERE username=? AND (lower(source) LIKE ? OR lower(target) LIKE ? OR lower(relation) LIKE ?)",
                (username, q, q, q)
            )]
        lines = []
        if entities:
            lines.append("Entities: " + ", ".join(f"{e['name']} ({e['entity_type']})" for e in entities))
        if relations:
            lines.append("Relations: " + "; ".join(f"{r['source']} -[{r['relation']}]→ {r['target']}" for r in relations))
        return {"result": "\n".join(lines) or "No matches found.", "entities": entities, "relations": relations}

    if action == "shortest_path":
        if not source or not target:
            return {"error": "source and target required"}
        G = _build_graph(username)
        if G is None:
            return {"error": "networkx not installed. Run: pip install networkx"}
        try:
            import networkx as nx
            path = nx.shortest_path(G, source=source, target=target)
            return {"result": " → ".join(path), "path": path, "length": len(path) - 1}
        except Exception as e:
            return {"error": f"No path found: {e}"}

    if action == "neighbors":
        if not entity:
            return {"error": "entity required"}
        G = _build_graph(username)
        if G is None:
            return {"error": "networkx not installed"}
        preds = list(G.predecessors(entity))
        succs = list(G.successors(entity))
        lines = []
        if preds: lines.append(f"Incoming: {', '.join(preds)}")
        if succs: lines.append(f"Outgoing: {', '.join(succs)}")
        return {"result": "\n".join(lines) or f"No connections for '{entity}'.", "predecessors": preds, "successors": succs}

    if action == "stats":
        with _conn() as con:
            n_entities = con.execute("SELECT COUNT(*) FROM kg_entities WHERE username=?", (username,)).fetchone()[0]
            n_relations = con.execute("SELECT COUNT(*) FROM kg_relations WHERE username=?", (username,)).fetchone()[0]
        return {"result": f"Knowledge graph: {n_entities} entities, {n_relations} relationships.", "entities": n_entities, "relations": n_relations}

    if action == "export":
        with _conn() as con:
            entities  = [dict(r) for r in con.execute("SELECT name, entity_type FROM kg_entities WHERE username=?", (username,))]
            relations = [dict(r) for r in con.execute("SELECT source, target, relation FROM kg_relations WHERE username=?", (username,))]
        data = {"entities": entities, "relations": relations}
        return {"result": json.dumps(data, indent=2), **data}

    return {"error": f"Unknown action: {action}"}
