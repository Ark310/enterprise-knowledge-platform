import sys,os,json,subprocess,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w
class WireProtocolTests(unittest.TestCase):
 def test_original_locale_failure_reproduced(self):
  with self.assertRaises(UnicodeEncodeError):json.dumps({'text':'□ ₹ العربية 中文'},ensure_ascii=False).encode('cp1252')
 def test_transport_roundtrips_all_symbols_through_legacy_locale(self):
  payload={'ok':True,'result':{'text':'□ ₹ العربية 中文 café 😀'}}
  wire=w.wire_result(payload);self.assertEqual(json.loads(wire.encode('cp1252').decode('cp1252')),payload)
 def test_large_packet_roundtrip(self):
  payload={'result':[{'text':'□ ₹ العربية 中文 '*200,'id':i} for i in range(500)]}
  self.assertEqual(json.loads(w.wire_result(payload).encode('ascii')),payload)
 def test_stdio_overrides_legacy_locale_for_progress(self):
  code="import sys;sys.path.insert(0,sys.argv[1]);import worker;worker.configure_stdio();worker.progress('□ ₹ العربية 中文');print(worker.wire_result({'ok':True,'result':'□ ₹ العربية 中文'}))"
  env=dict(os.environ,PYTHONIOENCODING='cp1252',PYTHONUTF8='0')
  result=subprocess.run([sys.executable,'-c',code,str(Path(w.__file__).parent)],capture_output=True,env=env,check=True)
  self.assertEqual(json.loads(result.stdout)['result'],'□ ₹ العربية 中文');self.assertIn('□ ₹ العربية 中文',result.stderr.decode('utf-8'))
if __name__=='__main__':unittest.main()
