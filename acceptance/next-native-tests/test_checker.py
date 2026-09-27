"""Synthetic controls for check-export.py; no CAD launch or native execution."""
from pathlib import Path
import csv, importlib.util, io, json, subprocess, sys, tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('checker', HERE/'check-export.py')
checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)

def encode(rows): return ('\r\n'.join(','.join(row) for row in rows)+'\r\n').encode()

def main():
    results = []
    for case in sorted(x for x in HERE.iterdir() if (x/'case.json').is_file()):
        raw = (case/'expected.txt').read_bytes()
        rows = list(csv.reader(io.StringIO(raw.decode())))
        controls = {'synthetic-positive': (raw, True, 0),
                    'row-order-does-not-change-identity': (encode(list(reversed(rows))), True, 0),
                    'dropped-id': (encode(rows[:1]), False, 1),
                    'duplicate-id': (encode([rows[0],rows[0]]), False, 2)}
        for label,index,value,code in [('altered-description',4,'CHANGED',1), ('altered-coordinate',3,'9999.00000000',1),
                ('invalid-finite-number',1,'NaN',2), ('fraction-token-refused',1,'1200/1',2)]:
            changed = [row[:] for row in rows]; changed[0][index] = value
            controls[label] = (encode(changed), False, code)
        changed = [row[:] for row in rows]
        changed[0][1], changed[0][2] = changed[0][2], changed[0][1]
        controls['swapped-axes'] = (encode(changed),False,1)
        with tempfile.TemporaryDirectory(prefix='synthetic export ') as work:
            observed = Path(work)/'synthetic-observation.txt'
            for name,(data,want,expected_exit) in controls.items():
                error = None
                try: got = checker.compare(case,data)['passed']
                except ValueError as exc: got = False; error = str(exc)
                observed.write_bytes(data)
                process = subprocess.run([sys.executable,str(HERE/'check-export.py'),'--case',str(case),'--observed',str(observed)],
                                         capture_output=True,encoding='utf-8')
                results.append({'case':case.name,'control':name,'expected_pass':want,'actual_pass':got,
                                'expected_exit':expected_exit,'actual_exit':process.returncode,
                                'control_succeeded':want==got and expected_exit==process.returncode,'parse_error':error})
    record = {'scope':'Synthetic file controls only; native NOT RUN','controls':results}
    print(json.dumps(record,indent=2))
    return 0 if len(results)==27 and all(item['control_succeeded'] for item in results) else 1

if __name__=='__main__':sys.exit(main())
