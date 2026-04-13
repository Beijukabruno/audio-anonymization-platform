"""
Script to correct operator names in IOA database.
"""
from backend.ioa_database import SessionLocal
from backend.ioa_models import Operator, Annotation

SIMON_NAMES = [
    '',
    'NAMATIITI SIMON PETER',
    'NAMATIITTI SIMON PETER',
    'NAMATTITI SIMON PETER'
]
NEW_NAME = 'Simon'

def correct_operator_names():
    session = SessionLocal()
    # Get or create Simon operator
    simon_op = session.query(Operator).filter_by(name=NEW_NAME).first()
    if not simon_op:
        simon_op = Operator(name=NEW_NAME)
        session.add(simon_op)
        session.commit()
    # Update all annotations with old names to Simon
    for old_name in SIMON_NAMES:
        op = session.query(Operator).filter_by(name=old_name).first()
        if op:
            anns = session.query(Annotation).filter_by(operator_id=op.id).all()
            for ann in anns:
                ann.operator_id = simon_op.id
            session.commit()
            session.delete(op)
            session.commit()
    session.close()
    print(f"Corrected operator names to '{NEW_NAME}'")

if __name__ == '__main__':
    correct_operator_names()
