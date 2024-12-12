#!/usr/bin/env python3
"""Convert Observicia telemetry logs to Mermaid sequence diagrams."""

import json
from datetime import datetime
from typing import List, Dict
import sys
import argparse


def parse_timestamp(ts_str: str) -> datetime:
    """Parse timestamp string to datetime object."""
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        # Fallback for other timestamp formats
        return datetime.utcnow()


def format_time(dt: datetime) -> str:
    """Format datetime to HH:MM:SS.mmm."""
    return dt.strftime('%H:%M:%S.%f')[:-3]


def parse_spans(log_lines: List[str]) -> List[Dict]:
    """Parse JSON log lines into span dictionaries."""
    spans = []
    for line in log_lines:
        try:
            data = json.loads(line)
            # Handle both old and new log formats
            if data.get('type') == 'span' or 'span_id' in data:
                # Clean and normalize data
                if 'timestamp' not in data and 'time' in data:
                    data['timestamp'] = data['time']
                spans.append(data)
        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"Warning: Error parsing line: {e}", file=sys.stderr)
    return spans


def sanitize_for_mermaid(value: str) -> str:
    """Sanitize text for Mermaid diagram compatibility."""
    if not isinstance(value, str):
        value = str(value)
    # Replace semicolons with commas
    value = value.replace(';', ',')
    # Replace other problematic characters
    value = value.replace(':', ' - ')
    # Replace newlines with <br/>
    value = value.replace('\n', '<br/>')
    return value


def format_attributes(attributes: Dict) -> str:
    """Format span attributes for Mermaid note."""
    formatted = []
    for k, v in attributes.items():
        if k.startswith('stream.chunks'):
            continue  # Skip chunk counts
        if isinstance(v, dict):
            v = sanitize_for_mermaid(json.dumps(v))
        else:
            v = sanitize_for_mermaid(str(v))
        k = sanitize_for_mermaid(k)
        formatted.append(f"{k} - {v}")
    return '<br/>'.join(formatted)


def generate_mermaid(spans: List[Dict]) -> str:
    """Generate Mermaid sequence diagram from spans."""
    if not spans:
        return "sequenceDiagram\n    Note over System: No spans found"

    # Sort spans by start_time
    spans.sort(key=lambda x: parse_timestamp(
        x.get('timestamp', x.get('start_time', ''))))

    # Get trace ID from first span
    trace_id = spans[0].get('trace_id', 'unknown')

    # Initialize diagram
    diagram = ['sequenceDiagram']
    # Sanitize trace ID just in case
    diagram.append(
        f'    Note over Root,Final: Trace ID - {sanitize_for_mermaid(trace_id)}'
    )
    diagram.append('')

    # Define participants based on span names found
    participants = set()
    for span in spans:
        name = sanitize_for_mermaid(span.get('name', '').split('.')[-1])
        if name:
            participants.add(name)

    # Add participants in order
    diagram.append('    participant Root')
    for participant in sorted(participants):
        if participant not in ('Root', 'Final'):
            diagram.append(f'    participant {participant}')
    if 'Final' not in participants:
        diagram.append('    participant Final')
    diagram.append('')

    # Process spans
    for span in spans:
        timestamp = format_time(parse_timestamp(span.get('timestamp', '')))
        name = sanitize_for_mermaid(span.get('name', '').split('.')[-1])
        parent = sanitize_for_mermaid(span.get('parent_id', 'Root'))

        if name:
            # Add span start
            diagram.append(f'    Root->>+{name}: start ({timestamp})')

            # Add attributes as note
            if span.get('attributes'):
                diagram.append(
                    f'    Note over {name}: {format_attributes(span["attributes"])}'
                )

            # Add span end
            diagram.append(f'    {name}-->>-Root: complete')
            diagram.append('')

    return '\n'.join(diagram)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Observicia telemetry logs to Mermaid diagram')
    parser.add_argument('-i',
                        '--input',
                        help='Input log file (default: stdin)')
    parser.add_argument('-o', '--output', help='Output file (default: stdout)')
    args = parser.parse_args()

    # Read input
    if args.input:
        with open(args.input, 'r') as f:
            log_lines = f.readlines()
    else:
        log_lines = sys.stdin.readlines()

    # Parse and generate diagram
    spans = parse_spans(log_lines)
    mermaid_diagram = generate_mermaid(spans)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(mermaid_diagram)
    else:
        print(mermaid_diagram)


if __name__ == '__main__':
    main()
