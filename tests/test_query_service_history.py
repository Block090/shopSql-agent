# ruff: noqa: E402, I001

import asyncio
import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault(
    "langchain_huggingface",
    types.SimpleNamespace(HuggingFaceEndpointEmbeddings=object),
)
sys.modules.setdefault(
    "elasticsearch",
    types.SimpleNamespace(AsyncElasticsearch=object),
)
sys.modules.setdefault(
    "qdrant_client",
    types.SimpleNamespace(AsyncQdrantClient=object),
)
sys.modules.setdefault(
    "qdrant_client.http.models",
    types.SimpleNamespace(PointStruct=object),
)
sys.modules.setdefault(
    "qdrant_client.models",
    types.SimpleNamespace(Distance=types.SimpleNamespace(COSINE="cosine"), PointStruct=object, VectorParams=object),
)
sys.modules.setdefault("app.agent.graph", types.SimpleNamespace(graph=object()))

from app.services.query_history_service import QueryService, format_user_error_message  # noqa: E402


class FakeHistoryRepository:
    def __init__(self, recent_turns=None):
        self.recent_turns = recent_turns or []
        self.saved = []
        self.touched_sessions = []

    async def ensure_tables(self):
        self.ensured = True

    async def create_or_touch_session(self, session_id, title=None):
        self.touched_sessions.append({"session_id": session_id, "title": title})

    async def get_recent_turns(self, session_id, limit=3):
        return self.recent_turns[:limit]

    async def save_history(
        self,
        session_id,
        query,
        resolved_query,
        sql,
        result_summary,
        status,
        error_message=None,
        result_data=None,
        context_trace=None,
        semantic_slots=None,
        rewrite_confidence=None,
        result_facts=None,
        result_analysis=None,
    ):
        self.last_result_data = result_data
        self.last_context_trace = context_trace
        self.last_semantic_slots = semantic_slots
        self.last_rewrite_confidence = rewrite_confidence
        self.last_result_facts = result_facts
        self.last_result_analysis = result_analysis
        self.saved.append(
            {
                "session_id": session_id,
                "query": query,
                "resolved_query": resolved_query,
                "sql": sql,
                "result_summary": result_summary,
                "status": status,
                "error_message": error_message,
                "context_trace": context_trace,
                "semantic_slots": semantic_slots,
                "rewrite_confidence": rewrite_confidence,
                "result_facts": result_facts,
                "result_analysis": result_analysis,
            }
        )

    async def delete_session(self, session_id):
        self.deleted_session_id = session_id


class FakeGraph:
    def __init__(self):
        self.inputs = []

    async def astream(self, input, context, stream_mode):
        self.inputs.append(input)
        yield (
            "values",
            {
                "sql": "SELECT region_name, SUM(order_amount) AS GMV FROM fact_order LIMIT 10",
                "metric_infos": [
                    {
                        "name": "GMV",
                        "description": "成交总额，按订单金额汇总",
                        "relevant_columns": ["fact_order.order_amount"],
                        "alias": ["成交额", "销售总额"],
                    }
                ],
            },
        )
        yield (
            "custom",
            {
                "type": "result",
                "data": [{"region_name": "华东", "GMV": 100}],
            },
        )


class NamespacedFakeGraph:
    def __init__(self):
        self.inputs = []

    async def astream(self, input, context, stream_mode):
        self.inputs.append(input)
        yield (
            (),
            "values",
            {
                "sql": "SELECT region_name, SUM(order_amount) AS GMV FROM fact_order LIMIT 10",
                "metric_infos": [
                    {
                        "name": "GMV",
                        "description": "成交总额，按订单金额汇总",
                        "relevant_columns": ["fact_order.order_amount"],
                        "alias": ["成交额", "销售总额"],
                    }
                ],
            },
        )
        yield (
            (),
            "custom",
            {
                "type": "result",
                "data": [{"region_name": "华东", "GMV": 100}],
            },
        )


class EmptyResultGraph:
    async def astream(self, input, context, stream_mode):
        yield (
            "values",
            {
                "sql": "SELECT region_name, SUM(order_amount) AS GMV FROM fact_order WHERE date_id BETWEEN 20261201 AND 20261231 LIMIT 10",
                "metric_infos": [
                    {
                        "name": "GMV",
                        "description": "成交总额，按订单金额汇总",
                        "relevant_columns": ["fact_order.order_amount"],
                        "alias": ["成交额"],
                    }
                ],
            },
        )
        yield ("custom", {"type": "result", "data": []})


class FakeQueryCaseRepository:
    def __init__(self):
        self.upserted = []

    async def upsert_query_case(self, query_case, vector):
        self.upserted.append({"query_case": query_case, "vector": vector})


class FakeEmbeddingClient:
    async def aembed_query(self, text):
        self.last_text = text
        return [0.1, 0.2, 0.3]


