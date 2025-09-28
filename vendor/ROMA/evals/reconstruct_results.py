#!/usr/bin/env python3
"""
Script to reconstruct run results from project_results JSON files using frames_benchmark.csv
"""

import json
import csv
import os
import argparse
from datetime import datetime
from pathlib import Path

def parse_timestamp(timestamp_str):
    """Parse timestamp string to datetime object"""
    if not timestamp_str:
        return None
    try:
        # Remove timezone info if present and parse
        clean_timestamp = timestamp_str.replace('Z', '').split('+')[0].split('-')[0]
        return datetime.fromisoformat(clean_timestamp.replace('Z', ''))
    except:
        return None

def calculate_execution_time(start_time, end_time):
    """Calculate execution time in seconds"""
    if not start_time or not end_time:
        return None
    
    start = parse_timestamp(start_time)
    end = parse_timestamp(end_time)
    
    if start and end:
        return (end - start).total_seconds()
    return None

def extract_project_id(filename):
    """Extract project ID (UUID) from filename"""
    # Remove .json extension and _results suffix
    base_name = filename.replace('.json', '').replace('_results', '')
    return base_name

def count_nodes(json_data):
    """Count total number of nodes in the execution graph"""
    if 'basic_state' in json_data and 'all_nodes' in json_data['basic_state']:
        return len(json_data['basic_state']['all_nodes'])
    return 0

def get_completion_status(root_node_status):
    """Map root node status to completion status"""
    status_map = {
        'DONE': 'completed',
        'FAILED': 'failed',
        'RUNNING': 'running'
    }
    return status_map.get(root_node_status, 'unknown')

def extract_result_from_node(node):
    """Extract result text from a node"""
    # Try different fields for the result
    if node.get('full_result'):
        return node['full_result']
    elif node.get('output_summary'):
        return node['output_summary']
    elif node.get('result'):
        return node['result']
    else:
        return "No output generated"

def find_last_layer1_node(json_data):
    """Find the last processed node in layer 1"""
    if 'basic_state' not in json_data or 'all_nodes' not in json_data['basic_state']:
        return None
    
    all_nodes = json_data['basic_state']['all_nodes']
    layer1_nodes = []
    
    for node in all_nodes.values():
        if node.get('layer') == 1:
            layer1_nodes.append(node)
    
    if not layer1_nodes:
        return None
    
    # Sort by timestamp_updated to find the last processed one
    layer1_nodes.sort(key=lambda x: x.get('timestamp_updated', ''), reverse=True)
    return layer1_nodes[0]

def load_benchmark_data(benchmark_file):
    """Load question-answer pairs from benchmark CSV"""
    benchmark_data = {}
    
    with open(benchmark_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            question = row['question'].strip()
            answer = row['answer'].strip()
            benchmark_data[question] = answer
    
    return benchmark_data

def match_question_answer(goal, benchmark_data):
    """Match project goal with benchmark question to get expected answer"""
    # Direct match first
    if goal in benchmark_data:
        return goal, benchmark_data[goal]
    
    # Fuzzy match - find closest question
    goal_lower = goal.lower().strip()
    for question, answer in benchmark_data.items():
        if question.lower().strip() == goal_lower:
            return question, answer
    
    # If no match found, return the goal as question with empty answer
    return goal, ""

def process_json_file(file_path, benchmark_data):
    """Process a single JSON file and extract required information"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Extract project ID from filename
        project_id = extract_project_id(os.path.basename(file_path))
        
        # Get basic state and root node
        basic_state = json_data.get('basic_state', {})
        all_nodes = basic_state.get('all_nodes', {})
        
        if 'root' not in all_nodes:
            print(f"Warning: No root node found in {file_path}")
            return None
        
        root_node = all_nodes['root']
        
        # Get project goal (question)
        project_goal = basic_state.get('overall_project_goal', '')
        question, answer = match_question_answer(project_goal, benchmark_data)
        
        # Get completion status
        root_status = root_node.get('status', 'UNKNOWN')
        completion_status = get_completion_status(root_status)
        
        # Extract result based on completion status
        if completion_status == 'completed':
            result = extract_result_from_node(root_node)
        else:
            # For failed/running, get result from last layer 1 node
            last_layer1_node = find_last_layer1_node(json_data)
            if last_layer1_node:
                result = extract_result_from_node(last_layer1_node)
            else:
                result = "No output generated"
        
        # Calculate execution time
        start_time = root_node.get('timestamp_created')
        end_time = root_node.get('timestamp_completed') or root_node.get('timestamp_updated')
        execution_time = calculate_execution_time(start_time, end_time)
        
        # Count nodes
        node_count = count_nodes(json_data)
        
        # Get evaluation timestamp
        eval_timestamp = root_node.get('timestamp_created', '')
        
        # Extract server URL if available (assuming localhost:5000 as default)
        server_url = "http://localhost:5000"  # Default as seen in example
        
        return {
            'question': question,
            'answer': answer,
            'result': result,
            'project_id': project_id,
            'execution_time': execution_time if execution_time else 0,
            'node_count': node_count,
            'completion_status': completion_status,
            'eval_timestamp': eval_timestamp,
            'server_url': server_url
        }
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def main():
    """Main function to process all JSON files and create reconstructed CSV"""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Reconstruct run results from project_results JSON files.")
    parser.add_argument(
        '--benchmark_file',
        type=str,
        default='evals/datasets/frames_benchmark.csv',
        help='Path to the benchmark CSV file.'
    )
    args = parser.parse_args()
    
    # Paths
    project_results_dir = Path("project_results")
    benchmark_file = Path(args.benchmark_file)
    output_file = Path("reconstructed_results.csv")
    
    # Load benchmark data
    print("Loading benchmark data...")
    benchmark_data = load_benchmark_data(benchmark_file)
    print(f"Loaded {len(benchmark_data)} benchmark questions")
    
    # Process all JSON files
    print("Processing project results...")
    results = []
    
    json_files = list(project_results_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files to process")
    
    for i, json_file in enumerate(json_files):
        if i % 100 == 0:
            print(f"Processing file {i+1}/{len(json_files)}: {json_file.name}")
        
        result = process_json_file(json_file, benchmark_data)
        if result:
            results.append(result)
    
    # Write results to CSV
    print(f"Writing {len(results)} results to {output_file}")
    
    fieldnames = ['question', 'answer', 'result', 'project_id', 'execution_time', 
                  'node_count', 'completion_status', 'eval_timestamp', 'server_url']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Successfully created {output_file}")
    
    # Print summary statistics
    completed = sum(1 for r in results if r['completion_status'] == 'completed')
    failed = sum(1 for r in results if r['completion_status'] == 'failed')
    running = sum(1 for r in results if r['completion_status'] == 'running')
    
    print(f"\nSummary:")
    print(f"Total results: {len(results)}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Running: {running}")

if __name__ == "__main__":
    main()