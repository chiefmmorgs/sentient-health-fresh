import multiprocessing
import time
import traceback
from sentientresearchagent.framework_entry import ProfiledSentientAgent

def run_agent_execution(query: str, queue: multiprocessing.Queue):
    """
    A target function for each process to execute a query.
    It creates its own agent instance in its own memory space.
    """
    process_name = multiprocessing.current_process().name
    
    try:
        # Each process creates its own agent instance. This guarantees
        # that all state, including the agent registry, is completely isolated.
        print(f"🤖 [{process_name}] Creating a dedicated agent instance in a new process...")
        agent = ProfiledSentientAgent.create_with_profile(
            profile_name="general_agent",
            enable_hitl_override=False,
            max_concurrent_tasks=10,
            max_planning_depth=3
        )
        
        print(f"🚀 [{process_name}] Starting execution for query: '{query}'")
        start_time = time.time()

        result = agent.execute(goal=query)

        end_time = time.time()
        print(f"✅ [{process_name}] Finished in {end_time - start_time:.2f} seconds.")

        # In multiprocessing, returning complex objects can be tricky.
        # For this example, we'll just print a summary.
        final_output = result.get('final_output', 'No output generated.')
        print(f"📄 [{process_name}] Result for '{query}':\n   {final_output[:200].replace('\n', '\n   ')}...\n")

        # Put the result into the queue
        queue.put(final_output)

    except Exception as e:
        end_time = time.time()
        print(f"❌ [{process_name}] An error occurred: {e}")
        traceback.print_exc()
        # Optionally, put an error message into the queue
        queue.put(f"Error: {e}")