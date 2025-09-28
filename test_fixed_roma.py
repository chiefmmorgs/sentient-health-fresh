import logging, json
from datetime import datetime
from roma_engine.sentient_roma_runner import SentientROMARunner

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def show(runner):
    print("Summary:", json.dumps(runner.get_execution_summary(), indent=2))

def test_simple_task():
    runner = SentientROMARunner(max_depth=3, max_subtasks=4)
    task = {"name":"daily_health_check","type":"analysis","description":"Analyze today's metrics",
            "data":{"date": datetime.now().isoformat(),"metrics":["heart_rate","steps","sleep"]}}
    result = runner.solve(task)
    print("Result:", json.dumps(result, indent=2)); show(runner)
    assert runner.get_execution_summary()["max_depth_reached"] <= 3

def test_complex_task():
    runner = SentientROMARunner(max_depth=4, max_subtasks=5)
    task = {"name":"create_personalized_health_plan","type":"planning","description":"30-day plan",
            "data":{"goals":["sleep","steps"]}}
    runner.solve(task)
    assert runner.get_execution_summary()["max_depth_reached"] <= 4

def test_edge_cases():
    runner = SentientROMARunner(max_depth=2, max_subtasks=3)
    runner.solve({"name":"empty_task"})
    assert runner.get_execution_summary()["max_depth_reached"] <= 2
    runner.solve({"name":"analyze_analysis_of_analysis","type":"analysis"})
    assert runner.get_execution_summary()["max_depth_reached"] <= 2

if __name__ == "__main__":
    print("🚀 Testing Fixed ROMA System")
    test_simple_task(); test_complex_task(); test_edge_cases()
    print("🎉 Tests completed")
