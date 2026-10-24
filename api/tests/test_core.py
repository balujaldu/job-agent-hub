import unittest

from app.ats import extract_keywords, score_resume
from app.state import InvalidTransition, JobStatus, can_send, transition

JD = "We need a Python engineer with FastAPI, PostgreSQL and Docker. Python and FastAPI daily."
RESUME = (
    "Jane Doe jane@example.com\n"
    "Experience\nPython engineer. Built FastAPI services in Python with PostgreSQL and Docker. " + "word " * 160 + "\n"
    "Education\nBSc\nSkills\nPython, FastAPI, PostgreSQL, Docker\n"
)


class ATSTests(unittest.TestCase):
    def test_keywords_ranked_by_frequency(self):
        kws = extract_keywords(JD)
        self.assertEqual(kws[:2], ["python", "fastapi"])

    def test_deterministic(self):
        self.assertEqual(score_resume(RESUME, JD), score_resume(RESUME, JD))

    def test_full_match_scores_high(self):
        r = score_resume(RESUME, JD)
        self.assertEqual(r.missing, [])
        self.assertGreaterEqual(r.score, 90)

    def test_missing_keywords_lower_score(self):
        weak = score_resume(RESUME.replace("Docker", "").replace("FastAPI", ""), JD)
        self.assertIn("docker", weak.missing)
        self.assertLess(weak.score, score_resume(RESUME, JD).score)

    def test_format_issues_reported(self):
        r = score_resume("short | text", JD)
        self.assertTrue(r.format_issues)


class StateTests(unittest.TestCase):
    def test_only_approved_can_send(self):
        for s in JobStatus:
            self.assertEqual(can_send(s), s == JobStatus.APPROVED)

    def test_cannot_skip_approval(self):
        with self.assertRaises(InvalidTransition):
            transition(JobStatus.AWAITING_APPROVAL, JobStatus.SENDING)
        with self.assertRaises(InvalidTransition):
            transition(JobStatus.PROCESSING, JobStatus.APPROVED)

    def test_email_not_found_cannot_be_approved(self):
        with self.assertRaises(InvalidTransition):
            transition(JobStatus.EMAIL_NOT_FOUND, JobStatus.APPROVED)

    def test_happy_path(self):
        s = JobStatus.QUEUED
        for nxt in (JobStatus.PROCESSING, JobStatus.AWAITING_APPROVAL, JobStatus.APPROVED,
                    JobStatus.SENDING, JobStatus.SENT):
            s = transition(s, nxt)
        self.assertEqual(s, JobStatus.SENT)


if __name__ == "__main__":
    unittest.main()
