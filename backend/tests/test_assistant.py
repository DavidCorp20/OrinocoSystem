"""AI assistant SSE streaming with GPT 5.4 Mini + history persistence."""
import json
import os
import time

import pytest
from conftest import API


class TestAssistant:
    def test_history_endpoint(self, admin):
        r = admin.get(f"{API}/assistant/history")
        assert r.status_code == 200
        assert isinstance(r.json()["messages"], list)

    @pytest.mark.skipif(not os.getenv("EMERGENT_LLM_KEY"), reason="No hay clave EMERGENT_LLM_KEY configurada para validar el streaming real del asistente IA.")
    def test_chat_streams_spanish_grounded_answer(self, admin):
        t0 = time.time()
        with admin.post(f"{API}/assistant/chat",
                        json={"message": "¿Qué productos debo comprar hoy?"},
                        stream=True, timeout=180) as r:
            assert r.status_code == 200, r.text[:400]
            assert "text/event-stream" in r.headers.get("content-type", "")
            chunks, done = [], False
            first_chunk_at = None
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    done = True
                    break
                chunks.append(json.loads(payload)["c"])
                if first_chunk_at is None:
                    first_chunk_at = round(time.time() - t0, 2)
        full = "".join(chunks)
        print(f"AI chunks={len(chunks)} ttfb={first_chunk_at}s len={len(full)}")
        print(f"AI answer: {full[:700]}")
        assert done, "stream did not terminate with [DONE]"
        assert "no pude procesar tu consulta" not in full, "LLM call failed (fallback message returned)"
        assert len(full) > 60, full
        assert len(chunks) > 1, f"expected multiple SSE deltas (streaming), got {len(chunks)}"
        # Grounding check: the answer must mention inventory/purchase vocabulary
        # (LLM wording varies: "compra hoy", "repón", "quedan 4"...), so match stems.
        assert any(w in full.lower() for w in ("stock", "product", "compr", "repon", "repón", "invent", "agotad")), full

    def test_chat_persists_to_history(self, admin):
        msgs = admin.get(f"{API}/assistant/history").json()["messages"]
        assert any(m["role"] == "user" for m in msgs)
        assert any(m["role"] == "assistant" and m["content"] for m in msgs)

    def test_chat_validation(self, admin):
        assert admin.post(f"{API}/assistant/chat", json={"message": ""}).status_code == 422
