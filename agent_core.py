"""Durable approval and dispatch primitives for the publishing agent.

No social network or model is configured by this module. Ad spend is out of scope.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

PLATFORMS = {'instagram', 'facebook', 'pinterest', 'youtube'}
FORMATS = {'post', 'reel', 'story', 'short', 'pin'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(payload):
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


class Queue:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=15, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(
          id INTEGER PRIMARY KEY, platform TEXT NOT NULL, format TEXT NOT NULL,
          payload TEXT NOT NULL, payload_hash TEXT NOT NULL, scheduled_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'draft', approved_hash TEXT,
          external_id TEXT, error TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL, action TEXT NOT NULL,
          at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id));
        ''')

    def create(self, platform, media_format, payload, scheduled_at):
        if platform not in PLATFORMS or media_format not in FORMATS:
            raise ValueError('Unsupported platform or format')
        if not isinstance(payload, dict) or not payload.get('caption'):
            raise ValueError('A caption is required')
        dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Schedule must include a timezone')
        utc = dt.astimezone(timezone.utc).isoformat()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            cur = self.db.execute('INSERT INTO jobs(platform,format,payload,payload_hash,scheduled_at,created_at) VALUES(?,?,?,?,?,?)', (platform,media_format,canonical(payload),digest(payload),utc,timestamp()))
            job = cur.lastrowid
            self.db.execute('INSERT INTO events(job_id,action,at) VALUES(?,?,?)',(job,'created',timestamp()))
            self.db.commit()
            return job
        except Exception:
            self.db.rollback(); raise

    def approve(self, job):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
            if not row or row['status'] != 'draft':
                raise ValueError('Only drafts can be approved')
            self.db.execute("UPDATE jobs SET status='approved', approved_hash=payload_hash WHERE id=?",(job,))
            self.db.execute('INSERT INTO events(job_id,action,at) VALUES(?,?,?)',(job,'approved',timestamp()))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise

    def claim_due(self, now=None):
        now = now or timestamp()
        dt = datetime.fromisoformat(now.replace('Z','+00:00'))
        if dt.tzinfo is None: raise ValueError('Clock must include timezone')
        now = dt.astimezone(timezone.utc).isoformat()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute("SELECT * FROM jobs WHERE status='approved' AND approved_hash=payload_hash AND scheduled_at<=? ORDER BY scheduled_at,id LIMIT 1",(now,)).fetchone()
            if row is None: self.db.commit(); return None
            changed = self.db.execute("UPDATE jobs SET status='publishing' WHERE id=? AND status='approved' AND approved_hash=payload_hash",(row['id'],)).rowcount
            if changed:
                self.db.execute('INSERT INTO events(job_id,action,at) VALUES(?,?,?)',(row['id'],'claimed',timestamp()))
            self.db.commit()
            return dict(row) if changed else None
        except Exception:
            self.db.rollback(); raise

    def finish(self, job, external_id=None, error=None):
        if bool(external_id) == bool(error): raise ValueError('Provide an external ID or an error')
        status = 'published' if external_id else 'failed'
        self.db.execute('BEGIN IMMEDIATE')
        try:
            changed = self.db.execute("UPDATE jobs SET status=?, external_id=?, error=? WHERE id=? AND status='publishing'",(status,external_id,error,job)).rowcount
            if changed != 1: raise ValueError('Only a claimed job can be finished')
            self.db.execute('INSERT INTO events(job_id,action,at) VALUES(?,?,?)',(job,status,timestamp()))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise

    def get(self, job):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
        return dict(row) if row else None
