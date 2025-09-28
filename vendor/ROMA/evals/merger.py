import pandas as pd

frames = []


for i in range(1,5):
    df = pd.read_csv(f"final_results_odr_{i}.csv")
    print(df['is_correct'].sum())
    frames.append(df)

'''temp_df = pd.read_csv("final_results_0528_missing_evals.csv")
print(temp_df['is_correct'].sum())
frames.append(temp_df)'''

results_df = pd.concat(frames)
#results_df = results_df.drop_duplicates(subset='problem',keep='first')

results_df.to_csv("final_results_odr.csv", index=False)

total_correct = results_df['is_correct'].sum()
print(f"TOTAL CORRECT: {total_correct}")
print(f"RATE: {total_correct}/{results_df.shape[0]} or {total_correct/results_df.shape[0]}")