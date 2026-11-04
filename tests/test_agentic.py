"""Synthetic orchestration checks and real local MCP transport discovery."""
import asyncio
import unittest
from unittest.mock import Mock
from agentic.graph import build_agent, initial_state


def response(calls=None, tokens=1):
    return {'content': 'No supported evidence.', 'tool_calls': calls or [], 'total_tokens': tokens}


def call(name='search_manuals'):
    return {'id': '1', 'name': name, 'arguments': {}}


class GraphTests(unittest.TestCase):
    def test_observation_and_answer(self):
        executor = Mock()
        executor.execute.return_value = {'passages': []}
        model = Mock(side_effect=[response([call()]), response()])
        result = build_agent(model, executor).invoke(initial_state('Find'))
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(result['messages'][-2]['role'], 'tool')
        self.assertEqual(result['calls'], 1)

    def test_error_feedback(self):
        executor = Mock()
        executor.execute.side_effect = PermissionError('Approval required')
        model = Mock(side_effect=[response([call('save_report_revision')]), response()])
        result = build_agent(model, executor).invoke(initial_state('Save'))
        self.assertIn('PermissionError', result['messages'][-2]['content'])

    def test_call_budget(self):
        executor = Mock()
        executor.execute.return_value = {}
        calls = [{**call(), 'id': str(i)} for i in range(3)]
        model = Mock(return_value=response(calls))
        result = build_agent(model, executor, max_tool_calls=1).invoke(initial_state('Find'))
        self.assertEqual(executor.execute.call_count, 1)
        self.assertEqual(result['status'], 'budget_exhausted')

    def test_token_budget_blocks_write(self):
        executor = Mock()
        model = Mock(return_value=response([call('save_report_revision')], 101))
        result = build_agent(model, executor, max_tokens=100).invoke(initial_state('Save'))
        executor.execute.assert_not_called()
        self.assertEqual(result['status'], 'budget_exhausted')

    def test_step_limit_and_fresh_memory(self):
        executor = Mock()
        executor.execute.return_value = {}
        model = Mock(return_value=response([call()]))
        result = build_agent(model, executor, max_steps=1).invoke(initial_state('Find'))
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(len(initial_state('Next')['messages']), 2)


class MCPTests(unittest.TestCase):
    def test_discovery_real_stdio(self):
        from agentic.mcp_client import query_server
        self.assertEqual(asyncio.run(query_server()), {'tools': ['search_manuals']})

    def test_wrapper_delegation(self):
        from server import create_server
        executor = Mock()
        executor.execute.return_value = {'status': 'no_supported_passages', 'passages': []}
        async def check():
            return await create_server(executor).call_tool('search_manuals', {
                'query': 'bearing', 'machine_type': 'fan', 'language': 'en', 'top_k': 3})
        asyncio.run(check())
        executor.execute.assert_called_once()
