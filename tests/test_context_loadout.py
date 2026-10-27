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


def preference_profile(text):
    return {"schema": "custom.preference-profile-export.v1", "ownerId": "custom-ai",
            "ownerRevision": "a" * 40, "kitId": "synthetic-kit", "kitVersion": 2,
            "kitDigest": "b" * 64, "profileId": "personal-default", "profileRevision": 3,
            "scope": "personal", "projectId": None, "sessionId": None,
            "lineage": [{"id": "personal-default", "label": "Personal defaults", "scope": "personal",
                         "project_id": None, "session_id": None, "revision": 3,
                         "expires_at": None, "state": "active"}],
            "expiresAt": None, "preferences": [{"id": "brevity", "text": "Keep prose concise.",
                "swap": {}, "exceptions": [], "source": {"profile_id": "personal-default", "scope": "personal",
                "label": "Personal defaults", "revision": 3, "expires_at": None},
                "provenance": {"kind": "saved-profile-edit"}, "override_of": None}],
            "conflicts": [], "previewDigest": "c" * 64,
            "textSha256": hashlib.sha256(text.encode()).hexdigest(), "text": text,
            "exportReceipt": {"schema": "custom.preference-profile-export-receipt.v1",
                "requestId": "11111111-1111-4111-8111-111111111111", "inputDigest": "d" * 64,
                "exported": "exports/profile-personal-default-r3-cccccccccccc.md",
                "previewDigest": "c" * 64, "textSha256": hashlib.sha256(text.encode()).hexdigest()},
            "qualification": context_loadout.PREFERENCE_PROFILE_QUALIFICATION}


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

    def test_source_pack_only_v2_freezes_exact_context_source_and_cold_reads(self):
        spec = {"schemaVersion": 2, "variant": "source-pack-only",
                "task": "change billing total", "contextPreviewId": self.preview_id,
                "maxTokens": 8192,
                "reductionRequests": [{"itemId": self.source_id, "maxLines": 8}]}
        first = context_loadout.create(self.loadout_store, "source-task", spec)
        self.assertEqual(first["schemaVersion"], 2)
        second = context_loadout.revise(self.loadout_store, "source-task", expected_version=1,
                                        expected_digest=first["digest"], spec=spec)
        inspected = context_loadout.inspect(self.loadout_store, "source-task", version=2,
                                            digest=second["digest"], service=self.service)
        self.assertEqual(inspected["deliveryState"], "not_sent")
        source = inspected["sourceArtifact"]
        self.assertEqual(source["kind"], "context_source_pack")
        self.assertEqual(source["owner"], "context-ai")
        self.assertEqual(source["contextProjectId"], "fixture-project")
        self.assertEqual(source["previewId"], self.preview_id)
        self.assertEqual(source["packId"], inspected["contextPack"]["packId"])
        self.assertEqual(source["artifactId"], context_loadout._sha(
            context_pack._json({key: value for key, value in source.items() if key != "artifactId"}).encode()))
        self.assertEqual(source["manifestSha256"], hashlib.sha256(source["jsonRender"].encode()).hexdigest())
        self.assertEqual(source["textSha256"], hashlib.sha256(source["textRender"].encode()).hexdigest())
        first_source = source["fileHashes"][0]
        self.assertEqual(first_source["fileSha256"], hashlib.sha256((self.project / first_source["path"]).read_bytes()).hexdigest())
        self.assertEqual(inspected["inspection"]["includedOwnerRefs"], [])
        self.assertEqual(inspected["inspection"]["estimatedTokens"], (inspected["inspection"]["combinedBytes"] + 3) // 4)
        self.assertEqual(len(inspected["reductionPreviews"]), 1)
        frozen = context_loadout.freeze(self.loadout_store, "source-task", version=2,
                                        digest=second["digest"], service=self.service)
        comparison = context_loadout.compare(self.loadout_store, "source-task", frozen["artifactId"],
                                             version=2, digest=second["digest"], service=self.service)
        self.assertFalse(comparison["changed"])
        self.assertEqual(comparison["state"], "comparison_only")
        self.assertEqual(context_loadout.read(self.loadout_store, frozen["artifactId"]), frozen)
        bound_file = self.project / first_source["path"]
        bound_file.write_text(bound_file.read_text() + "\n# changed after freeze\n")
        with self.assertRaises(context_pack.ContextPackError) as drift:
            context_loadout.inspect(self.loadout_store, "source-task", version=2,
                                    digest=second["digest"], service=self.service)
        self.assertEqual(drift.exception.code, "source_drift")
        self.assertEqual(context_loadout.read(self.loadout_store, frozen["artifactId"]), frozen)

    def test_source_pack_only_v2_runs_through_standalone_cli(self):
        spec = {"schemaVersion": 2, "variant": "source-pack-only",
                "task": "change billing total", "contextPreviewId": self.preview_id, "maxTokens": 8192}
        spec_path = self.root / "source-spec.json"
        spec_path.write_text(json.dumps(spec))
        script = Path(__file__).resolve().parents[1] / "scripts" / "context_loadout.py"
        base = [sys.executable, str(script)]
        def run(*args):
            return subprocess.run([*base, *map(str, args)], check=True, capture_output=True, text=True)
        created = json.loads(run("create", "--store", self.loadout_store,
                                 "--loadout-id", "cli-source", "--spec", spec_path).stdout)
        frozen = json.loads(run("freeze", "--store", self.loadout_store,
                                "--loadout-id", "cli-source", "--version", 1, "--digest", created["digest"],
                                "--project", self.project, "--project-id", "fixture-project",
                                "--context-store", self.context_store).stdout)
        reopened = json.loads(run("read", "--store", self.loadout_store,
                                  "--artifact-id", frozen["artifactId"]).stdout)
        self.assertEqual(reopened["sourceArtifact"]["kind"], "context_source_pack")
        self.assertEqual(reopened["artifactId"], frozen["artifactId"])

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

    def test_typed_custom_preference_profile_loadout_is_frozen_and_reopened_without_fake_owner_rows(self):
        text = "# Profile preview\n\nKeep prose concise.\n"
        spec = {"schemaVersion": 1, "task": "change billing total",
                "contextPreviewId": self.preview_id, "maxTokens": 8192,
                "preferenceProfile": preference_profile(text)}
        created = context_loadout.create(self.loadout_store, "profile-billing", spec)
        inspected = context_loadout.inspect(self.loadout_store, "profile-billing", version=1,
                                            digest=created["digest"], service=self.service)
        profile_artifact = inspected["ownerArtifact"]["artifact"]
        self.assertEqual(profile_artifact["schema"], "context.preference-profile-artifact.v1")
        self.assertEqual(profile_artifact["profile"], spec["preferenceProfile"])
        self.assertEqual(profile_artifact["included"][0]["kind"], "preference_profile")
        self.assertEqual(profile_artifact["included"][0]["owner"], "custom-ai")
        self.assertNotIn("ownerPacket", inspected["loadout"]["spec"])
        self.assertIn("system, developer, user and project instructions", inspected["text"])
        self.assertIn(text, inspected["text"])
        frozen = context_loadout.freeze(self.loadout_store, "profile-billing", version=1,
                                        digest=created["digest"], service=self.service)
        reopened = context_loadout.read(self.loadout_store, frozen["artifactId"])
        self.assertEqual(reopened, frozen)
        self.assertEqual(reopened["ownerArtifact"]["artifact"]["profile"], spec["preferenceProfile"])

    def test_preference_profile_loadout_refuses_bad_source_digest_and_expired_source(self):
        text = "# Profile preview\n"
        bad = preference_profile(text)
        bad["textSha256"] = "0" * 64
        spec = {"schemaVersion": 1, "task": "change billing total", "contextPreviewId": self.preview_id,
                "maxTokens": 8192, "preferenceProfile": bad}
        with self.assertRaises(context_pack.ContextPackError) as mismatch:
            context_loadout.create(self.loadout_store, "bad-profile-digest", spec)
        self.assertEqual(mismatch.exception.code, "invalid_request")
        expired = preference_profile(text)
        expired["scope"] = "session"
        expired["sessionId"] = "temporary-review"
        expired["expiresAt"] = "2000-01-01T00:00:00Z"
        row = expired["lineage"][0]
        row.update(scope="session", session_id="temporary-review", expires_at=expired["expiresAt"])
        spec["preferenceProfile"] = expired
        with self.assertRaises(context_pack.ContextPackError) as inactive:
            context_loadout.create(self.loadout_store, "expired-profile", spec)
        self.assertEqual(inactive.exception.code, "profile_expired")


if __name__ == "__main__":
    unittest.main()
