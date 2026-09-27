"""Compare files for these small fictional cases. This does not operate CAD or authenticate export provenance."""
import argparse, csv, hashlib, io, json, re, sys
from fractions import Fraction
from pathlib import Path

NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
def sha(raw): return hashlib.sha256(raw).hexdigest()

def parse(raw):
    if len(raw) > 1024*1024: raise ValueError('This small-fixture checker accepts at most 1 MiB')
    result = {}
    for line, row in enumerate(csv.reader(io.StringIO(raw.decode('utf-8-sig')), strict=True), 1):
        if len(row) != 5: raise ValueError(f'Line {line}: expected five columns, no header')
        identifier = row[0].strip()
        if not re.fullmatch(r'[1-9][0-9]*', identifier): raise ValueError(f'Line {line}: invalid point number')
        if identifier in result: raise ValueError(f'Line {line}: duplicate point number')
        coordinates = []
        for token in row[1:4]:
            token = token.strip()
            if len(token) > 128 or NUMBER.fullmatch(token) is None:
                raise ValueError(f'Line {line}: invalid finite decimal coordinate')
            exponent = re.search(r'[eE]([+-]?[0-9]+)', token)
            if exponent and abs(int(exponent[1])) > 1000: raise ValueError('Exponent exceeds fixture-checker limit')
            coordinates.append(Fraction(token))
        result[identifier] = (coordinates, row[4])
    return result

def compare(case_dir, observed):
    spec = json.loads((case_dir/'case.json').read_bytes())
    expected = (case_dir/spec['expected']).read_bytes()
    converted = (case_dir/spec['import_file']).read_bytes()
    source = (case_dir/spec['source']).read_bytes()
    failures = []
    if sha(source) != spec['source_sha256']: failures.append('Source changed from prepared case')
    if sha(expected) != spec['expected_sha256']: failures.append('Expected fixture changed')
    if sha(converted) != spec['import_sha256'] or converted != expected: failures.append('Prepared converter output changed')
    wanted, actual = parse(expected), parse(observed)
    if set(wanted) != set(actual): failures.append('Missing or extra point IDs')
    if len(wanted) != spec['expected_point_count']: failures.append('Expected point count disagrees with case record')
    tolerance = Fraction(spec['coordinate_tolerance'])
    if tolerance < 0: raise ValueError('Negative tolerance')
    max_error = Fraction(0)
    axes = ('E','N','Z') if spec['format'] == 'PENZD' else ('N','E','Z')
    for identifier in sorted(set(wanted)&set(actual)):
        want, description = wanted[identifier]; got, got_description = actual[identifier]
        if description != got_description: failures.append(f'Point {identifier}: raw description changed')
        for axis, x, y in zip(axes, want, got):
            error = abs(x-y); max_error = max(max_error, error)
            if error > tolerance: failures.append(f'Point {identifier} {axis}: difference {error} exceeds {tolerance} {spec["target_unit"]}')
    return {'schema':'pfu-next-native-file-comparison/1','passed':not failures,'case':spec['case'],
            'scope':'Supplied-file comparison only. Native execution and provenance require an operator record.',
            'observed_sha256':sha(observed),'expected_sha256':sha(expected),
            'observed_point_count':len(actual),'byte_identical':observed==expected,
            'max_coordinate_difference':str(max_error),'target_unit':spec['target_unit'],
            'tolerance':str(tolerance),'failures':failures}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--observed', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compare(args.case, args.observed.read_bytes())
        print(json.dumps(result, indent=2))
        return 0 if result['passed'] else 1
    except (OSError, ValueError, csv.Error, KeyError) as exc:
        print(json.dumps({'passed':False,'error':str(exc)}))
        return 2
if __name__ == '__main__': sys.exit(main())
