import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import context_pack
import linked_context


def record(kind, owner, record_id, title, text):
    return {"kind": kind, "owner": owner, "record_id": record_id,
            "revision": "rev-1", "digest": "sha256:" + "a" * 64,
            "title": title, "text": text, "qualification": "caller validated"}


def packet(research="A cited finding.", planning="Draft a response."):
    return {"task": "Prepare a response", "records": [
        record("research_answer", "research", "answer-1", "Finding", research),
        record("planning_intent", "planning", "intent-1", "Intent", planning)]}


def maestro_result(record_id="mission-1/task-2/event-9", text="Observed task result.", title="Task result"):
    return {"kind": "maestro_result", "owner": "maestro", "record_id": record_id,
            "revision": "event-9", "digest": "sha256:" + context_pack._sha(text.encode("utf-8")),
            "title": title, "text": text, "qualification": "Observed assistant output"}


class LinkedContextTests(unittest.TestCase):
    def test_complete_exact_fixture_and_cold_read(self):
        with tempfile.TemporaryDirectory() as directory:
            result = linked_context.assemble(directory, packet())
            self.assertEqual(result["included"], [
                {"kind": "research_answer", "owner": "research", "record_id": "answer-1",
                 "revision": "rev-1", "digest": "sha256:" + "a" * 64,
                 "qualification": "caller validated"},
                {"kind": "planning_intent", "owner": "planning", "record_id": "intent-1",
                 "revision": "rev-1", "digest": "sha256:" + "a" * 64,
                 "qualification": "caller validated"}])
            expected = ("# Context pack " + result["packId"] + "\n"
                        "Preview: linked-owner-packets\n"
                        "Task: Prepare a response\n"
                        'Project observation: {"authority":"caller_validated_data"}\n'
                        'Context observation: {"authority":"caller_validated_data"}\n'
                        'Included IDs: ["answer-1","intent-1"]\n'
                        'Limits: {"max_bytes_per_format":32768,"max_tokens":8192,"token_estimate":"ceil(UTF-8 bytes / 4)"}\n'
                        "Selected exact excerpts and guidance follow. Advisory only; user and project instructions win.\n"
                        "\n## research_answer: Finding (answer-1)\n"
                        'Metadata: {"authority":"caller_validated_data","item_id":"answer-1","kind":"research_answer","source_ref":{"digest":"sha256:' + "a" * 64 + '","owner":"research","qualification":"caller validated","record_id":"answer-1","revision":"rev-1"},"title":"Finding"}\n'
                        "```\nA cited finding.\n```\n"
                        "\n## planning_intent: Intent (intent-1)\n"
                        'Metadata: {"authority":"caller_validated_data","item_id":"intent-1","kind":"planning_intent","source_ref":{"digest":"sha256:' + "a" * 64 + '","owner":"planning","qualification":"caller validated","record_id":"intent-1","revision":"rev-1"},"title":"Intent"}\n'
                        "```\nDraft a response.\n```\n"
                        "\nOmissions: none\n")
            self.assertEqual(result["text"], expected)
            self.assertEqual(result["renderSha256"], context_pack._sha(expected.encode("utf-8")))
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "scripts")
            reopened = subprocess.run([sys.executable, str(Path(linked_context.__file__)),
                                       "read", "--store", directory,
                                       "--artifact-id", result["artifactId"]],
                                      check=True, capture_output=True, text=True, env=env)
            cold = json.loads(reopened.stdout)
            self.assertEqual(cold, result)

    def test_budget_omits_research_explicitly_and_never_clips(self):
        with tempfile.TemporaryDirectory() as directory:
            result = linked_context.assemble(directory, packet("R" * 5000), max_tokens=450)
            self.assertEqual([row["record_id"] for row in result["included"]], ["intent-1"])
            self.assertEqual(result["omissions"], [{"record_id": "answer-1", "reason": "budget"}])
            self.assertNotIn("R" * 100, result["text"])
            self.assertIn("Draft a response.", result["text"])
            with self.assertRaises(context_pack.ContextPackError):
                linked_context.assemble(directory, packet("short", "P" * 50000), max_tokens=450)

    def test_tampered_store_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result = linked_context.assemble(directory, packet())
            path = Path(directory) / f"linked-{result['artifactId']}.json"
            body = json.loads(path.read_text())
            body["artifact"]["text"] += "tampered"
            path.write_text(json.dumps(body))
            with self.assertRaises(context_pack.ContextPackError):
                linked_context.read(directory, result["artifactId"])

    def test_maestro_result_is_frozen_as_v2_and_reopens_without_owner(self):
        source = packet()
        source["maestro_results"] = [maestro_result()]
        with tempfile.TemporaryDirectory() as directory:
            result = linked_context.assemble(directory, source)
            self.assertEqual(result["schemaVersion"], 2)
            self.assertEqual([row["record_id"] for row in result["included"]],
                             ["answer-1", "intent-1", "mission-1/task-2/event-9"])
            self.assertEqual(result["sourceRefs"][-1]["digest"], source["maestro_results"][0]["digest"])
            self.assertIn("Observed task result.", result["text"])
            reopened = linked_context.read(directory, result["artifactId"])
            self.assertEqual(reopened, result)

    def test_maestro_result_digest_must_bind_exact_utf8_text(self):
        source = packet()
        result = maestro_result(text="café")
        result["digest"] = "sha256:" + "0" * 64
        source["maestro_results"] = [result]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(context_pack.ContextPackError, "digest does not match"):
                linked_context.assemble(directory, source)

    def test_result_budget_omissions_are_explicit_and_planning_stays_included(self):
        source = packet()
        source["maestro_results"] = [
            maestro_result("mission-1/task-2/event-10", "L" * 5000, "Large output"),
            maestro_result("mission-1/task-2/event-11", "Short observed output", "Short output")]
        with tempfile.TemporaryDirectory() as directory:
            result = linked_context.assemble(directory, source, max_tokens=450)
            included_ids = [row["record_id"] for row in result["included"]]
            self.assertIn("intent-1", included_ids)
            self.assertIn("mission-1/task-2/event-11", included_ids)
            self.assertEqual(result["omissions"], [{
                "kind": "maestro_result", "owner": "maestro",
                "record_id": "mission-1/task-2/event-10", "reason": "budget"}])
            self.assertNotIn("L" * 100, result["text"])
            self.assertIn("Short observed output", result["text"])

    def test_more_than_eight_maestro_results_is_rejected(self):
        source = packet()
        source["maestro_results"] = [maestro_result(f"source-{index}") for index in range(9)]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(context_pack.ContextPackError, "at most eight"):
                linked_context.assemble(directory, source)

    def test_resolve_for_mission_returns_exact_bounded_context_and_identity_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = linked_context.assemble(directory, packet())
            ref = {"owner": "context-ai", "id": artifact["artifactId"],
                   "artifactSha256": artifact["renderSha256"],
                   "qualification": "Deep journal qualification is caller metadata"}
            resolved = linked_context.resolve_for_mission(directory, ref)
            self.assertEqual(resolved["preparedInput"]["text"], artifact["text"])
            self.assertEqual(resolved["contextRef"], ref)
            receipt = resolved["publicReceipt"]
            self.assertEqual(receipt["callerQualificationUnverified"], ref["qualification"])
            self.assertIn("included=research_answer,planning_intent", receipt["ownerQualification"])
            self.assertEqual(resolved["preparedInput"]["context"]["qualification"],
                             receipt["ownerQualification"])
            self.assertNotEqual(resolved["preparedInput"]["context"]["qualification"],
                                ref["qualification"])
            self.assertEqual(receipt["sourceFreshness"], "not_verified_by_context_owner_api")
            self.assertIsNone(receipt["missionTaskBinding"])
            self.assertEqual(receipt["textSha256"], artifact["renderSha256"])

    def test_resolve_for_mission_rejects_wrong_owner_or_render_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = linked_context.assemble(directory, packet())
            ref = {"owner": "context-ai", "id": artifact["artifactId"],
                   "artifactSha256": artifact["renderSha256"], "qualification": "checked"}
            with self.assertRaisesRegex(context_pack.ContextPackError, "owner does not match"):
                linked_context.resolve_for_mission(directory, {**ref, "owner": "research-ai"})
            with self.assertRaisesRegex(context_pack.ContextPackError, "does not match"):
                linked_context.resolve_for_mission(directory, {**ref, "artifactSha256": "0" * 64})

    def test_resolve_for_mission_cli_uses_explicit_store_and_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = linked_context.assemble(directory, packet())
            ref = {"owner": "context-ai", "id": artifact["artifactId"],
                   "artifactSha256": artifact["renderSha256"], "qualification": "caller note"}
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(linked_context.__file__).resolve().parent)
            result = subprocess.run(
                [sys.executable, str(Path(linked_context.__file__)), "resolve-for-mission",
                 "--store", directory], input=json.dumps({"contextRef": ref}),
                check=True, capture_output=True, text=True, env=env)
            self.assertEqual(json.loads(result.stdout), linked_context.resolve_for_mission(directory, ref))

    def test_resolve_for_mission_validates_expected_planning_source(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = linked_context.assemble(directory, packet())
            ref = {"owner": "context-ai", "id": artifact["artifactId"],
                   "artifactSha256": artifact["renderSha256"], "qualification": "caller note"}
            expected = {"planId": "intent-1", "planSha256": "a" * 64}
            with_expected = linked_context.resolve_for_mission(
                directory, ref, expected_planning=expected)
            without_expected = linked_context.resolve_for_mission(directory, ref)
            self.assertEqual(with_expected, without_expected)
            for bad in ({"planId": "other-plan", "planSha256": "a" * 64},
                        {"planId": "intent-1", "planSha256": "b" * 64}):
                with self.subTest(expected=bad), self.assertRaisesRegex(
                        context_pack.ContextPackError, "does not match expectedPlanning"):
                    linked_context.resolve_for_mission(directory, ref, expected_planning=bad)

    def test_expected_planning_rejects_missing_or_omitted_source(self):
        expected = {"planId": "intent-1", "planSha256": "a" * 64}
        with self.assertRaisesRegex(context_pack.ContextPackError, "no Planning intent"):
            linked_context._validate_expected_planning(
                {"sourceRefs": [], "included": [], "omissions": []}, expected)

        source_ref = {"kind": "planning_intent", "owner": "planning",
                      "record_id": "intent-1", "digest": "sha256:" + "a" * 64}
        omitted = {"sourceRefs": [source_ref], "included": [],
                   "omissions": [{"record_id": "intent-1", "reason": "budget"}]}
        with self.assertRaisesRegex(context_pack.ContextPackError, "is omitted"):
            linked_context._validate_expected_planning(omitted, expected)

    def test_resolve_for_mission_cli_accepts_expected_planning_additively(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = linked_context.assemble(directory, packet())
            request = {
                "contextRef": {"owner": "context-ai", "id": artifact["artifactId"],
                               "artifactSha256": artifact["renderSha256"],
                               "qualification": "caller note"},
                "expectedPlanning": {"planId": "intent-1", "planSha256": "a" * 64},
            }
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(linked_context.__file__).resolve().parent)
            result = subprocess.run(
                [sys.executable, str(Path(linked_context.__file__)), "resolve-for-mission",
                 "--store", directory], input=json.dumps(request),
                check=True, capture_output=True, text=True, env=env)
            self.assertEqual(json.loads(result.stdout), linked_context.resolve_for_mission(
                directory, request["contextRef"], expected_planning=request["expectedPlanning"]))


if __name__ == "__main__":
    unittest.main()