async def fake_llm_rewriter(query, recent_turns):
    from app.core.query_rewriter import QueryRewriteResult

    return QueryRewriteResult(
        original_query=query,
        resolved_query="统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序",
        is_follow_up=True,
        inherited_context={"time_range": "2025 年 3 月"},
        overwritten_context={"dimension": "大区", "metrics": ["GMV"], "sort": "GMV 从高到低"},
        source_turn_id=None,
        rewrite_method="llm",
        semantic_slots={
            "time_range": "2025 年 3 月",
            "dimension": "大区",
            "metrics": ["GMV"],
            "filters": {},
            "sort": {"field": "GMV", "direction": "desc"},
            "limit": None,
        },
        confidence=0.92,
    )


async def fake_rule_rewriter(query, recent_turns):
    from app.core.query_rewriter import rewrite_query_with_trace

    return rewrite_query_with_trace(query, recent_turns)


async def fake_clarification_rewriter(query, recent_turns):
    from app.core.query_rewriter import QueryRewriteResult

    return QueryRewriteResult(
        original_query=query,
        resolved_query="",
        is_follow_up=True,
        inherited_context={},
        overwritten_context={},
        source_turn_id=None,
        rewrite_method="llm",
        semantic_slots={},
        confidence=0.62,
        needs_clarification=True,
        clarification_question="你是想按大区统计 2025 年 3 月 GMV，并按 GMV 从高到低排序吗？",
    )


async def fake_result_analyzer(query, resolved_query, result_data):
    return {
        "summary": "华东 GMV 最高。",
        "insights": ["华东地区 GMV 为 100。"],
        "chart_recommendation": {
            "type": "bar",
            "x": "region_name",
            "y": "GMV",
            "reason": "按地区比较 GMV 适合柱状图。",
        },
        "result_facts": {
            "row_count": 1,
            "columns": ["region_name", "GMV"],
            "dimension_columns": ["region_name"],
            "metric_columns": ["GMV"],
        },
        "generated_by": "test_stub",
    }


async def blocking_result_analyzer(query, resolved_query, result_data):
    await asyncio.Event().wait()


