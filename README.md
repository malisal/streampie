## Streampie

[![Documentation Status](https://readthedocs.org/projects/streampie/badge/?version=latest)](http://streampie.readthedocs.org/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/streampie.svg?style=flat)](https://pypi.python.org/pypi/streampie/)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat)](http://choosealicense.com/licenses/mit/)

Streampie is a tiny library for simple and parallel execution of job processing tasks. The project heavily draws both concepts and code from the awesome [stream.py](http://www.trinhhaianh.com/stream.py/) project by Anh Hai Trinh. However, it is a leaner, cleaner re-implementation with the addition of simple distributed computation.

### Installation

You can streampie with:

```bash
pip install streampie
```

### Example

Here is an example where streampie becomes useful. For more information, visit our [docs](https://streampie.readthedocs.org/en/latest)

```python
from streampie import *

ints = [2498834631017, 14536621517459, 6528633441793, 1941760544137, 7311548077279, 
        8567757849149, 5012823744127, 806981130983, 15687248010773, 7750678781801, 
        2703878052163, 3581512537619, 12656415588017, 468180585877, 19268446801283, 
        5719647740869, 11493581481859, 366611086739]

def factor(n):
   result = set()
   for i in range(1, int(n ** 0.5) + 1):
      div, mod = divmod(n, i)
      if mod == 0:
         result |= {i, div}
   return sorted(list(result))[:-1]

def do_work(wid, items):
   for i in items:
      yield factor(i)

print ints >> ProcessPool(do_work, poolsize=8) >> list
```

