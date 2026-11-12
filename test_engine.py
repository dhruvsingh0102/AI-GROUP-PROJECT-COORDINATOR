import unittest
from engine import analyze_update, analyze_multi_task_reply


class EngineTests(unittest.TestCase):
    def test_connected_but_waiting_for_credentials_is_blocked(self):
        result = analyze_update("The API is connected, but I am waiting for test credentials.")
        self.assertEqual(result.status, "Blocked")
        self.assertEqual(result.blocker, "test credentials")
        self.assertNotEqual(result.status, "Complete")

    def test_vague_reply_does_not_complete(self):
        self.assertEqual(analyze_update("Working on it, will update soon").status, "In Progress")
        self.assertEqual(analyze_update("looks good").status, "Needs Clarification")

    def test_hinglish_blocker(self):
        result = analyze_update("API connected hai, test credentials ka wait kar raha hoon")
        self.assertEqual(result.status, "Blocked")
        self.assertEqual(result.blocker, "test credentials")

    def test_negated_completion_not_complete(self):
        self.assertNotEqual(analyze_update("Not complete yet").status, "Complete")

    def test_single_multi_task_reply_is_ambiguous(self):
        results = analyze_multi_task_reply("Done", ["API", "Demo"])
        self.assertTrue(all(decision.status == "Needs Clarification" for _, decision in results))


if __name__ == "__main__":
    unittest.main()
