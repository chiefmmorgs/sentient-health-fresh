import argparse
import multiprocessing
import pandas as pd
import time
import traceback
from tqdm import tqdm
from threading import Lock
import queue
import os
import requests
import json
from datetime import datetime
import socketio as socketio_client
from typing import Dict, Any, Optional

result_lock = Lock()

class ServerEvaluationClient:
    """Client for communicating with the Sentient Research Agent server."""
    
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url
        self.session = requests.Session()
        self.sio = None
        self._connected = False
        
    def connect_websocket(self):
        """Connect to the server via WebSocket for real-time updates."""
        try:
            self.sio = socketio_client.Client()
            
            @self.sio.on('connect')
            def on_connect():
                print(f"✅ WebSocket connected to {self.server_url}")
                self._connected = True
                
            @self.sio.on('disconnect')
            def on_disconnect():
                print(f"❌ WebSocket disconnected from {self.server_url}")
                self._connected = False
                
            self.sio.connect(self.server_url)
            # Wait for connection
            timeout = 5
            start = time.time()
            while not self._connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"⚠️ Failed to connect WebSocket: {e}")
            
    def disconnect_websocket(self):
        """Disconnect WebSocket."""
        if self.sio:
            self.sio.disconnect()
            
    def create_configured_project(self, goal: str, config: Dict[str, Any], max_steps: int = 250) -> Optional[Dict[str, Any]]:
        """Create a project with custom configuration."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/projects/configured",
                json={
                    "goal": goal,
                    "config": config,
                    "max_steps": max_steps
                }
            )
            if response.status_code == 201:
                return response.json()
            else:
                print(f"❌ Failed to create project: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error creating project: {e}")
            return None
            
    def wait_for_project_completion(self, project_id: str, timeout: int = 1800) -> Dict[str, Any]:
        """Wait for a project to complete and return its final state."""
        start_time = time.time()
        last_status = None
        
        while (time.time() - start_time) < timeout:
            try:
                # Get project status
                response = self.session.get(f"{self.server_url}/api/projects/{project_id}")
                if response.status_code == 200:
                    project_data = response.json()
                    project = project_data.get('project', {})
                    status = project.get('status', 'unknown')
                    
                    if status != last_status:
                        print(f"📊 Project {project_id} status: {status}")
                        last_status = status
                    
                    if status in ['completed', 'failed']:
                        # Get the final project state with results
                        return self.get_project_results(project_id)
                        
                time.sleep(2)  # Poll every 2 seconds
                
            except Exception as e:
                print(f"⚠️ Error checking project status: {e}")
                time.sleep(5)
                
        # Timeout reached
        print(f"⏱️ Project {project_id} timed out after {timeout} seconds")
        return self.get_project_results(project_id)
        
    def get_project_results(self, project_id: str) -> Dict[str, Any]:
        """Get the complete results for a project."""
        try:
            # Try to get saved results first
            response = self.session.get(f"{self.server_url}/api/projects/{project_id}/load-results")
            if response.status_code == 200:
                return response.json()
                
            # Fallback to getting project state
            response = self.session.get(f"{self.server_url}/api/projects/{project_id}")
            if response.status_code == 200:
                return response.json()
                
            return {"error": "Failed to get project results"}
            
        except Exception as e:
            print(f"❌ Error getting project results: {e}")
            return {"error": str(e)}


def save_checkpoint(results, df, output_file, lock):
    """Save checkpoint with project IDs for frontend reference."""
    try:
        sorted_results = sorted(results, key=lambda x: x['index'])
        results_df = pd.DataFrame(sorted_results)
        
        # Copy original DataFrame
        output_df = df.copy()
        
        # Add all result columns
        for col in results_df.columns:
            if col != 'index':
                # Use iloc for positional indexing instead of loc with original indices
                for i, original_idx in enumerate(results_df['index']):
                    if original_idx in output_df.index:
                        output_df.loc[original_idx, col] = results_df.iloc[i][col]
                
        output_df.to_csv(output_file, index=False)
        print(f"💾 [Checkpoint] Saved {len(results)} results -> {output_file}")
        
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint: {e}")


def evaluation_worker(task_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue, 
                     worker_config: dict):
    """Worker that creates projects via the server API."""
    process_name = multiprocessing.current_process().name
    
    # Create a client for this worker
    client = ServerEvaluationClient(worker_config['server_url'])
    
    # Optionally connect WebSocket for monitoring (not required for basic operation)
    if worker_config.get('enable_websocket', False):
        client.connect_websocket()
    
    print(f"🤖 [{process_name}] Worker initialized, connected to {worker_config['server_url']}")
    
    while True:
        try:
            task = task_queue.get(timeout=1)
            if task is None:
                # Sentinel value - put it back for other workers
                task_queue.put(None)
                break
        except queue.Empty:
            continue
            
        query, idx = task
        
        try:
            print(f"🚀 [{process_name}] Creating project for query #{idx+1}: '{query}'")
            start_time = time.time()
            
            # Add delay to avoid rate limiting
            if worker_config.get('request_delay', 0) > 0:
                delay = worker_config['request_delay']
                print(f"⏱️ [{process_name}] Waiting {delay}s before request (rate limiting)")
                time.sleep(delay)
            
            # Create the project with configuration
            project_response = client.create_configured_project(
                goal=query,
                config=worker_config['agent_config'],
                max_steps=worker_config['max_steps']
            )
            
            if not project_response:
                result_queue.put({
                    'query': query,
                    'result': 'Error: Failed to create project',
                    'index': idx,
                    'error': True
                })
                continue
                
            project_id = project_response['project']['id']
            print(f"✅ [{process_name}] Created project {project_id} for query #{idx+1}")
            
            # Wait for completion
            final_results = client.wait_for_project_completion(
                project_id, 
                timeout=worker_config.get('execution_timeout', 1800)
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Extract the final output
            final_output = "No output generated"
            
            # Try different paths to find the result
            if 'basic_state' in final_results:
                graph_data = final_results.get('basic_state', {})
            elif 'graph_data' in final_results:
                graph_data = final_results.get('graph_data', {})
            elif 'state' in final_results:
                graph_data = final_results.get('state', {})
            else:
                graph_data = final_results
                
            # Find root node result with more robust error handling
            all_nodes = graph_data.get('all_nodes', {})
            for node_key, node in all_nodes.items():
                try:
                    # FIX: More robust handling of different node types
                    if isinstance(node, str):
                        try:
                            node = json.loads(node)
                        except (json.JSONDecodeError, TypeError):
                            print(f"⚠️ Skipping invalid JSON node: {node_key}")
                            continue
                    
                    if not isinstance(node, dict):
                        print(f"⚠️ Skipping non-dict node: {node_key} (type: {type(node)})")
                        continue
                    
                    # Safe access with .get() method
                    layer = node.get('layer')
                    parent_node_id = node.get('parent_node_id')
                    
                    if layer == 0 and not parent_node_id:
                        # This is the root node - extract result safely
                        full_result = node.get('full_result', {})
                        
                        # Ensure full_result is a dict
                        if not isinstance(full_result, dict):
                            full_result = {}
                        
                        if full_result.get('output_text_with_citations'):
                            final_output = full_result['output_text_with_citations']
                        elif full_result.get('output_text'):
                            final_output = full_result['output_text']
                        elif node.get('output_summary'):
                            final_output = node['output_summary']
                        break
                        
                except Exception as e:
                    print(f"⚠️ Error processing node {node_key}: {e}")
                    continue
                
            print(f"✅ [{process_name}] Completed query #{idx+1} in {execution_time:.2f}s")
            
            result_queue.put({
                'query': query,
                'result': final_output,
                'index': idx,
                'project_id': project_id,  # Store project ID for frontend reference
                'execution_time': execution_time,
                'node_count': len(all_nodes),
                'completion_status': final_results.get('metadata', {}).get('completion_status', 'unknown')
            })
            
        except Exception as e:
            print(f"❌ [{process_name}] Error on query #{idx+1}: {e}")
            traceback.print_exc()
            result_queue.put({
                'query': query,
                'result': f"Error: {str(e)}",
                'index': idx,
                'error': True
            })
            
    # Cleanup
    if worker_config.get('enable_websocket', False):
        client.disconnect_websocket()
    print(f"🏁 [{process_name}] Worker finished")


def main():
    parser = argparse.ArgumentParser(description="Run evaluations through the Sentient Agent Server")
    parser.add_argument("--input-file", type=str, default="datasets/seal-0.csv", 
                       help="Path to the input CSV/parquet file with queries")
    parser.add_argument("--output-file", default="server_eval_results.csv", type=str, 
                       help="Path to save the results CSV file")
    parser.add_argument("--query-column", type=str, default="question", 
                       help="Name of the column containing queries")
    parser.add_argument("--num-examples", type=int, default=None, 
                       help="Number of examples to run")
    parser.add_argument("--start-idx", type=int, default=None, 
                       help="Start index for batch processing (inclusive)")
    parser.add_argument("--end-idx", type=int, default=None, 
                       help="End index for batch processing (exclusive)")
    parser.add_argument("--checkpoint-interval", type=int, default=10, 
                       help="Number of queries between checkpoints")
    parser.add_argument("--checkpoint-file", type=str, default="server_checkpoint.csv", 
                       help="Path to save checkpoint file")
    
    # Server settings
    parser.add_argument("--server-url", type=str, default="http://localhost:5000", 
                       help="URL of the Sentient Agent server")
    parser.add_argument("--enable-websocket", action='store_true', 
                       help="Enable WebSocket monitoring")
    
    # Agent configuration
    parser.add_argument("--profile-name", type=str, default="general_agent", 
                       help="Agent profile name")
    parser.add_argument("--enable-hitl", action='store_true', 
                       help="Enable HITL (Human-in-the-loop)")
    parser.add_argument("--max-concurrent-tasks", type=int, default=10, 
                       help="Maximum concurrent tasks")
    parser.add_argument("--max-planning-depth", type=int, default=3, 
                       help="Maximum planning depth")
    parser.add_argument("--max-steps", type=int, default=250, 
                       help="Maximum execution steps per query")
    parser.add_argument("--execution-timeout", type=int, default=1800, 
                       help="Timeout for each execution in seconds")
    
    # Rate limiting settings
    parser.add_argument("--request-delay", type=float, default=5.0, 
                       help="Delay between requests in seconds (to avoid rate limiting)")
    
    # Multiprocessing settings
    parser.add_argument("--num-processes", type=int, default=min(2, multiprocessing.cpu_count()), 
                       help="Number of parallel processes (default: 2 to avoid rate limiting)")
    
    args = parser.parse_args()
    
    # Test server connection
    print(f"🔍 Testing connection to server at {args.server_url}...")
    try:
        response = requests.get(f"{args.server_url}/api/system-info")
        if response.status_code == 200:
            system_info = response.json()
            print(f"✅ Connected to server - Profile: {system_info.get('current_profile')}")
        else:
            print(f"❌ Server returned status {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Failed to connect to server: {e}")
        print("Make sure the server is running with: python -m sentientresearchagent.server")
        return
    
    # Load dataset
    try:
        df = pd.read_csv(args.input_file)
        
        # Handle batch processing with start/end indices
        start_idx = args.start_idx if args.start_idx is not None else 0
        end_idx = args.end_idx if args.end_idx is not None else len(df)
        
        # Apply slicing if indices are specified
        if args.start_idx is not None or args.end_idx is not None:
            # Validate indices
            if start_idx < 0 or start_idx >= len(df):
                print(f"Error: start_idx {start_idx} is out of range [0, {len(df)})")
                return
            if end_idx <= start_idx or end_idx > len(df):
                print(f"Error: end_idx {end_idx} must be > start_idx {start_idx} and <= {len(df)}")
                return
                
            print(f"📋 Processing batch: indices {start_idx} to {end_idx-1} ({end_idx-start_idx} examples)")
            df = df.iloc[start_idx:end_idx]
        elif args.num_examples:
            df = df.iloc[:args.num_examples]
            
        if args.query_column not in df.columns:
            print(f"Error: Query column '{args.query_column}' not found")
            return
        queries = df[args.query_column].tolist()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return
    
    # Load checkpoint if it exists
    processed_indices = set()
    existing_results = []
    
    if os.path.exists(args.checkpoint_file):
        print(f"🔄 Found checkpoint file: {args.checkpoint_file}")
        try:
            checkpoint_df = pd.read_csv(args.checkpoint_file)
            # Determine which queries have been processed successfully
            if 'index' in checkpoint_df.columns:
                # Case 1: Checkpoint has explicit index column
                if 'completion_status' in checkpoint_df.columns:
                    print("✅ Using 'completion_status' column for resume logic")
                    completed_mask = checkpoint_df['completion_status'] == 'completed'
                else:
                    print("⚠️ 'completion_status' column not found, falling back to result/error check")
                    completed_mask = (
                        checkpoint_df['result'].notna() & 
                        (checkpoint_df['result'].str.strip() != '') &
                        (checkpoint_df.get('error', False) != True)
                    )
                completed_rows = checkpoint_df[completed_mask]
                processed_indices = set(completed_rows['index'].tolist())
                existing_results = completed_rows.to_dict('records')
            else:
                # Case 2: Match questions by content instead of position
                print("🔍 No 'index' column found, matching questions by content")
                if 'completion_status' in checkpoint_df.columns:
                    print("✅ Using 'completion_status' column for resume logic")
                    completed_mask = checkpoint_df['completion_status'] == 'completed'
                else:
                    print("⚠️ 'completion_status' column not found, falling back to result/error check")
                    completed_mask = (
                        checkpoint_df['result'].notna() & 
                        (checkpoint_df['result'].str.strip() != '') &
                        (checkpoint_df.get('error', False) != True)
                    )
                completed_rows = checkpoint_df[completed_mask].copy()
                
                # Find which questions from the original dataset are completed
                completed_questions = set(completed_rows['question'].tolist())
                processed_indices = set()
                
                # Match completed questions to their indices in the original dataset
                for i, query in enumerate(queries):
                    if query in completed_questions:
                        processed_indices.add(i)
                        
                # Add index column for existing results
                completed_rows['index'] = [i for i, q in enumerate(queries) if q in completed_questions]
                existing_results = completed_rows.to_dict('records')
            
            total_in_checkpoint = len(checkpoint_df)
            completed_count = len(completed_rows)
            failed_or_incomplete = total_in_checkpoint - completed_count
            
            print(f"✅ Resuming from checkpoint: {completed_count} queries completed successfully")
            if failed_or_incomplete > 0:
                print(f"🔄 Will re-run {failed_or_incomplete} failed/incomplete queries")
        except Exception as e:
            print(f"⚠️ Error loading checkpoint: {e}, starting fresh")
    
    # Prepare worker configuration
    worker_config = {
        'server_url': args.server_url,
        'enable_websocket': args.enable_websocket,
        'max_steps': args.max_steps,
        'execution_timeout': args.execution_timeout,
        'request_delay': args.request_delay,
        'agent_config': {
            'active_profile_name': args.profile_name,  # Pass the profile name
            'llm': {
                'provider': 'openai',
                'model': 'gpt-4o',
                'temperature': 0.7
            },
            'execution': {
                'enable_hitl': args.enable_hitl,
                'hitl_root_plan_only': True,
                'max_concurrent_nodes': min(2, args.max_concurrent_tasks),  # Limit concurrent nodes for rate limiting
                'max_recursion_depth': args.max_planning_depth,
                'max_execution_steps': args.max_steps,
                'rate_limit_rpm': 20,  # Conservative rate limit for evaluations
                'hitl_timeout_seconds': 300,
                'hitl_after_plan_generation': False,
                'hitl_after_modified_plan': False,
                'hitl_after_atomizer': False,
                'hitl_before_execute': False
            },
            'cache': {
                'enabled': True,
                'ttl_seconds': 3600,
                'max_size': 1000,
                'cache_type': 'file'
            }
        }
    }
    
    # Create queues
    task_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()
    
    # Enqueue only unprocessed tasks
    queries_to_process = [(query, i) for i, query in enumerate(queries) if i not in processed_indices]
    
    if not queries_to_process:
        print("✅ All queries already processed!")
        return
    
    print(f"📋 Processing {len(queries_to_process)} out of {len(queries)} total queries")
    
    for query, i in queries_to_process:
        task_queue.put((query, i))
    
    # Add sentinel values
    for _ in range(args.num_processes):
        task_queue.put(None)
    
    # Start worker processes with staggered startup
    processes = []
    print(f"🏁 Starting {args.num_processes} worker processes for {len(queries_to_process)} queries...")
    for i in range(args.num_processes):
        process = multiprocessing.Process(
            target=evaluation_worker,
            args=(task_queue, result_queue, worker_config),
            name=f"EvalWorker-{i+1}"
        )
        processes.append(process)
        process.start()
    
    # Collect results (start with existing results from checkpoint)
    results = existing_results.copy()
    num_queries_to_process = len(queries_to_process)
    
    # Create batch-aware filenames
    if args.start_idx is not None or args.end_idx is not None:
        batch_suffix = f"_{start_idx}_{end_idx}"
        # Update output filenames to include batch info
        base_output = args.output_file.rsplit('.', 1)
        if len(base_output) == 2:
            args.output_file = f"{base_output[0]}{batch_suffix}.{base_output[1]}"
        else:
            args.output_file = f"{args.output_file}{batch_suffix}"
            
        base_checkpoint = args.checkpoint_file.rsplit('.', 1)
        if len(base_checkpoint) == 2:
            args.checkpoint_file = f"{base_checkpoint[0]}{batch_suffix}.{base_checkpoint[1]}"
        else:
            args.checkpoint_file = f"{args.checkpoint_file}{batch_suffix}"
    
    # Add timestamp for tracking
    eval_start_time = datetime.now()
    
    with tqdm(total=num_queries_to_process, desc="Processing queries", ncols=100, initial=0) as pbar:
        processed_count = 0
        while processed_count < num_queries_to_process:
            try:
                result = result_queue.get(timeout=300)
                with result_lock:
                    results.append(result)
                    processed_count += 1
                    pbar.update(1)
                    
                    # Show project ID for frontend reference
                    if 'project_id' in result:
                        print(f"📊 Progress: {len(existing_results) + processed_count}/{len(queries)} - "
                              f"Latest project: {result['project_id']}")
                    
                    if len(results) % args.checkpoint_interval == 0:
                        save_checkpoint(results, df, args.checkpoint_file, result_lock)
                        
            except queue.Empty:
                print("⏱️ Timeout waiting for results. Checking worker status...")
                if not any(p.is_alive() for p in processes):
                    print("❌ All workers terminated unexpectedly")
                    break
    
    # Wait for all processes
    for process in processes:
        process.join()
    
    print("\n✅ All evaluations completed")
    
    # Save final results
    if results:
        results.sort(key=lambda x: x['index'])
        
        output_df = df.copy()
        # Map results back to original dataframe by index
        result_map = {r['index']: r for r in results}
        for idx in range(len(df)):
            if idx in result_map:
                for col, val in result_map[idx].items():
                    if col != 'index' and col != 'query':  # Don't overwrite query column
                        output_df.loc[idx, col] = val
        
        # Add evaluation metadata
        output_df['eval_timestamp'] = eval_start_time.isoformat()
        output_df['server_url'] = args.server_url
        
        output_df.to_csv(args.output_file, index=False)
        print(f"💾 Results saved to {args.output_file}")
        
        # Clean up checkpoint file after successful completion (only if different from output file)
        if os.path.exists(args.checkpoint_file) and args.checkpoint_file != args.output_file:
            os.remove(args.checkpoint_file)
            print(f"🧹 Cleaned up checkpoint file: {args.checkpoint_file}")
        
        # Print summary
        print("\n📊 Evaluation Summary:")
        print(f"  Total queries: {len(results)}")
        print(f"  Successful: {sum(1 for r in results if not r.get('error', False))}")
        print(f"  Failed: {sum(1 for r in results if r.get('error', False))}")
        if any('execution_time' in r for r in results):
            avg_time = sum(r.get('execution_time', 0) for r in results) / len(results)
            print(f"  Average execution time: {avg_time:.2f} seconds")
        
        # Print project IDs for frontend reference
        print("\n🌐 Projects created (viewable in frontend):")
        for i, result in enumerate(results[:5]):  # Show first 5
            if 'project_id' in result:
                print(f"  - {result['project_id']}: {result['query'][:50]}...")
        if len(results) > 5:
            print(f"  ... and {len(results) - 5} more")
            
    else:
        print("No results were generated")


if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    main() 