class QueryServiceHistoryTest(unittest.IsolatedAsyncioTestCase):
    def test_format_user_error_message_hides_raw_502_http_exception(self):
        raw_error = (
            "Server error '502 Bad Gateway' for url 'http://localhost:8081' "
            "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/502"
        )

        message = format_user_error_message(RuntimeError(raw_error))

        assert message == (
            "后端调用下游服务失败：本次查询依赖的本地服务 localhost:8081 返回 502。"
            "请检查对应服务是否已启动、端口是否正确，或稍后重试。"
        ), message
        assert "developer.mozilla.org" not in message
        assert "Server error" not in message

    async def test_query_returns_error_event_when_history_init_fails(self):
        class FailingHistoryRepository(FakeHistoryRepository):
            async def ensure_tables(self):
                raise RuntimeError("history unavailable")

        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=FailingHistoryRepository(),
            graph=FakeGraph(),
        )

        events = []
        async for event in service.query("查询 GMV", session_id="session-error"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert events == [{"type": "error", "message": "history unavailable"}]

    async def test_query_rewrites_follow_up_and_saves_history(self):
        history_repository = FakeHistoryRepository(
            recent_turns=[
                {
                    "query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                    "resolved_query": "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
                }
            ]
        )
        fake_graph = FakeGraph()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=fake_graph,
            context_rewriter=fake_rule_rewriter,
        )

        events = []
        async for event in service.query("那华东地区呢", session_id="session-1"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert fake_graph.inputs[0]["query"] == "统计 2025 年第一季度华东地区的 GMV"
        assert events[0] == {"type": "session", "session_id": "session-1"}
        assert events[1]["type"] == "context_trace"
        assert events[1]["data"]["original_query"] == "那华东地区呢"
        assert events[1]["data"]["resolved_query"] == "统计 2025 年第一季度华东地区的 GMV"
        assert events[1]["data"]["inherited_context"]["metrics"] == ["GMV"]
        assert events[1]["data"]["overwritten_context"] == {"region": "华东"}
        assert history_repository.last_context_trace == events[1]["data"]
        assert history_repository.last_result_data == events[2]["data"]
        assert history_repository.saved == [
            {
                "session_id": "session-1",
                "query": "那华东地区呢",
                "resolved_query": "统计 2025 年第一季度华东地区的 GMV",
                "sql": "SELECT region_name, SUM(order_amount) AS GMV FROM fact_order LIMIT 10",
                "result_summary": "返回 1 行，字段：大区、GMV",
                "status": "success",
                "error_message": None,
                "context_trace": events[1]["data"],
                "result_facts": history_repository.last_result_facts,
                "result_analysis": history_repository.last_result_analysis,
                "semantic_slots": history_repository.last_semantic_slots,
                "rewrite_confidence": history_repository.last_rewrite_confidence,
            }
        ]
        assert history_repository.last_semantic_slots["filters"]["region"] == "华东"
        assert history_repository.last_rewrite_confidence >= 0.8

    async def test_query_injects_permission_context_by_user_id(self):
        history_repository = FakeHistoryRepository()
        fake_graph = FakeGraph()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=fake_graph,
            context_rewriter=fake_rule_rewriter,
        )

        async for _ in service.query(
            "查询华东地区 GMV", session_id="session-permission", user_id="region_east"
        ):
            pass

        permission_context = fake_graph.inputs[0]["permission_context"]
        assert permission_context["user_id"] == "region_east"
        assert permission_context["data_scope"] == {"region_name": ["华东"]}
        assert "customer_phone" in permission_context["denied_columns"]

    async def test_query_uses_injected_llm_rewriter_for_follow_up(self):
        history_repository = FakeHistoryRepository(
            recent_turns=[
                {
                    "query": "统计 2025 年 3 月各商品品类的销量和销售额",
                    "resolved_query": "统计 2025 年 3 月各商品品类的销量和销售额",
                    "semantic_slots": {
                        "time_range": "2025 年 3 月",
                        "dimension": "商品品类",
                        "metrics": ["销量", "销售额"],
                        "filters": {},
                        "sort": None,
                        "limit": None,
                    },
                }
            ]
        )
        fake_graph = FakeGraph()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=fake_graph,
            context_rewriter=fake_llm_rewriter,
        )

        events = []
        async for event in service.query("那各大区的GMV排序呢", session_id="session-llm"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert fake_graph.inputs[0]["query"] == "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序"
        assert events[1]["data"]["rewrite_method"] == "llm"
        assert events[1]["data"]["confidence"] == 0.92
        assert history_repository.last_semantic_slots["dimension"] == "大区"

    async def test_query_returns_clarification_when_llm_rewriter_is_uncertain(self):
        history_repository = FakeHistoryRepository(
            recent_turns=[{"query": "统计 2025 年 3 月各商品品类的销量和销售额"}]
        )
        fake_graph = FakeGraph()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=fake_graph,
            context_rewriter=fake_clarification_rewriter,
        )

        events = []
        async for event in service.query("那各大区呢", session_id="session-clarify"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert len(fake_graph.inputs) == 0
        assert events[-1]["type"] == "clarification"
        assert events[-1]["clarification_type"] == "context_rewrite"
        assert history_repository.saved[0]["status"] == "clarification_required"

    async def test_query_forwards_namespaced_langgraph_custom_events(self):
        history_repository = FakeHistoryRepository()
        fake_graph = NamespacedFakeGraph()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=fake_graph,
        )

        events = []
        async for event in service.query("查询 GMV", session_id="session-3"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert {"type": "result", "data": [{"大区": "华东", "GMV": 100}]} in events
        assert history_repository.saved[0]["status"] == "success"

    async def test_delete_session_delegates_to_history_repository(self):
        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=FakeGraph(),
        )

        result = await service.delete_session("session-delete")

        assert result == {"deleted": True, "session_id": "session-delete"}
        assert history_repository.deleted_session_id == "session-delete"

    async def test_query_saves_error_history_when_graph_raises(self):
        class ErrorGraph:
            async def astream(self, input, context, stream_mode):
                raise RuntimeError("backend failed")
                yield

        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=ErrorGraph(),
        )

        events = []
        async for event in service.query("查询 GMV", session_id="session-2"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert events[-1] == {"type": "error", "message": "backend failed"}
        assert history_repository.saved[0]["status"] == "failed"
        assert history_repository.saved[0]["error_message"] == "backend failed"

    async def test_query_returns_friendly_error_when_downstream_service_raises_502(self):
        class BadGatewayGraph:
            async def astream(self, input, context, stream_mode):
                raise RuntimeError(
                    "Server error '502 Bad Gateway' for url 'http://localhost:8081' "
                    "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/502"
                )
                yield

        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=BadGatewayGraph(),
        )

        events = []
        async for event in service.query("查询 GMV", session_id="session-502"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert events[-1] == {
            "type": "error",
            "message": (
                "后端调用下游服务失败：本次查询依赖的本地服务 localhost:8081 返回 502。"
                "请检查对应服务是否已启动、端口是否正确，或稍后重试。"
            ),
        }
        assert "developer.mozilla.org" not in history_repository.saved[0]["error_message"]


    async def test_query_emits_result_analysis_and_saves_it(self):
        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=FakeGraph(),
            result_analyzer=fake_result_analyzer,
        )

        events = []
        async for event in service.query("查询华东地区 GMV", session_id="session-analysis"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        assert events[2]["type"] == "result_analysis"
        assert events[2]["data"]["summary"] == "华东 GMV 最高。"
        assert history_repository.last_result_facts == {
            "row_count": 1,
            "columns": ["region_name", "GMV"],
            "dimension_columns": ["region_name"],
            "metric_columns": ["GMV"],
        }
        assert history_repository.last_result_analysis["generated_by"] == "test_stub"

    async def test_query_emits_masked_query_explanation_after_result_analysis(self):
        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=FakeGraph(),
            result_analyzer=fake_result_analyzer,
        )

        events = []
        async for event in service.query("查询华东地区 GMV", session_id="session-explain"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        explanation_events = [
            event for event in events if event["type"] == "query_explanation"
        ]
        assert len(explanation_events) == 1
        explanation = explanation_events[0]["data"]
        assert explanation["business"]["metrics"] == ["GMV：成交总额，按订单金额汇总"]
        assert explanation["business"]["dimensions"] == ["大区"]
        assert explanation["technical"]["visibility"] == "admin_masked"
        assert "fact_order" not in explanation["technical"]["sql"]
        assert "order_amount" not in explanation["technical"]["sql"]
        assert "订单金额" in explanation["technical"]["sql"]
        assert explanation["risk"]["level"] == "low"

        suggestion_events = [
            event for event in events if event["type"] == "followup_suggestions"
        ]
        assert len(suggestion_events) == 1
        assert len(suggestion_events[0]["data"]["suggestions"]) >= 3

    async def test_query_emits_empty_result_diagnosis_for_zero_rows(self):
        history_repository = FakeHistoryRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            graph=EmptyResultGraph(),
            result_analyzer=fake_result_analyzer,
        )

        events = []
        async for event in service.query("查询 2026 年 12 月 GMV", session_id="session-empty"):
            events.append(json.loads(event.removeprefix("data: ").strip()))

        diagnosis_events = [
            event for event in events if event["type"] == "empty_result_diagnosis"
        ]
        assert len(diagnosis_events) == 1
        assert diagnosis_events[0]["data"]["summary"] == "本次查询没有返回数据。"
        assert any("放宽时间范围" in item for item in diagnosis_events[0]["data"]["suggestions"])

    async def test_query_upserts_successful_query_case_memory(self):
        history_repository = FakeHistoryRepository()
        query_case_repository = FakeQueryCaseRepository()
        embedding_client = FakeEmbeddingClient()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=embedding_client,
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            query_case_repository=query_case_repository,
            graph=FakeGraph(),
            context_rewriter=fake_llm_rewriter,
            result_analyzer=fake_result_analyzer,
        )

        async for _ in service.query("那各大区的GMV排序呢", session_id="session-memory"):
            pass

        assert len(query_case_repository.upserted) == 1
        query_case = query_case_repository.upserted[0]["query_case"]
        assert query_case["question"] == "那各大区的GMV排序呢"
        assert query_case["resolved_query"] == "统计 2025 年 3 月各大区的 GMV，并按 GMV 从高到低排序"
        assert "fact_order" in query_case["used_tables"]
        assert "order_amount" in query_case["used_fields"]
        assert "指标：GMV" in embedding_client.last_text

    async def test_result_event_is_not_blocked_by_slow_result_analysis(self):
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=object(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=FakeHistoryRepository(),
            graph=FakeGraph(),
            result_analyzer=blocking_result_analyzer,
        )

        stream = service.query("查询华东地区 GMV", session_id="session-slow-analysis")
        first_event = json.loads((await stream.__anext__()).removeprefix("data: ").strip())
        second_event = json.loads(
            (await asyncio.wait_for(stream.__anext__(), timeout=0.2))
            .removeprefix("data: ")
            .strip()
        )
        await stream.aclose()

        assert first_event == {"type": "session", "session_id": "session-slow-analysis"}
        assert second_event["type"] == "result"

    async def test_query_does_not_upsert_query_case_for_empty_result(self):
        history_repository = FakeHistoryRepository()
        query_case_repository = FakeQueryCaseRepository()
        service = QueryService(
            meta_mysql_repository=object(),
            embedding_client=FakeEmbeddingClient(),
            dw_mysql_repository=object(),
            column_qdrant_repository=object(),
            metric_qdrant_repository=object(),
            value_es_repository=object(),
            query_history_repository=history_repository,
            query_case_repository=query_case_repository,
            graph=EmptyResultGraph(),
            result_analyzer=fake_result_analyzer,
        )

        async for _ in service.query("查询 2026 年 12 月 GMV", session_id="session-empty-memory"):
            pass

        assert query_case_repository.upserted == []

if __name__ == "__main__":
    unittest.main()
