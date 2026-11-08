import json
import os
import sqlite3
import tempfile

from src.llm.client import LLM, Tracker


class _Usage:
    def __init__(self, prompt_tokens=0, completion_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _Completions:
    def __init__(self, content):
        self._content = content
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        return _Response(self._content)


class _Chat:
    def __init__(self, content):
        self.completions = _Completions(content)


class _StubGroq:
    """Stand-in for the Groq client: always returns the same completion."""

    def __init__(self, content):
        self.chat = _Chat(content)


def _llm_with_db(content):
    """LLM with a stub Groq client and a throwaway SQLite cache (no key needed)."""
    l = LLM.__new__(LLM)
    l.m = {"name": "m", "reasoning_effort": "low", "max_tokens": 10}
    l.namespace = "ns"
    l.use_cache = True
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    l.cache_path = path
    l.db = sqlite3.connect(path, check_same_thread=False)
    l.db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT)")
    l.db.commit()
    l._client = _StubGroq(content)
    return l, path
    l = LLM.__new__(LLM)  # skips API client, so test needs no key
    l.m = {"name": "m", "reasoning_effort": "low", "max_tokens": 10}
    l.namespace = "ns"
    return l


def make():
    l = LLM.__new__(LLM)  # skips API client, so test needs no key
    l.m = {"name": "m", "reasoning_effort": "low", "max_tokens": 10}
    l.namespace = "ns"
    return l


def test_key_changes_with_every_setting():
    l, msgs = make(), [{"role": "user", "content": "hi"}]
    base = l._key(msgs, 0.0, 10, 0)

    # 1. Temperature change alters key
    assert base != l._key(msgs, 0.7, 10, 0)

    # 2. Max tokens change alters key
    assert base != l._key(msgs, 0.0, 11, 0)

    # 3. Sample index change alters key (critical for self-consistency)
    assert base != l._key(msgs, 0.0, 10, 1)

    # 4. Prompt content alters key
    assert base != l._key([{"role": "user", "content": "hello"}], 0.0, 10, 0)

    # 5. Model name alters key
    l.m = dict(l.m, name="other")
    assert base != l._key(msgs, 0.0, 10, 0)

    # 6. Namespace alters key
    l.m = dict(l.m, name="m")
    l.namespace = "ns2"
    assert base != l._key(msgs, 0.0, 10, 0)

    # 7. Reasoning effort alters key
    l.namespace = "ns"
    l.m = dict(l.m, reasoning_effort="high")
    assert base != l._key(msgs, 0.0, 10, 0)


def test_key_changes_with_version():
    """Audit M3: bumping the cache-key version must invalidate old keys."""
    import src.llm.client as client_mod

    l, msgs = make(), [{"role": "user", "content": "hi"}]
    base = l._key(msgs, 0.0, 10, 0)
    old = client_mod.CACHE_KEY_VERSION
    try:
        client_mod.CACHE_KEY_VERSION = old + 1
        assert base != l._key(msgs, 0.0, 10, 0)
    finally:
        client_mod.CACHE_KEY_VERSION = old
    assert base == l._key(msgs, 0.0, 10, 0)


def test_empty_completion_is_not_cached():
    """Audit M1: an empty Groq response must never be written to the cache."""
    l, path = _llm_with_db("")
    try:
        tr = Tracker()
        assert l.chat([{"role": "user", "content": "hi"}], tr) == ""
        assert l.db.execute("SELECT COUNT(*) FROM c").fetchone()[0] == 0
        # A second call re-fetches live instead of serving an empty row.
        assert l.chat([{"role": "user", "content": "hi"}], tr) == ""
        assert l._client.chat.completions.calls == 2
        assert tr.cache_hits == 0
    finally:
        l.close()
        os.unlink(path)


def test_nonempty_completion_is_cached():
    l, path = _llm_with_db("hello")
    try:
        tr = Tracker()
        assert l.chat([{"role": "user", "content": "hi"}], tr) == "hello"
        assert l.db.execute("SELECT COUNT(*) FROM c").fetchone()[0] == 1
        assert l.chat([{"role": "user", "content": "hi"}], tr) == "hello"
        assert l._client.chat.completions.calls == 1
        assert tr.cache_hits == 1
    finally:
        l.close()
        os.unlink(path)


def test_cached_empty_row_is_not_served():
    """A legacy poisoned row (written before the guard) must be skipped."""
    l, path = _llm_with_db("hello")
    try:
        key = l._key([{"role": "user", "content": "hi"}], 0.0, 10, 0)
        l.db.execute(
            "INSERT INTO c (k, v) VALUES (?, ?)",
            (key, json.dumps({"text": "", "in": 0, "out": 0})),
        )
        l.db.commit()
        tr = Tracker()
        assert l.chat([{"role": "user", "content": "hi"}], tr) == "hello"
        assert tr.cache_hits == 0
        assert l._client.chat.completions.calls == 1
    finally:
        l.close()
        os.unlink(path)

