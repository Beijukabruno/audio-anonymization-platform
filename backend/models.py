from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Annotation:
    start_sec: float
    end_sec: float
    gender: str  # 'male' | 'female'
    label: Optional[str] = None
    language: str = "luganda"  # 'luganda' | 'english'

    def duration_ms(self) -> int:
        return int(max(0.0, (self.end_sec - self.start_sec)) * 1000)


def normalize_annotations(annotations: List[Annotation]) -> List[Annotation]:
    """
    - Ensure start <= end
    - Remove zero/negative duration
    - Sort by start
    - Merge overlapping by keeping earliest start and latest end per contiguous block
    """
    cleaned = [a for a in annotations if a.end_sec > a.start_sec]
    cleaned.sort(key=lambda a: a.start_sec)
    merged: List[Annotation] = []
    for ann in cleaned:
        if not merged:
            merged.append(ann)
            continue
        last = merged[-1]
        if ann.start_sec <= last.end_sec:
            # overlap: merge
            merged[-1] = Annotation(
                start_sec=last.start_sec,
                end_sec=max(last.end_sec, ann.end_sec),
                gender=ann.gender or last.gender,
                label=(ann.label or last.label),
                language=ann.language or last.language,
            )
        else:
            merged.append(ann)
    return merged
