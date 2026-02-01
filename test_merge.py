# Test merge logic
candidates = [
    {'text': 'MF3NA81DE', 'y_start': 100, 'y_end': 110, 'items': []},
    {'text': 'SJ078013', 'y_start': 115, 'y_end': 125, 'items': []},
    {'text': 'MF3NA81DE', 'y_start': 200, 'y_end': 210, 'items': []},
    {'text': 'SJ078015', 'y_start': 215, 'y_end': 225, 'items': []}
]

merged = []
i = 0
while i < len(candidates):
    current = candidates[i]
    if i + 1 < len(candidates):
        next_cand = candidates[i + 1]
        combined = current['text'] + next_cand['text']
        if len(combined) == 17 and combined.isalnum():
            merged.append({'text': combined})
            print(f"Merged: {current['text']} + {next_cand['text']} = {combined}")
            i += 2
            continue
    merged.append(current)
    i += 1

print(f"Total merged: {len(merged)}")
for m in merged:
    print(f"  - {m['text']}")
