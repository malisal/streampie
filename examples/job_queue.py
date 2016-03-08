from streampie import *

def sum(x, y):
   return x + y
   
q = JobQueue()
q.enqueue(sum, (1, 2))
q.enqueue(sum, (2, 3))
q.enqueue(sum, (3, 4))
q.finalize()

for r in q:
   print r.ret

