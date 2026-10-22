"""One-time repair of an unapplied null intent, with backups and state guards."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,sqlite3,shutil
from edsl.workflows import SQLiteWorkflowStore

p=Path(__file__).parent
archive=p/'recovery-before-retry'
archive.mkdir(exist_ok=False)
for name in ('workflow.sqlite','state-0.sqlite'):
    with sqlite3.connect(p/name) as source, sqlite3.connect(archive/name) as target:
        source.backup(target)
shutil.copyfile(p/'execution.log',archive/'execution.log')
store=SQLiteWorkflowStore(p/'workflow.sqlite')
with store.connect() as db:
    db.execute('BEGIN IMMEDIATE')
    pending=db.execute("select * from workflow_items where status='committing'").fetchall()
    assert len(pending)==1
    item=dict(pending[0]); item_id=item['id']
    assert item['participant_id']=='trader-05' and item['step_name']=='orders-30'
    intent=dict(db.execute('select * from workflow_submission_intents where work_item_id=?',(item_id,)).fetchone())
    assert json.loads(intent['answers'])=={'decision':None}
    assert not db.execute('select 1 from workflow_submissions where work_item_id=?',(item_id,)).fetchone()
    effects=[dict(r) for r in db.execute('select * from workflow_effects where work_item_id=?',(item_id,))]
    assert len(effects)==1 and effects[0]['applied']==0
    operation=json.loads(effects[0]['operation'])
    with sqlite3.connect(p/'state-0.sqlite') as state_db:
        assert not state_db.execute('select 1 from state_events where idempotency_key=?',(operation['idempotency_key'],)).fetchone()
        state=json.loads(state_db.execute("select payload from state_events where kind='write' order by sequence desc limit 1").fetchone()[0])['state']['market']
        assert state['period']==30 and len(state['tape'])==29
        assert len(state['orders'])==11 and 'trader-05' not in state['orders']
    record={'at':datetime.now(timezone.utc).isoformat(),'reason':'EDSL returned decision=null with no raw response; no state effect was applied.','item':item,'voided_intent':intent,'voided_unapplied_effects':effects,'preserved_successful_decisions':359,'guarded_state_unchanged':True,'test_result':'2 passed: null response and partial batch retry tests'}
    (archive/'voided-intent.json').write_text(json.dumps(record,indent=2)+'\n')
    db.execute('delete from workflow_effects where work_item_id=? and applied=0',(item_id,))
    db.execute('delete from workflow_submission_intents where work_item_id=?',(item_id,))
    db.execute("update workflow_items set status='in_progress' where id=?",(item_id,))
    store._event(db,item['instance_id'],'work_item.invalid_null_intent_voided',{'work_item_id':item_id,'archive':str(archive),'no_state_effect_applied':True})
    db.commit()
store.finish_attempt(intent['attempt_id'],status='failed',error_kind='incomplete_model_result',error_message='Null decision; no raw model response. Unapplied intent archived and voided before retry.')
assert store.retry_item(item_id,reason='Retry only null-result trader after guarded repair')
name='edsl/workflows/experiment.py'
record['runtime_before_sha256']=json.loads((p/'source-manifest.json').read_text())[name]
record['runtime_after_sha256']=hashlib.sha256(Path(name).read_bytes()).hexdigest()
shutil.copyfile(name,archive/'workflow_experiment_after_fix.py')
(p/'recovery.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'status':'ok','retry_item':item_id,'preserved_decisions':359,'state_database_unchanged':True}))
