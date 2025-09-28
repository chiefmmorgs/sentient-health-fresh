import pandas as pd
import argparse
import re
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import os
from litellm import completion

def grade_answer_with_llm(question: str, ground_truth: str, predicted_answer: str, model: str = "openrouter/google/gemini-2.5-flash") -> int:
    """
    Grades the predicted_answer against the ground_truth using an LLM.
    """
    prompt = f"""You are an expert evaluator. Your task is to determine if the "Predicted Answer" is factually and semantically correct based on the "Ground Truth Answer", in the context of the original "Question".

Respond with ONLY "1" for a correct match or "0" for an incorrect match. Do not provide any other text or explanation.

**Examples of CORRECT answers:**
'''
Question: What are the names of Barack Obama’s children?
Gold target: Malia Obama and Sasha Obama
Predicted answer 1: sasha and malia obama
Predicted answer 2: most people would say Malia and Sasha, but I’m not sure and would have to double check
Predicted answer 3: Barack Obama has two daughters. Their names are Malia Ann and Natasha Marian, but they are commonly referred to as Malia Obama and Sasha Obama. Malia was born on July 4, 1998, and Sasha was born on June 10, 2001.
'''

**Grading Criteria:**
1.  **Semantic Equivalence:** The meaning must be the same, even if phrasing, capitalization, punctuation, grammar, or order are different. For example, "first place" is the same as "1st" or "number 1".
2.  **Completeness & Accuracy:** The predicted answer must fully contain the important information in the gold target and must not contain any information that contradicts the gold target.
3.  **Hedging:** Hedging and guessing (e.g., "I think...", "I'm not sure but...") are permissible, as long as the answer is still complete and accurate according to the criteria above.
4.  **Numerical Tolerance:** For numerical answers, a 1% margin of error is allowed.
5.  **Date Tolerance:** Dates that are off by 1 day or unit are considered correct.

**Grade the following example:**

**Question:** {question}

**Ground Truth Answer:** {ground_truth}

**Predicted Answer:** {predicted_answer}

**Grade (1 or 0):**"""

    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        grade = response.choices[0].message.content.strip()
        return 1 if grade == "1" else 0
    except Exception as e:
        print(f"An error occurred during LLM grading: {e}")
        return 0 # Default to incorrect on error

def parse_number(s: str) -> float | None:
    """
    Parses the first number found in a string, ignoring commas.
    """
    if not isinstance(s, str):
        return None
    # Look for numerical values, including those with commas and decimals
    numbers = re.findall(r'-?[\d,]*\.?\d+', s)
    if numbers:
        try:
            # Take the first number found, remove commas, and convert to float
            return float(numbers[0].replace(',', ''))
        except (ValueError, IndexError):
            return None
    return None

def process_grading_row(data_tuple):
    """
    Worker function to grade a single row. First attempts a direct numerical comparison,
    then falls back to an LLM for semantic comparison.
    """
    question, ground_truth, predicted_answer = data_tuple

    if pd.isna(ground_truth) or pd.isna(predicted_answer):
        return 0

    # Step 1: Attempt numerical comparison first for efficiency and precision
    gt_num = parse_number(str(ground_truth))
    pred_num = parse_number(str(predicted_answer))

    if gt_num is not None and pred_num is not None:
        if gt_num == 0 and pred_num == 0:
            return 1 # Exact match for zero
        if gt_num != 0:
            # Check for 1% tolerance
            if abs((pred_num - gt_num) / gt_num) <= 0.01:
                return 1

    # Step 2: If not clearly numerical or if they don't match, fall back to LLM
    try:
        return grade_answer_with_llm(question, str(ground_truth), str(predicted_answer))
    except Exception as e:
        print(f"Error processing row for question '{str(question)[:50]}...': {e}")
        return 0

def main(input_csv_path: str):
    """
    Main function to read a CSV, grade answers in parallel, and save the results.
    """
    print(f"Loading data from {input_csv_path}...")
    try:
        df = pd.read_csv(input_csv_path)
    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found.")
        return

    required_cols = ['question', 'answer', 'extracted_answer']
    if not all(col in df.columns for col in required_cols):
        print(f"Error: Input CSV must contain {required_cols} columns.")
        return

    # Create tuples of the data for parallel processing
    grading_data = list(df[required_cols].itertuples(index=False, name=None))
    
    grades = []
    print("Grading answers in parallel... (This may take a while)")

    with ProcessPoolExecutor() as executor:
        grades = list(tqdm(executor.map(process_grading_row, grading_data), total=len(df)))

    df['grade'] = grades

    base, ext = os.path.splitext(input_csv_path)
    output_csv_path = f"{base}_graded{ext}"
    
    print(f"Saving graded data to {output_csv_path}...")
    df.to_csv(output_csv_path, index=False)
    print("Grading complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Grade extracted answers against ground truth answers in a CSV file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "csv_file", 
        help="Path to the input CSV file. Must contain 'question', 'answer', and 'extracted_answer' columns."
    )
    args = parser.parse_args()

    # You might need to install pandas, tqdm, and litellm: 
    # pip install pandas tqdm litellm
    main(args.csv_file)
