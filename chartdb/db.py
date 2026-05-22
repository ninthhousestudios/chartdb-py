import sqlite3
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

from .vectors import VectorSchema, DEFAULT_SCHEMA, extract_vector
from .properties import SCHEMA_SQL as PROPS_SCHEMA_SQL, extract_properties


class ChartDB:

    def __init__(self, db_path: str | Path, schema: VectorSchema | None = None):
        self.db_path = Path(db_path)
        self.schema = schema or DEFAULT_SCHEMA
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma journal_mode=wal")
        self.conn.execute("pragma foreign_keys=on")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            create table if not exists charts (
                id          text primary key,
                jd          real not null,
                lat         real not null,
                lon         real not null,
                alt         real,
                name        text not null,
                gender      text,
                placename   text,
                country     text,
                utc_offset  real not null,
                notes       text,
                source_path text,
                created_at  text not null,
                updated_at  text not null,
                unique(jd, lat, lon)
            );

            create table if not exists collections (
                id   text primary key,
                name text not null unique,
                note text
            );

            create table if not exists chart_collections (
                chart_id      text not null references charts(id) on delete cascade,
                collection_id text not null references collections(id) on delete cascade,
                primary key (chart_id, collection_id)
            );

            create table if not exists chart_tags (
                chart_id text not null references charts(id) on delete cascade,
                tag      text not null,
                primary key (chart_id, tag)
            );

            create index if not exists idx_chart_tags_tag on chart_tags(tag);

            create table if not exists vector_schema (
                id   text primary key,
                spec text not null,
                dims integer not null
            );

            create table if not exists chart_vectors (
                chart_id text not null references charts(id) on delete cascade,
                vector   blob not null,
                primary key (chart_id)
            );
        """)
        self.conn.executescript(PROPS_SCHEMA_SQL)
        self._init_fts()
        self._store_schema()
        self.conn.commit()

    def _init_fts(self):
        self.conn.execute("""
            create virtual table if not exists charts_fts using fts5(
                name, placename, country, notes,
                content='charts', content_rowid='rowid'
            )
        """)
        # sync triggers
        for sql in [
            """create trigger if not exists charts_ai after insert on charts begin
                insert into charts_fts(rowid, name, placename, country, notes)
                values (new.rowid, new.name, new.placename, new.country, new.notes);
            end""",
            """create trigger if not exists charts_ad after delete on charts begin
                insert into charts_fts(charts_fts, rowid, name, placename, country, notes)
                values ('delete', old.rowid, old.name, old.placename, old.country, old.notes);
            end""",
            """create trigger if not exists charts_au after update on charts begin
                insert into charts_fts(charts_fts, rowid, name, placename, country, notes)
                values ('delete', old.rowid, old.name, old.placename, old.country, old.notes);
                insert into charts_fts(rowid, name, placename, country, notes)
                values (new.rowid, new.name, new.placename, new.country, new.notes);
            end""",
        ]:
            self.conn.execute(sql)

    def _store_schema(self):
        schema_id = self.schema.content_hash()
        existing = self.conn.execute(
            "select id from vector_schema where id = ?", (schema_id,)
        ).fetchone()
        if not existing:
            self.conn.execute(
                "insert into vector_schema (id, spec, dims) values (?, ?, ?)",
                (schema_id, json.dumps(self.schema.to_dict()), self.schema.dims()),
            )

    # -- chart CRUD --

    def insert_chart(self, context, source_path: str | None = None, tags: list[str] | None = None) -> str:
        """Insert a chart from a libaditya EphContext. Returns the chart id."""
        from libaditya.charts import Chart

        jd = context.timeJD.jd_number() if hasattr(context.timeJD, 'jd_number') else context.timeJD.jd
        lat = context.location.lat
        lon = context.location.long
        placename = context.location.placename() if callable(context.location.placename) else context.location.placename

        existing = self.conn.execute(
            "select id from charts where jd = ? and lat = ? and lon = ?",
            (jd, lat, lon),
        ).fetchone()
        if existing:
            return existing["id"]

        chart_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """insert into charts (id, jd, lat, lon, alt, name, placename, utc_offset, source_path, created_at, updated_at)
               values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chart_id, jd, lat, lon, context.location.alt, context.name, placename,
             context.timeJD.utcoffset, source_path, now, now),
        )

        if tags:
            for tag in tags:
                self.conn.execute(
                    "insert or ignore into chart_tags (chart_id, tag) values (?, ?)",
                    (chart_id, tag),
                )

        chart = Chart(context)
        vec = extract_vector(chart, self.schema)
        self.conn.execute(
            "insert into chart_vectors (chart_id, vector) values (?, ?)",
            (chart_id, vec.tobytes()),
        )

        props = extract_properties(chart)
        self.conn.executemany(
            "insert into chart_properties (chart_id, subject, property, value) values (?, ?, ?, ?)",
            [(chart_id, subj, prop, val) for subj, prop, val in props],
        )

        self.conn.commit()
        return chart_id

    def import_chtk(self, path: str | Path, tags: list[str] | None = None) -> str:
        """Import a .chtk file. Returns the chart id."""
        from libaditya import read
        ctx = read.chtk_to_context(str(path))
        return self.insert_chart(ctx, source_path=str(path), tags=tags)

    def import_directory(self, directory: str | Path, tags: list[str] | None = None) -> list[str]:
        """Import all .chtk files from a directory. Returns list of chart ids."""
        directory = Path(directory)
        ids = []
        for f in sorted(directory.glob("*.chtk")):
            try:
                chart_id = self.import_chtk(f, tags=tags)
                ids.append(chart_id)
            except Exception as e:
                print(f"skipping {f.name}: {e}")
        return ids

    def get_chart(self, chart_id: str) -> dict | None:
        row = self.conn.execute("select * from charts where id = ?", (chart_id,)).fetchone()
        if row:
            d = dict(row)
            d["tags"] = [r["tag"] for r in self.conn.execute(
                "select tag from chart_tags where chart_id = ?", (chart_id,)
            )]
            return d
        return None

    def list_charts(self) -> list[dict]:
        rows = self.conn.execute("select * from charts order by name").fetchall()
        return [dict(r) for r in rows]

    def delete_chart(self, chart_id: str):
        self.conn.execute("delete from charts where id = ?", (chart_id,))
        self.conn.commit()

    # -- tags --

    def add_tag(self, chart_id: str, tag: str):
        self.conn.execute(
            "insert or ignore into chart_tags (chart_id, tag) values (?, ?)",
            (chart_id, tag),
        )
        self.conn.commit()

    def remove_tag(self, chart_id: str, tag: str):
        self.conn.execute(
            "delete from chart_tags where chart_id = ? and tag = ?",
            (chart_id, tag),
        )
        self.conn.commit()

    # -- collections --

    def create_collection(self, name: str, note: str | None = None) -> str:
        cid = str(uuid.uuid4())
        self.conn.execute(
            "insert into collections (id, name, note) values (?, ?, ?)",
            (cid, name, note),
        )
        self.conn.commit()
        return cid

    def add_to_collection(self, chart_id: str, collection_id: str):
        self.conn.execute(
            "insert or ignore into chart_collections (chart_id, collection_id) values (?, ?)",
            (chart_id, collection_id),
        )
        self.conn.commit()

    def list_collections(self) -> list[dict]:
        rows = self.conn.execute("""
            select c.*, count(cc.chart_id) as chart_count
            from collections c
            left join chart_collections cc on c.id = cc.collection_id
            group by c.id
            order by c.name
        """).fetchall()
        return [dict(r) for r in rows]

    # -- search --

    def search(self, query: str) -> list[dict]:
        """Full-text search across name, placename, country, notes."""
        rows = self.conn.execute("""
            select c.* from charts c
            join charts_fts f on c.rowid = f.rowid
            where charts_fts match ?
            order by rank
        """, (query,)).fetchall()
        return [dict(r) for r in rows]

    def filter_by_properties(self, filters: list[tuple[str, str, str]]) -> list[dict]:
        """Filter charts by property matches. Each filter is (subject, property, value).
        Returns charts matching ALL filters (intersection)."""
        if not filters:
            return self.list_charts()

        # intersect chart_ids across all filters
        sets = []
        for subject, prop, value in filters:
            rows = self.conn.execute(
                "select chart_id from chart_properties where subject = ? and property = ? and value = ?",
                (subject, prop, value),
            ).fetchall()
            sets.append({r["chart_id"] for r in rows})

        matching_ids = sets[0]
        for s in sets[1:]:
            matching_ids &= s

        if not matching_ids:
            return []

        placeholders = ",".join("?" * len(matching_ids))
        rows = self.conn.execute(
            f"select * from charts where id in ({placeholders}) order by name",
            list(matching_ids),
        ).fetchall()
        return [dict(r) for r in rows]

    def filter_then_similar(
        self, chart_id: str, filters: list[tuple[str, str, str]], n: int = 10, weights: np.ndarray | None = None
    ) -> list[tuple[dict, float]]:
        """Filter by properties first, then rank the filtered set by vector similarity."""
        row = self.conn.execute(
            "select vector from chart_vectors where chart_id = ?", (chart_id,)
        ).fetchone()
        if not row:
            return []
        query_vec = np.frombuffer(row["vector"], dtype=np.float64)

        if filters:
            candidates = self.filter_by_properties(filters)
            candidate_ids = {c["id"] for c in candidates} - {chart_id}
        else:
            candidate_ids = None

        rows = self.conn.execute("select chart_id, vector from chart_vectors").fetchall()
        results = []
        for r in rows:
            cid = r["chart_id"]
            if cid == chart_id:
                continue
            if candidate_ids is not None and cid not in candidate_ids:
                continue
            vec = np.frombuffer(r["vector"], dtype=np.float64)
            dist = _cosine_distance(query_vec, vec, weights)
            results.append((cid, dist))

        results.sort(key=lambda x: x[1])
        out = []
        for cid, dist in results[:n]:
            chart = self.get_chart(cid)
            if chart:
                out.append((chart, dist))
        return out

    def get_chart_properties(self, chart_id: str) -> list[dict]:
        """Get all properties for a chart."""
        rows = self.conn.execute(
            "select subject, property, value from chart_properties where chart_id = ? order by subject, property",
            (chart_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_property_values(self, property: str, subject: str | None = None) -> list[str]:
        """List distinct values for a property, optionally filtered by subject."""
        if subject:
            rows = self.conn.execute(
                "select distinct value from chart_properties where property = ? and subject = ? order by value",
                (property, subject),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "select distinct value from chart_properties where property = ? order by value",
                (property,),
            ).fetchall()
        return [r["value"] for r in rows]

    def similar(self, chart_id: str, n: int = 10, weights: np.ndarray | None = None) -> list[tuple[dict, float]]:
        """Find the n most similar charts to the given chart by vector distance."""
        row = self.conn.execute(
            "select vector from chart_vectors where chart_id = ?", (chart_id,)
        ).fetchone()
        if not row:
            return []

        query_vec = np.frombuffer(row["vector"], dtype=np.float64)
        return self._similar_by_vector(query_vec, n, weights, exclude_id=chart_id)

    def _similar_by_vector(
        self, query_vec: np.ndarray, n: int, weights: np.ndarray | None, exclude_id: str | None = None
    ) -> list[tuple[dict, float]]:
        rows = self.conn.execute("select chart_id, vector from chart_vectors").fetchall()
        results = []
        for r in rows:
            if r["chart_id"] == exclude_id:
                continue
            vec = np.frombuffer(r["vector"], dtype=np.float64)
            dist = _cosine_distance(query_vec, vec, weights)
            results.append((r["chart_id"], dist))

        results.sort(key=lambda x: x[1])
        out = []
        for cid, dist in results[:n]:
            chart = self.get_chart(cid)
            if chart:
                out.append((chart, dist))
        return out

    # -- rebuild --

    def _reconstruct_chart(self, row):
        from libaditya.charts import Chart
        from libaditya.objects import EphContext, JulianDay, Location
        jd = JulianDay(row["jd"], row["utc_offset"])
        loc = Location(row["lat"], row["lon"], row["alt"] or 0, row["placename"] or "", row["utc_offset"])
        ctx = EphContext(name=row["name"], timeJD=jd, location=loc)
        return Chart(ctx)

    def rebuild_vectors(self):
        """Recompute all vectors using the current schema."""
        rows = self.conn.execute("select * from charts").fetchall()
        self.conn.execute("delete from chart_vectors")
        for r in rows:
            chart = self._reconstruct_chart(r)
            vec = extract_vector(chart, self.schema)
            self.conn.execute(
                "insert into chart_vectors (chart_id, vector) values (?, ?)",
                (r["id"], vec.tobytes()),
            )
        self._store_schema()
        self.conn.commit()

    def rebuild_properties(self):
        """Recompute all chart properties."""
        rows = self.conn.execute("select * from charts").fetchall()
        self.conn.execute("delete from chart_properties")
        for r in rows:
            chart = self._reconstruct_chart(r)
            props = extract_properties(chart)
            self.conn.executemany(
                "insert into chart_properties (chart_id, subject, property, value) values (?, ?, ?, ?)",
                [(r["id"], subj, prop, val) for subj, prop, val in props],
            )
        self.conn.commit()

    def rebuild_all(self):
        """Recompute both vectors and properties for all charts."""
        rows = self.conn.execute("select * from charts").fetchall()
        self.conn.execute("delete from chart_vectors")
        self.conn.execute("delete from chart_properties")
        for r in rows:
            chart = self._reconstruct_chart(r)
            vec = extract_vector(chart, self.schema)
            self.conn.execute(
                "insert into chart_vectors (chart_id, vector) values (?, ?)",
                (r["id"], vec.tobytes()),
            )
            props = extract_properties(chart)
            self.conn.executemany(
                "insert into chart_properties (chart_id, subject, property, value) values (?, ?, ?, ?)",
                [(r["id"], subj, prop, val) for subj, prop, val in props],
            )
        self._store_schema()
        self.conn.commit()

    def close(self):
        self.conn.close()


def _cosine_distance(a: np.ndarray, b: np.ndarray, weights: np.ndarray | None = None) -> float:
    if weights is not None:
        a = a * weights
        b = b * weights
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)
