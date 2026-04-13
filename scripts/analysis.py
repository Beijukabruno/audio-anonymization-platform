import pandas as pd
import numpy as np

SIMON_NAMES = [
    '',
    'NAMATIITI SIMON PETER',
    'NAMATIITTI SIMON PETER',
    'NAMATTITI SIMON PETER'
]
NEW_NAME = 'Simon'

csv_path = 'ioa_annotations_20260318_074443.csv'
df = pd.read_csv(csv_path)
df['Operator'] = df['Operator'].replace(SIMON_NAMES, NEW_NAME)

audio_ops = df.groupby('Audio File')['Operator'].nunique()
shared_audios = audio_ops[audio_ops > 1].index.tolist()

report_rows = []
disagreement_rows = []
def compute_overlap(row1, row2):
    start = max(row1['Start'], row2['Start'])
    end = min(row1['Stop'], row2['Stop'])
    return max(0, end - start)

def segment_agreement(seg1, seg2, overlap_thresh=0.5):
    overlap = compute_overlap(seg1, seg2)
    return overlap >= overlap_thresh and seg1['Label'] == seg2['Label']

for audio in shared_audios:
    sub = df[df['Audio File'] == audio]
    ops = sub['Operator'].unique()
    if len(ops) < 2:
        continue
    op1, op2 = ops[:2]
    segs1 = sub[sub['Operator'] == op1].reset_index(drop=True)
    segs2 = sub[sub['Operator'] == op2].reset_index(drop=True)
    matched = []
    unmatched_op1 = []
    unmatched_op2 = []
    for i, r1 in segs1.iterrows():
        found = False
        for j, r2 in segs2.iterrows():
            if segment_agreement(r1, r2):
                matched.append((i, j, r1['Label'], r1['Start'], r1['Stop'], r2['Start'], r2['Stop'], compute_overlap(r1, r2)))
                found = True
        if not found:
            unmatched_op1.append((r1['Label'], r1['Start'], r1['Stop']))
            disagreement_rows.append({
                'Audio File': audio,
                'Operator': op1,
                'Label': r1['Label'],
                'Start': r1['Start'],
                'Stop': r1['Stop']
            })
    for j, r2 in segs2.iterrows():
        found = False
        for i, r1 in segs1.iterrows():
            if segment_agreement(r1, r2):
                found = True
        if not found:
            unmatched_op2.append((r2['Label'], r2['Start'], r2['Stop']))
            disagreement_rows.append({
                'Audio File': audio,
                'Operator': op2,
                'Label': r2['Label'],
                'Start': r2['Start'],
                'Stop': r2['Stop']
            })
    # Summary row for report
    report_rows.append({
        'Audio File': audio,
        f'{op1} Segments': len(segs1),
        f'{op2} Segments': len(segs2),
        'Matched Segments': len(matched),
        f'{op1} Unique': len(unmatched_op1),
        f'{op2} Unique': len(unmatched_op2),
        'Agreement Ratio': round(len(matched) / (len(segs1) * len(segs2)), 2) if len(segs1) and len(segs2) else 0,
    })
    # Save detailed breakdown for each audio
    with open(f'report_{audio}.txt', 'w') as f:
        f.write(f'Audio: {audio}\n')
        f.write(f'Total segments {op1}: {len(segs1)}, {op2}: {len(segs2)}\n')
        f.write(f'Matched segments: {len(matched)}\n')
        f.write(f'{op1} segments not matched: {len(unmatched_op1)}\n')
        f.write(f'{op2} segments not matched: {len(unmatched_op2)}\n')
        if matched:
            f.write('\nMatched segments (label, op1 start-stop, op2 start-stop, overlap):\n')
            for m in matched:
                f.write(f'  {m[2]} [{m[3]}-{m[4]}] vs [{m[5]}-{m[6]}], overlap: {m[7]:.2f}\n')
        if unmatched_op1:
            f.write(f'\n{op1} unique selections:\n')
            for label, start, stop in unmatched_op1:
                f.write(f'  {label} [{start}-{stop}]\n')
        if unmatched_op2:
            f.write(f'\n{op2} unique selections:\n')
            for label, start, stop in unmatched_op2:
                f.write(f'  {label} [{start}-{stop}]\n')
        f.write('\n---\n')

# Save summary CSV
report_df = pd.DataFrame(report_rows)
report_df.to_csv('inter_operator_agreement_summary.csv', index=False)
disagreement_df = pd.DataFrame(disagreement_rows)
disagreement_df.to_csv('disagreement_segments.csv', index=False)
print('Summary report saved to inter_operator_agreement_summary.csv')
print('Disagreement segments saved to disagreement_segments.csv')
print('Detailed breakdowns saved to report_<audio>.txt files.')