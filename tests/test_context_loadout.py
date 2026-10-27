import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import context_loadout
import context_pack


def owner_record(kind, owner, record_id, title, text, revision):
    return {"kind": kind, "owner": owner, "record_id": record_id,
            "revision": revision, "digest": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            "title": title, "text": text, "qualification": "caller supplied; not independently verified"}


class ContextLoadoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        (self.project / "billing.py").write_text("def bill(items):\n    return sum(items)\n")
        (self.project / "prices.py").write_text("def calculate_total(items):\n    return sum(items)\n")
        self._git("add", ".")
        self._git("commit", "-qm", "fixture")
        self.context_store = self.root / "context-store"
        self.loadout_store = self.root / "loadouts"
        self.service = context_pack.ContextPackService(
            self.project, store=self.context_store,
            context_root=Path(__file__).resolve().parents[1], project_id="fixture-project")
        candidates = self.service.candidates("change billing total", focus=["billing.py", "prices.py"],
                                             representation="full")
        sources = [row["item_id"] for row in candidates["items"] if row["kind"] == "source"]
        self.assertGreaterEqual(len(sources), 2)
        self.source_id = sources[0]
        preview = self.service.preview(candidates["candidate_set_id"], include_ids=sources[:1], max_tokens=8192)
        self.preview_id = preview["preview_id"]
        self.spec = self._spec("A cited research finding.")

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.project), *args], check=True)

    def _spec(self, research_text):
        return {"schemaVersion": 1, "task": "change billing total",
                "contextPreviewId": self.preview_id, "maxTokens": 8192,
                "reductionRequests": [{"itemId": self.source_id, "maxLines": 8}],
                "ownerPacket": {"task": "change billing total", "records": [
                    owner_record("research_answer", "research", "answer-1", "Finding", research_text, "r1"),
                    owner_record("planning_intent", "planning", "intent-1", "Plan",
                                 "Update the total calculation.", "p1")
                ]}}

    def test_revision_inspection_freeze_cold_read_and_compare(self):
        first = context_loadout.create(self.loadout_store, "billing-task", self.spec)
        self.assertEqual(first["state"], "referenced")
        inspected = context_loadout.inspect(self.loadout_store, "billing-task", version=1,
                                            digest=first["digest"], service=self.service)
        self.assertEqual(inspected["assemblyState"], "assembled")
        self.assertEqual(inspected["deliveryState"], "not_sent")
        manifest = inspected["contextPack"]["manifest"]
        self.assertEqual(len(manifest["items"]), 1)
        self.assertTrue(manifest["omissions"])
        self.assertIn("A cited research finding.", inspected["text"])
        self.assertIn("excluded", [row["reason"] for row in manifest["omissions"]])
        self.assertEqual(len(inspected["reductionPreviews"]), 1)
        self.assertEqual(inspected["reductionPreviews"][0]["source_ref"]["item_id"], self.source_id)
        self.assertEqual(inspected["reductionPreviews"][0]["projected_text"], manifest["items"][0]["content"])
        self.assertNotIn("reductionPreviews", inspected["text"])

        frozen = context_loadout.freeze(self.loadout_store, "billing-task", version=1,
                                        digest=first["digest"], service=self.service)
        self.assertEqual(frozen["artifactState"], "frozen")
        reopened = context_loadout.read(self.loadout_store, frozen["artifactId"])
        self.assertEqual(reopened, frozen)
        self.assertIn("A cited research finding.", reopened["text"])
        self.assertIn("research_answer", reopened["ownerArtifact"]["artifact"]["text"])
        self.assertEqual(reopened["reductionPreviews"], inspected["reductionPreviews"])

        bound_source = self.project / manifest["items"][0]["source"]["path"]
        bound_source.write_text(bound_source.read_text() + "\n# changed after freeze\n")
        with self.assertRaises(context_pack.ContextPackError) as drift:
            context_loadout.inspect(self.loadout_store, "billing-task", version=1,
                                    digest=first["digest"], service=self.service)
        self.assertEqual(drift.exception.code, "source_drift")
        self.assertEqual(context_loadout.read(self.loadout_store, frozen["artifactId"]), frozen)

        candidates = self.service.candidates("change billing total", focus=["billing.py", "prices.py"],
                                             representation="full")
        new_sources = [row["item_id"] for row in candidates["items"] if row["kind"] == "source"]
        preview = self.service.preview(candidates["candidate_set_id"], include_ids=new_sources[:1], max_tokens=8192)
        self.preview_id = preview["preview_id"]
        self.source_id = new_sources[0]
        revised_spec = self._spec("A newer cited research finding.")
        second = context_loadout.revise(self.loadout_store, "billing-task", expected_version=1,
                                        expected_digest=first["digest"], spec=revised_spec)
        comparison = context_loadout.compare(self.loadout_store, "billing-task", frozen["artifactId"],
                                             version=2, digest=second["digest"], service=self.service)
        self.assertTrue(comparison["changed"])
        self.assertTrue(comparison["changes"]["projectPack"])
        self.assertTrue(comparison["changes"]["ownerPacket"])
        self.assertEqual(comparison["state"], "comparison_only")
        self.assertEqual(comparison["before"]["version"], 1)
        self.assertEqual(comparison["after"]["version"], 2)
        revised = context_loadout.inspect(self.loadout_store, "billing-task", version=2,
                                          digest=second["digest"], service=self.service)
        self.assertIn("A newer cited research finding.", revised["text"])

    def test_revision_compare_and_outer_integrity_fail_closed(self):
        first = context_loadout.create(self.loadout_store, "billing-task", self.spec)
        with self.assertRaises(context_pack.ContextPackError) as conflict:
            context_loadout.revise(self.loadout_store, "billing-task", expected_version=1,
                                   expected_digest="0" * 64, spec=self.spec)
        self.assertEqual(conflict.exception.code, "revision_conflict")
        frozen = context_loadout.freeze(self.loadout_store, "billing-task", version=1,
                                        digest=first["digest"], service=self.service)
        path = self.loadout_store / f"snapshot-{frozen['artifactId']}.json"
        body = json.loads(path.read_text())
        body["text"] += "tampered"
        path.write_text(json.dumps(body, sort_keys=True, separators=(",", ":")))
        with self.assertRaises(context_pack.ContextPackError) as invalid:
            context_loadout.read(self.loadout_store, frozen["artifactId"])
        self.assertEqual(invalid.exception.code, "store_invalid")

    def test_loadout_rejects_mission_results_instead_of_dropping_them(self):
        spec = self._spec("A cited research finding.")
        result_text = "The task completed."
        spec["ownerPacket"]["maestro_results"] = [
            owner_record(
                "maestro_result",
                "maestro",
                "result-1",
                "Task result",
                result_text,
                "turn-1",
            )
        ]
        with self.assertRaises(context_pack.ContextPackError) as refused:
            context_loadout.create(self.loadout_store, "billing-task", spec)
        self.assertEqual(refused.exception.code, "invalid_request")
        self.assertFalse(list(self.loadout_store.glob("loadout-*.json")))


if __name__ == "__main__":
    unittest.main()
