import pandas as pd
import argparse
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import os
from litellm import completion

def extract_final_answer(query: str, result: str, model: str = "openrouter/google/gemini-2.5-flash") -> str:
    """Extract the final answer from a verbose result using LiteLLM."""
    prompt = f"""Given the following query and verbose result, extract ONLY the final answer.
    Return just the exact final answer with no additional text, explanations, or formatting.

    Query: {query}

    Verbose Result: {result}

    Final Answer:"""

    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    final_answer = response.choices[0].message.content.strip()
    return final_answer

def process_row_data(question, result):
    """
    Worker function that takes a question and result, then calls the extraction function.
    This function will be executed in a separate process.
    """
    if pd.isna(question) or pd.isna(result):
        return None
    try:
        return extract_final_answer(query=question, result=result)
    except Exception as e:
        print(f"Error extracting answer for question '{question[:50]}...': {e}")
        return None

def main(input_csv_path: str):
    """
    Main function to read a CSV, process it in parallel, and save the results.
    """
    print(f"Loading data from {input_csv_path}...")
    try:
        df = pd.read_csv(input_csv_path)
    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found.")
        return

    # Ensure required columns exist
    if 'question' not in df.columns or 'result' not in df.columns:
        print("Error: Input CSV must contain 'question' and 'result' columns.")
        return

    questions = df['question']
    results = df['result']
    
    extracted_answers = []
    print("Processing rows in parallel... (This may take a while depending on the number of rows)")

    with ProcessPoolExecutor() as executor:
        # executor.map processes the iterables (questions, results) in parallel
        # and returns the results in order. tqdm provides a progress bar.
        extracted_answers = list(tqdm(executor.map(process_row_data, questions, results), total=len(df)))

    df['extracted_answer'] = extracted_answers

    # Create a new filename for the output
    base, ext = os.path.splitext(input_csv_path)
    output_csv_path = f"{base}_extracted{ext}"
    
    print(f"Saving processed data to {output_csv_path}...")
    df.to_csv(output_csv_path, index=False)
    print("Processing complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract final answers from evaluation results in parallel using an LLM.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "csv_file", 
        help="Path to the input CSV file. The file must contain 'question' and 'result' columns."
    )
    args = parser.parse_args()

    # You might need to install pandas, tqdm, and litellm: 
    # pip install pandas tqdm litellm
    main(args.csv_file) 