"""Generate the three tool schemas and separate read/write metadata."""
import argparse
import json
from pathlib import Path
from machineear.agent_tools.models import (
    AnalyzeAudioInput, AnalyzeAudioOutput, SearchManualsInput, SearchManualsOutput,
    SaveReportRevisionInput, SaveReportRevisionOutput,
)

TOOLS = {
    'analyze_audio': ('read', AnalyzeAudioInput, AnalyzeAudioOutput,
        'Read tool. Analyze a registered WAV using Ballystone\'s frozen fan/pump predictor. '
        'Returns unusual-sound scores and windows, not a mechanical diagnosis. Does not save records.'),
    'search_manuals': ('read', SearchManualsInput, SearchManualsOutput,
        'Read tool. Search fan/pump maintenance manuals with local semantic/BM25 hybrid retrieval. '
        'Return verified PDF page passages or no supported passages. Equipment applicability needs review.'),
    'save_report_revision': ('write', SaveReportRevisionInput, SaveReportRevisionOutput,
        'Write tool. Append a reviewed maintenance report revision to local history. Requires a '
        'trusted single-use human approval matching this report and exact text. Never invent approval.'),
}


def tool_schemas():
    # Metadata stays outside the provider function schema.
    return [{'name': name, 'access': access,
             'tool': {'type': 'function', 'function': {
                 'name': name, 'description': description,
                 'parameters': input_model.model_json_schema()}},
             'output_schema': output_model.model_json_schema()}
            for name, (access, input_model, output_model, description) in TOOLS.items()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('schemas/machineear_tools.json'))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(tool_schemas(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported three tools to {args.output}')


if __name__ == '__main__':
    main()
