"""
Script to analyze inter-operator agreement from IOA database
"""
from backend.ioa_database import SessionLocal
from backend.ioa_models import Operator, Entity, Annotation

def get_annotations_for_audio(audio_file):
    session = SessionLocal()
    entities = session.query(Entity).filter_by(audio_file=audio_file).all()
    results = []
    for entity in entities:
        annots = session.query(Annotation).filter_by(entity_id=entity.id).all()
        for annot in annots:
            operator = session.query(Operator).get(annot.operator_id)
            results.append({
                'operator': operator.name,
                'audio_file': entity.audio_file,
                'start_time': annot.start_time,
                'stop_time': annot.stop_time,
                'label': annot.label,
                'comments': annot.comments
            })
    session.close()
    return results

# Example usage:
# audio_file = 'example.wav'
# annotations = get_annotations_for_audio(audio_file)
# print(annotations)
