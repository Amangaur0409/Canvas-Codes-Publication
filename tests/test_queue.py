import unittest
from agent_core import Queue

class QueueTest(unittest.TestCase):
    def setUp(self): self.q=Queue(':memory:')
    def create(self, schedule='2026-11-09T10:00:00+00:00'):
        return self.q.create('pinterest','pin',{'caption':'Test caption','asset':'owned.png'},schedule)
    def test_draft_never_published(self):
        j=self.create(); self.assertIsNone(self.q.claim_due('2026-11-10T00:00:00Z')); self.assertEqual(self.q.get(j)['status'],'draft')
    def test_approval_due_claim_and_success(self):
        j=self.create(); self.q.approve(j); self.assertIsNone(self.q.claim_due('2026-11-09T09:59:59Z')); self.assertEqual(self.q.claim_due('2026-11-09T10:00:00Z')['id'],j); self.assertIsNone(self.q.claim_due('2026-11-10T00:00:00Z')); self.q.finish(j,external_id='pin-1'); self.assertEqual(self.q.get(j)['status'],'published')
    def test_error_is_not_published(self):
        j=self.create(); self.q.approve(j); self.q.claim_due('2026-11-10T00:00:00Z'); self.q.finish(j,error='missing connection'); self.assertEqual(self.q.get(j)['status'],'failed')
    def test_no_fake_success(self):
        j=self.create()
        with self.assertRaises(ValueError): self.q.finish(j,external_id='x')
    def test_schedule_requires_timezone(self):
        with self.assertRaises(ValueError): self.create('2026-11-09T10:00:00')
    def test_changed_payload_blocks_claim(self):
        j=self.create(); self.q.approve(j); self.q.db.execute("UPDATE jobs SET payload_hash='changed' WHERE id=?",(j,)); self.assertIsNone(self.q.claim_due('2026-11-10T00:00:00Z'))

if __name__=='__main__': unittest.main()
