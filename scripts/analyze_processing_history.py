import pandas as pd
from collections import Counter

def main():
    # Load CSV
    df = pd.read_csv('processing_history_20260223_100815.csv')

    print("\n--- Surrogate Usage Summary ---")
    surrogate_stats = df.groupby(['Surrogate', 'Gender', 'Language']).size().reset_index(name='Count')
    print(surrogate_stats.to_string(index=False))

    print("\n--- Method Distribution ---")
    method_stats = df['Method'].value_counts()
    print(method_stats.to_string())

    print("\n--- Error Summary ---")
    error_rows = df[(df['Status'] != 'completed') | (df['Error'].notna() & (df['Error'] != ''))]
    if not error_rows.empty:
        print(error_rows[['ID', 'Filename', 'Status', 'Error']].to_string(index=False))
    else:
        print("No errors found.")

    print("\n--- Inter-Annotator Agreement ---")
    agreement = []
    for fname, group in df.groupby('Filename'):
        surrogates = set(group['Surrogate'])
        if len(surrogates) > 1:
            agreement.append({'Filename': fname, 'Surrogates': list(surrogates), 'Agreement': 'No'})
        else:
            agreement.append({'Filename': fname, 'Surrogates': list(surrogates), 'Agreement': 'Yes'})
    agreement_df = pd.DataFrame(agreement)
    total = len(agreement_df)
    disagreed = agreement_df[agreement_df['Agreement'] == 'No']
    print(f"Agreement rate: {100*(total-len(disagreed))/total:.2f}%")
    print(f"Disagreement rate: {100*len(disagreed)/total:.2f}%")
    if not disagreed.empty:
        print(disagreed[['Filename', 'Surrogates']].to_string(index=False))
    else:
        print("All files have consistent surrogate assignments.")

if __name__ == '__main__':
    main()
