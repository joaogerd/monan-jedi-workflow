"""Installation fixture only: produces tiny artificial products, not forecasts."""
from pathlib import Path
import sys

operation = sys.argv[1]
if operation == 'analysis':
    Path('analysis.nc').write_bytes(b'ARTIFICIAL ANALYSIS: installation test only')
    print('iteration 0 J = 100\niteration 1 J = 65\nOOPS Ending')
elif operation in {'forecast', 'init'}:
    Path('state.nc').write_bytes(b'ARTIFICIAL STATE: installation test only')
    print('MPAS complete')
elif operation == 'convert':
    Path('obs.h5').write_bytes(b'ARTIFICIAL IODA: installation test only')
    print('converted')
elif operation == 'inspect':
    print('ARTIFICIAL IODA')
else:
    raise SystemExit('unknown fixture operation')
