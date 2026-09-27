"""Compare supplied conversion/export files against a fictional, independent oracle.
This does not run Civil 3D or authenticate the origin of the supplied export.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation
import argparse, csv, hashlib, io, json, sys

ROOT=Path(__file__).resolve().parent
def digest(raw): return hashlib.sha256(raw).hexdigest()
def rows(raw):
    result={}
    for line, row in enumerate(csv.reader(io.StringIO(raw.decode('utf-8-sig')),strict=True),1):
        if len(row)!=5: raise ValueError(f'row {line}: expected five PENZD columns, no header or blank rows')
        identity=row[0].strip()
        if identity in result: raise ValueError(f'duplicate point number {identity}')
        xyz=[Decimal(x.strip()) for x in row[1:4]]
        if not all(x.is_finite() for x in xyz): raise ValueError(f'row {line}: non-finite coordinate')
        result[identity]=(xyz,row[4])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--converted',type=Path,required=True)
    parser.add_argument('--observed',type=Path,required=True,help='Civil 3D export, PENZD comma, no header')
    args=parser.parse_args()
    try:
        spec=json.loads((ROOT/'fixture-manifest.json').read_text(encoding='utf-8'))
        app=args.app.read_bytes(); converted=args.converted.read_bytes(); observed=args.observed.read_bytes()
        expected=(ROOT/'expected-meters.csv').read_bytes()
        failures=[]
        if digest(app)!=spec['app_sha256']: failures.append('app hash differs from the nominated PFU Python build')
        if digest(expected)!=spec['expected_sha256']: failures.append('expected fixture hash differs from its manifest')
        if converted!=expected: failures.append('converted file is not byte-identical to the independent expected output')
        want,got=rows(expected),rows(observed)
        if set(want)!=set(got): failures.append('point-number set differs: missing '+str(sorted(set(want)-set(got)))+'; extra '+str(sorted(set(got)-set(want))))
        tolerance=Decimal(spec['cad_export_tolerance_m']);max_error=Decimal(0)
        for identity in sorted(set(want)&set(got)):
            wanted,description=want[identity];actual,actual_description=got[identity]
            if description!=actual_description: failures.append(f'point {identity}: raw description changed')
            for axis,x,y in zip(['E','N','Z'],wanted,actual):
                error=abs(x-y);max_error=max(max_error,error)
                if error>tolerance: failures.append(f'point {identity} {axis}: error {error} m exceeds {tolerance} m')
        report={'schema':'pfu-cad-fixture-comparison/1','passed':not failures,
                'scope':'Comparison of supplied files only; native CAD execution and export origin require the operator record.',
                'app_sha256':digest(app),'converted_sha256':digest(converted),'observed_sha256':digest(observed),
                'observed_point_count':len(got),'max_coordinate_error_m':str(max_error),
                'tolerance_m':str(tolerance),'failures':failures}
        print(json.dumps(report,indent=2));return 0 if not failures else 1
    except (OSError,ValueError,InvalidOperation,csv.Error) as error:
        print(json.dumps({'passed':False,'error':str(error)}));return 2

if __name__=='__main__': sys.exit(main())
