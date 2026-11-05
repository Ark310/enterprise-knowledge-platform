"""Offline host-test boundary: exercise real Python gates without PostgreSQL or model calls."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import knowledge_qa as qa
args=json.load(sys.stdin);part=args['part'];obj=args['object']
errors=qa.validate_normalization(args['original'],obj) if part=='normalization' else qa.validate_answer(obj,args['evidence']) if part=='answer' else qa.validate_verdict(obj,args['answer'],args.get('retrieval'))
print(json.dumps({'valid':not errors,'errors':errors,'needs_investigation':part=='verdict' and qa.may_investigate(obj,args.get('retrieval'))}))
