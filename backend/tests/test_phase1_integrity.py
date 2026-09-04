import pytest


@pytest.mark.asyncio
async def test_phase1_integrity_scope_does_not_require_http_client():
    """Smoke-test the Phase 1 integrity module can be imported."""
    from data_integrity import run_data_integrity_checks

    assert callable(run_data_integrity_checks)


@pytest.mark.asyncio
async def test_phase1_integrity_result_shape(monkeypatch):
    """Keep the audit contract stable for future admin diagnostics."""
    import data_integrity

    class FakeCollection:
        async def count_documents(self, query):
            return 0

        def find(self, *args, **kwargs):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class FakeDB:
        def __getitem__(self, name):
            return FakeCollection()

    monkeypatch.setattr(data_integrity, "db", FakeDB())
    result = await data_integrity.run_data_integrity_checks("business-test")
    assert "products" in result
    assert "references" in result
    assert result["products"]["total"] == 0
