import json
from datetime import datetime
from typing import List, Dict
import sys


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp string to datetime object."""
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))


def format_time(dt: datetime) -> str:
    """Format datetime to HH:MM:SS.mmm."""
    return dt.strftime('%H:%M:%S.%f')[:-3]


def parse_spans(log_lines: List[str]) -> List[Dict]:
    """Parse JSON log lines into span dictionaries."""
    spans = []
    for line in log_lines:
        try:
            data = json.loads(line)
            if data.get('type') == 'span':
                spans.append(data)
        except json.JSONDecodeError:
            continue
    return spans


def format_attributes(attributes: Dict) -> str:
    """Format span attributes for Mermaid note."""
    return '<br/>'.join(
        f"{k}: {v}" for k, v in attributes.items()
        if not k.startswith('stream.chunks'))  # Skip chunk counts


def generate_mermaid(spans: List[Dict]) -> str:
    """Generate Mermaid sequence diagram from spans."""
    # Sort spans by start_time
    spans.sort(key=lambda x: x['start_time'])

    # Get trace ID from first span
    trace_id = spans[0]['trace_id']

    # Initialize diagram
    diagram = ['sequenceDiagram']

    # Add trace ID note
    diagram.append(f'    Note over Root,Final: trace_id: {trace_id}')
    diagram.append('')

    # Define participants
    diagram.append('    participant Root')
    diagram.append('    participant Chat as openai.chat.completion.async')
    diagram.append('    participant Stream as stream_processing')
    diagram.append('    participant Final as finalize_stream')
    diagram.append('')

    # Process main completion span
    completion_span = next(s for s in spans
                           if s['name'] == 'openai.chat.completion.async')
    completion_time = format_time(parse_timestamp(
        completion_span['timestamp']))
    diagram.append(f'    Root->>Chat: start ({completion_time})')
    diagram.append(
        f'    Note over Chat: {format_attributes(completion_span["attributes"])}'
    )
    diagram.append('')

    # Process stream span
    stream_span = next(s for s in spans if s['name'] == 'stream_processing')
    stream_time = format_time(parse_timestamp(stream_span['timestamp']))
    diagram.append(f'    Chat->>Stream: start ({stream_time})')
    diagram.append(
        f'    Note over Stream: {format_attributes(stream_span["attributes"])}'
    )
    diagram.append('')

    # Process finalize span
    final_span = next(s for s in spans if s['name'] == 'finalize_stream')
    final_time = format_time(parse_timestamp(final_span['timestamp']))
    diagram.append(f'    Stream->>Final: start ({final_time})')
    diagram.append(
        f'    Note over Final: {format_attributes(final_span["attributes"])}')
    diagram.append(f'    Final-->>Stream: complete')
    diagram.append('')

    # Close remaining spans
    diagram.append('    Stream-->>Chat: complete')
    diagram.append('    Chat-->>Root: complete')

    return '\n'.join(diagram)


def main():
    # Read input from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            log_lines = f.readlines()
    else:
        log_lines = sys.stdin.readlines()

    # Parse spans and generate diagram
    spans = parse_spans(log_lines)
    mermaid_diagram = generate_mermaid(spans)
    print(mermaid_diagram)


if __name__ == '__main__':
    main()
