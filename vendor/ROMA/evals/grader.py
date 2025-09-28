import os
import pandas as pd
import re
import argparse
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = "You are a strict, high-precision evaluation assistant. Your job is to assess the correctness of answers by comparing model-generated responses against authoritative correct answers. You must focus only on whether the final answer matches, without solving the problem or adding any commentary. Be objective, literal, and rule-following."

def create_prompt(problem: str, response: str, answer: str) -> str:
    """Creates the prompt for the grading model."""
    return f"""
Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {problem}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.
""".strip()

def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Grade model responses against correct answers.")
    parser.add_argument("--input-file", required=True, help="Path to the input CSV file.")
    parser.add_argument("--output-file", help="Path to the output CSV file. If not provided, it defaults to '{input_file_name}_graded.csv' in the same directory.")
    parser.add_argument("--model", default="accounts/fireworks/models/deepseek-r1-0528", help="Model to use for evaluation.")
    parser.add_argument("--batch-size", type=int, default=30, help="Batch size for saving intermediate results.")
    parser.add_argument("--api-base-url", default="https://api.fireworks.ai/inference/v1", help="Base URL for the API.")
    parser.add_argument("--start-index", type=int, default=0, help="Start index for processing rows from the input file.")
    parser.add_argument("--end-index", type=int, default=None, help="End index for processing rows from the input file.")
    return parser.parse_args()

def main():
    """Main function to run the grading process."""
    args = parse_args()

    api_key = os.environ.get("FIREWORKS_AI_API_KEY")
    if not api_key:
        print("Error: Environment variable FIREWORKS_AI_API_KEY not set.")
        return

    client = OpenAI(api_key=api_key, base_url=args.api_base_url)

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at {args.input_file}")
        return

    try:
        df = pd.read_csv(args.input_file)
        inputs = df.to_dict('records')
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    inputs = inputs[args.start_index:args.end_index]
    
    print(f"Processing {len(inputs)} records.")
    print(f"Using model: {args.model}")

    results = []
    correct_count = 0
    
    if args.output_file:
        output_file = args.output_file
    else:
        input_dir = os.path.dirname(args.input_file) or '.'
        base_name = os.path.splitext(os.path.basename(args.input_file))[0]
        output_file = os.path.join(input_dir, f"{base_name}_graded.csv")
    
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    output_prefix = os.path.splitext(output_file)[0]
    batch_count = 0

    for i, row in enumerate(inputs):
        try:
            problem = row["question"].split("Your response should be in the following format:")[0].strip()
            prompt = create_prompt(problem, row["result"], row["answer"])

            response = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            model_ans = response.choices[0].message.content
            match = re.search(r"correct:\s*(yes|no)", model_ans, re.IGNORECASE)
            
            is_correct = None
            is_correct_str = 'N/A'
            if match:
                is_correct_str = match.group(1).lower()
                is_correct = 1 if is_correct_str == "yes" else 0
                if is_correct == 1:
                    correct_count += 1
            
            print(f"Processed record {i+1}/{len(inputs)} -> Correct: {is_correct_str}")

            results.append({
                'problem': problem,
                'agent_answer': row["result"],
                'full_answer': model_ans,
                'correct_answer': row["answer"],
                'is_correct': is_correct
            })

            if (i + 1) % args.batch_size == 0 and results:
                batch_count += 1
                batch_filename = f'{output_prefix}_batch_{batch_count}.csv'
                pd.DataFrame(results).to_csv(batch_filename, index=False)
                print(f"Saved batch to {batch_filename}")

        except Exception as e:
            print(f"Error processing record at index {i} (input file row {args.start_index + i}): {e}")
            continue

    pd.DataFrame(results).to_csv(output_file, index=False)
    print(f"\nSaved final results to {output_file}")

    if results:
        print(f"TOTAL CORRECT COUNT: {correct_count}/{len(results)} ({correct_count/len(results):.2%})")

if __name__ == "__main__":
    main()