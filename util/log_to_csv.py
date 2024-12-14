#!/usr/bin/env python3
import json
import csv
from datetime import datetime
import argparse


def parse_telemetry_log(log_file: str):
    """Parse telemetry log file into records focusing on token usage."""
    records = []

    with open(log_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)

                # Only process completion spans
                if (data.get('type') == 'span'
                        and 'completion' in data.get('name', '')
                        and data.get('attributes')):

                    attrs = data['attributes']
                    if 'prompt.tokens' in attrs:  # Only process spans with token data
                        record = {
                            'timestamp':
                            data.get('timestamp', ''),
                            'transaction_id':
                            attrs.get('transaction_id', ''),
                            'user_id':
                            attrs.get('user.id', ''),
                            'model':
                            attrs.get('llm.model', ''),
                            'provider':
                            attrs.get('llm.provider', ''),
                            'request_type':
                            attrs.get('llm.request.type', ''),
                            'prompt_tokens':
                            attrs.get('prompt.tokens', 0),
                            'completion_tokens':
                            attrs.get('completion.tokens', 0),
                            'total_tokens':
                            attrs.get('total.tokens', 0),
                            'duration_ms':
                            (data.get('end_time', 0) -
                             data.get('start_time', 0)) / 1000000,
                            'success':
                            attrs.get('policy.passed', True)
                        }
                        records.append(record)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"Error processing line: {e}")
                continue

    return records


def write_csv(records, output_file: str):
    """Write records to CSV file."""
    if not records:
        print("No records found to write")
        return

    fieldnames = [
        'timestamp', 'transaction_id', 'user_id', 'model', 'provider',
        'request_type', 'prompt_tokens', 'completion_tokens', 'total_tokens',
        'duration_ms', 'success'
    ]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Observicia telemetry logs to CSV')
    parser.add_argument('--input',
                        required=True,
                        help='Input telemetry log file')
    parser.add_argument('--output', required=True, help='Output CSV file')

    args = parser.parse_args()

    # Process the log file
    print(f"Processing telemetry log: {args.input}")
    records = parse_telemetry_log(args.input)

    # Write to CSV
    write_csv(records, args.output)
    print(f"Processed {len(records)} records to {args.output}")

    # Print some basic statistics
    if records:
        total_prompt_tokens = sum(r['prompt_tokens'] for r in records)
        total_completion_tokens = sum(r['completion_tokens'] for r in records)
        total_tokens = sum(r['total_tokens'] for r in records)
        avg_duration = sum(r['duration_ms'] for r in records) / len(records)

        print("\nSummary:")
        print(f"Total Prompt Tokens: {total_prompt_tokens:,}")
        print(f"Total Completion Tokens: {total_completion_tokens:,}")
        print(f"Total Tokens: {total_tokens:,}")
        print(f"Average Request Duration: {avg_duration:.2f}ms")


if __name__ == "__main__":
    main()
