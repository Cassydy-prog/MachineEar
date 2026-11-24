"""Opt-in Groq CLI. Sends the request, tool definitions and tool observations to Groq."""
import argparse
import json
import os
from pathlib import Path
from agentic.graph import build_agent, initial_state, observation
from machineear.agent_tools.executor import ToolExecutor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('goal')
    parser.add_argument('--allow-groq', action='store_true', help='Allow sending request and returned passages/results to Groq')
    parser.add_argument('--trace-langfuse', action='store_true', help='Send only operational metrics to the configured Langfuse project')
    parser.add_argument('--case', type=int, choices=range(1, 6), help='Optional demonstration case number for trace lookup')
    parser.add_argument('--wav', type=Path)
    parser.add_argument('--machine', choices=['fan', 'pump'])
    parser.add_argument('--id', choices=['id_00', 'id_02', 'id_04', 'id_06'])
    parser.add_argument('--report', type=Path, help='Existing trusted review record JSON')
    parser.add_argument('--review-text', type=Path, help='Exact report revision to display for approval')
    args = parser.parse_args()
    if not args.allow_groq:
        parser.error('Choose --allow-groq to authorize this external provider call')
    langfuse = None
    if args.trace_langfuse:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / '.env')
        if not all(os.environ.get(key) for key in ('LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'LANGFUSE_BASE_URL')):
            parser.error('Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL')
        from langfuse import get_client
        langfuse = get_client()
    if not os.environ.get('GROQ_API_KEY'):
        parser.error('Set GROQ_API_KEY in your environment')
    if args.wav and not (args.machine and args.id):
        parser.error('--wav requires --machine and --id')
    if bool(args.report) != bool(args.review_text):
        parser.error('--report and --review-text must be supplied together')
    executor = ToolExecutor()
    context = {}
    if args.wav:
        context.update(recording_id=executor.register_recording(args.wav),
                       machine_type=args.machine, machine_id=args.id)
    if args.report:
        record = json.loads(args.report.read_text(encoding='utf-8'))
        text = args.review_text.read_text(encoding='utf-8')
        print('\nEXACT TEXT FOR REVIEW:\n' + text)
        print('\nEquipment context:\n' + json.dumps(record['analysis'].get('audio', {}), indent=2))
        reviewer = input('Reviewer name: ').strip()
        if input('After checking source applicability, type SAVE to approve this exact text: ') != 'SAVE':
            raise SystemExit('Cancelled; nothing saved')
        report_id = executor.register_report(record)
        approval_id = executor.approve_report(report_id, text, reviewer, applicability_checked=True)
        context.update(report_id=report_id, approval_id=approval_id, reviewed_text=text)
    from openai import OpenAI
    client = OpenAI(base_url='https://api.groq.com/openai/v1',
                    api_key=os.environ['GROQ_API_KEY'], timeout=45, max_retries=0)
    model = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')

    def model_call(messages, schemas, remaining_tokens):
        # Leave room for input tokens. Actual total usage is checked after the response.
        response = client.chat.completions.create(
            model=model,
            messages=messages, temperature=0,
            **({'tools': schemas} if schemas else {}),
            max_completion_tokens=min(1500, remaining_tokens))
        message = response.choices[0].message
        return {'content': message.content,
                'tool_calls': [{'id': c.id, 'name': c.function.name,
                                'arguments': c.function.arguments} for c in message.tool_calls or []],
                'total_tokens': response.usage.total_tokens,
                'usage_details': {'input': response.usage.prompt_tokens,
                                  'output': response.usage.completion_tokens,
                                  'total': response.usage.total_tokens}}

    metadata = {'case': args.case} if args.case else {}
    try:
        with observation(langfuse, 'machineear-request', 'agent', metadata=metadata) as trace:
            result = build_agent(model_call, executor, trace=trace, model_name=model).invoke(
                initial_state(args.goal, 'Trusted host-issued context:\n' + json.dumps(context, ensure_ascii=False)))
            summary = {'status': result['status'], 'steps': result['steps'],
                       'tool_calls': result['calls'], 'tokens': result['tokens']}
            if trace is not None:
                trace.update(output=summary)
                summary = {**summary, 'trace_id': trace.trace_id}
    finally:
        if langfuse is not None:
            langfuse.flush()
    print(json.dumps(summary, indent=2))
    if result['status'] == 'answered':
        print(result['messages'][-1]['content'])
    else:
        print('Stopped without a final answer. Do not treat a tool observation as a completed report.')


if __name__ == '__main__':
    main()
