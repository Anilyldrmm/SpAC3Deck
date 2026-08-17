from macrodeck.security import AttemptLimiter, build_allowed_origins, origin_allowed


def test_limiter_locks_after_threshold_and_releases_after_lockout():
    limiter = AttemptLimiter(threshold=3, window=60.0, lockout=30.0)

    assert not limiter.is_locked("1.2.3.4", now=0.0)
    assert limiter.record_failure("1.2.3.4", now=0.0) is False
    assert limiter.record_failure("1.2.3.4", now=1.0) is False
    assert limiter.record_failure("1.2.3.4", now=2.0) is True

    assert limiter.is_locked("1.2.3.4", now=2.0) is True
    assert limiter.retry_after("1.2.3.4", now=2.0) == 30
    assert limiter.is_locked("1.2.3.4", now=31.9) is True
    # kilit son basarisiz denemeden itibaren lockout saniye sonra biter
    assert limiter.is_locked("1.2.3.4", now=32.1) is False
    assert limiter.retry_after("1.2.3.4", now=32.1) == 0


def test_limiter_is_per_client_ip():
    limiter = AttemptLimiter(threshold=2, window=60.0, lockout=30.0)
    limiter.record_failure("1.1.1.1", now=0.0)
    limiter.record_failure("1.1.1.1", now=0.0)
    assert limiter.is_locked("1.1.1.1", now=0.0) is True
    assert limiter.is_locked("2.2.2.2", now=0.0) is False


def test_limiter_window_expiry_resets_counter():
    limiter = AttemptLimiter(threshold=3, window=60.0, lockout=30.0)
    limiter.record_failure("1.1.1.1", now=0.0)
    limiter.record_failure("1.1.1.1", now=1.0)
    # pencere doldu, sayac sifirdan baslar -> kilitlenmez
    assert limiter.record_failure("1.1.1.1", now=61.0) is False
    assert limiter.is_locked("1.1.1.1", now=61.0) is False


def test_limiter_reset_clears_state():
    limiter = AttemptLimiter(threshold=2, window=60.0, lockout=30.0)
    limiter.record_failure("1.1.1.1", now=0.0)
    limiter.reset("1.1.1.1")
    assert limiter.record_failure("1.1.1.1", now=0.0) is False


def test_allowed_origins_cover_localhost_and_lan_ip_with_port():
    allowed = build_allowed_origins(["localhost", "127.0.0.1", "192.168.1.10"], 8765)
    assert "http://192.168.1.10:8765" in allowed
    assert "http://localhost:8765" in allowed
    assert "http://127.0.0.1:8765" in allowed
    # farkli port ya da host allowlist disinda
    assert "http://192.168.1.10:80" not in allowed
    assert "http://evil.com:8765" not in allowed


def test_origin_allowed_rejects_rebinding_and_allows_missing_origin():
    allowed = build_allowed_origins(["localhost", "192.168.1.10"], 8765)
    assert origin_allowed(None, allowed) is True  # curl / native istemci
    assert origin_allowed("", allowed) is True
    assert origin_allowed("http://192.168.1.10:8765", allowed) is True
    assert origin_allowed("HTTP://192.168.1.10:8765/", allowed) is True
    assert origin_allowed("http://evil.com", allowed) is False
    assert origin_allowed("null", allowed) is False
