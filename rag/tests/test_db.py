import os
import tempfile
import unittest

import rag


def _conn_or_skip():
    try:
        import psycopg
    except ImportError as e:
        raise unittest.SkipTest(f"psycopg が無い(make rag-venv が要る): {e}")
    try:
        conn = rag.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM knowledge LIMIT 1")
        conn.rollback()
        return conn
    except (RuntimeError, psycopg.Error) as e:  # DB に繋がらぬ、または表が無い
        raise unittest.SkipTest(f"DB が使えぬ(make rag-up が要る): {e}")


def fake_embed(texts):
    """決まった次元のベクトル。Ollama を使わずに、取り込みの流れを確かめる。"""
    return [[0.01 * (len(t) % 7 + 1) + i * 1e-4 for i in range(rag.EMBED_DIM)] for t in texts]


def write_docs(d, files):
    for rel, text in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()

    def count(self, project):
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowledge WHERE metadata->>'project' = %s", (project,))
            n = cur.fetchone()[0]
        self.conn.rollback()
        return n

    def test_ingest_writes_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"decisions/adr-0001-x.md": "# 題\n本文\n", "design/y.md": "# 設計\n本文\n"})
            stats = rag.ingest(self.conn, d, "unittest-a", commit="abc1234", embed_fn=fake_embed)
        self.assertEqual(stats["files"], 2)
        self.assertEqual(stats["chunks"], 2)
        self.assertEqual(stats["by_doc_type"], {"adr": 1, "design": 1})
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT metadata FROM knowledge WHERE metadata->>'project' = 'unittest-a' "
                "AND metadata->>'path' = 'decisions/adr-0001-x.md'"
            )
            meta = cur.fetchone()[0]
        self.conn.rollback()
        self.assertEqual(meta["heading"], "題")
        self.assertEqual(meta["doc_type"], "adr")
        self.assertEqual(meta["commit"], "abc1234")
        self.assertEqual(meta["model"], rag.EMBED_MODEL)

    def test_ingest_twice_keeps_count(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n", "b.md": "# B\n本文\n"})
            rag.ingest(self.conn, d, "unittest-b", embed_fn=fake_embed)
            first = self.count("unittest-b")
            rag.ingest(self.conn, d, "unittest-b", embed_fn=fake_embed)
            second = self.count("unittest-b")
        self.assertEqual(first, 2)
        self.assertEqual(second, first)

    def test_other_project_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            rag.ingest(self.conn, d, "unittest-c1", embed_fn=fake_embed)
            rag.ingest(self.conn, d, "unittest-c2", embed_fn=fake_embed)
            rag.ingest(self.conn, d, "unittest-c1", embed_fn=fake_embed)
        self.assertEqual(self.count("unittest-c1"), 1)
        self.assertEqual(self.count("unittest-c2"), 1)

    def test_failure_keeps_old_rows(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            rag.ingest(self.conn, d, "unittest-d", embed_fn=fake_embed)
        before = self.count("unittest-d")
        bad_rows = [("x", {"project": "unittest-d"}, [0.1] * 3)]  # 次元が違う: 挿入で失敗する
        with self.assertRaises(Exception):
            rag.replace_project(self.conn, "unittest-d", bad_rows)
        self.conn.rollback()
        self.assertEqual(self.count("unittest-d"), before)

    def test_wrong_dimension_from_ollama_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            write_docs(d, {"a.md": "# A\n本文\n"})
            with self.assertRaises(RuntimeError) as cm:
                rag.ingest(self.conn, d, "unittest-e", embed_fn=lambda ts: [[0.1] * 3 for _ in ts])
        self.assertIn("次元", str(cm.exception))

    def test_no_markdown_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                rag.ingest(self.conn, d, "unittest-f", embed_fn=fake_embed)


def axis_embed(texts):
    """語で、軸を決める(猫=0、犬=1、それ以外=2)。順位が、予想できる、決まったベクトル。"""
    out = []
    for t in texts:
        v = [0.0] * rag.EMBED_DIM
        v[0 if "猫" in t else 1 if "犬" in t else 2] = 1.0
        out.append(v)
    return out


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()
        self.d = tempfile.TemporaryDirectory()
        write_docs(self.d.name, {
            "decisions/adr-0001-neko.md": "# 猫\n猫の話です。\n",
            "decisions/shared/inu.md": "# 犬\n犬の話です。\n",
            "design/tori.md": "# 鳥\n鳥の話です。\n",
            "superpowers/plans/uma.md": "# 馬\n馬の話です。\n",
            "memo.md": "# 虫\n虫の話です。\n",
        })
        rag.ingest(self.conn, self.d.name, "unittest-s1", embed_fn=axis_embed)
        rag.ingest(self.conn, self.d.name, "unittest-s2", embed_fn=axis_embed)

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()
        self.d.cleanup()

    def test_nearest_is_first_with_source(self):
        hits = rag.search(self.conn, "猫について", k=3, embed_fn=axis_embed)
        self.assertEqual(hits[0].path, "decisions/adr-0001-neko.md")
        self.assertEqual(hits[0].heading, "猫")
        self.assertAlmostEqual(hits[0].score, 1.0, places=3)
        self.assertGreaterEqual(hits[0].score, hits[-1].score)

    def test_k_limits_results(self):
        self.assertEqual(len(rag.search(self.conn, "猫", k=2, embed_fn=axis_embed)), 2)

    def test_project_filter(self):
        hits = rag.search(self.conn, "猫", project="unittest-s2", k=10, embed_fn=axis_embed)
        self.assertTrue(hits)
        self.assertTrue(all(h.project == "unittest-s2" for h in hits))

    def test_doc_type_filter(self):
        hits = rag.search(self.conn, "猫", doc_type="adr", k=10, embed_fn=axis_embed)
        self.assertTrue(hits)
        self.assertTrue(all(h.doc_type == "adr" for h in hits))

    def test_default_is_adr_and_shared_only(self):
        hits = rag.search(self.conn, "鳥", k=20, embed_fn=axis_embed)
        self.assertEqual({h.doc_type for h in hits}, {"adr", "shared"})

    def test_explicit_design_is_returned(self):
        hits = rag.search(self.conn, "鳥", doc_type="design", k=20, embed_fn=axis_embed)
        self.assertTrue(hits)
        self.assertTrue(all(h.doc_type == "design" for h in hits))

    def test_explicit_plan_is_returned(self):
        hits = rag.search(self.conn, "馬", doc_type="plan", k=20, embed_fn=axis_embed)
        self.assertTrue(hits)
        self.assertTrue(all(h.doc_type == "plan" for h in hits))

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            rag.search(self.conn, "  ", embed_fn=axis_embed)

    def test_format_hits(self):
        hits = rag.search(self.conn, "猫", k=1, embed_fn=axis_embed)
        text = rag.format_hits(hits)
        self.assertIn("neko.md", text)
        self.assertIn("# 猫", text)
        self.assertEqual(rag.format_hits([]), "(該当なし)")


class DocumentToolsTest(unittest.TestCase):
    def setUp(self):
        self.conn = _conn_or_skip()
        self.d = tempfile.TemporaryDirectory()
        write_docs(self.d.name, {
            "design/a.md": "# 題\n前文\n\n## 一\naaa\n\n## 二\nbbb\n",
            "decisions/adr-0001-x.md": "# ADR\n本文\n",
        })
        rag.ingest(self.conn, self.d.name, "unittest-g1", commit="c1", embed_fn=fake_embed)
        rag.ingest(self.conn, self.d.name, "unittest-g2", commit="c2", embed_fn=fake_embed)

    def tearDown(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge WHERE metadata->>'project' LIKE 'unittest-%'")
        self.conn.commit()
        self.conn.close()
        self.d.cleanup()

    def test_get_document_joins_chunks_in_order(self):
        text = rag.get_document(self.conn, "design/a.md", project="unittest-g1")
        self.assertIn("前文", text)
        self.assertLess(text.index("aaa"), text.index("bbb"))
        self.assertNotIn("[design/a.md]", text)

    def test_get_document_unknown_path_is_none(self):
        self.assertIsNone(rag.get_document(self.conn, "no/such.md", project="unittest-g1"))

    def test_get_document_ambiguous_project_is_rejected(self):
        with self.assertRaises(ValueError) as cm:
            rag.get_document(self.conn, "design/a.md")
        self.assertIn("unittest-g1", str(cm.exception))

    def test_list_sources(self):
        rows = [r for r in rag.list_sources(self.conn) if r["project"] == "unittest-g1"]
        by_type = {r["doc_type"]: r for r in rows}
        self.assertEqual(by_type["design"]["files"], 1)
        self.assertEqual(by_type["design"]["chunks"], 3)
        self.assertEqual(by_type["adr"]["commit"], "c1")
        self.assertEqual(by_type["adr"]["model"], rag.EMBED_MODEL)

    def test_list_sources_filter(self):
        rows = rag.list_sources(self.conn, doc_type="adr")
        self.assertTrue(rows)
        self.assertTrue(all(r["doc_type"] == "adr" for r in rows))


if __name__ == "__main__":
    unittest.main()
