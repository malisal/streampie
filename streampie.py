import sys
import zlib
import dill
import redis
import random
import inspect
import threading
import traceback
import itertools
import collections
import multiprocessing

try:
   # Python2
   import Queue as queue

   ifilter = itertools.ifilter
   imap = itertools.imap
except:
   # Python3
   import queue

   # In python3, filter and map by default return iterators
   ifilter = filter
   imap = map

def _ifilter_ext(predicate, iterable):
   for i, val in enumerate(iterable):
      if predicate and predicate(i, val):
         yield val

def _iterqueue(queue):
   """
      Take a queue and return an iterator over that queue.
   """
   while 1:
      item = queue.get()

      if item is StopIteration:
         queue.put(StopIteration)
         break

      yield item

class Stream():
   """
      This is our generic stream class. It is iterable and it overloads the ``>>`` operator
      for convenience.
   """
   def __init__(self, obj=None):
      self.iterator = None

      if isinstance(obj, collections.Iterable):
         self.iterator = iter(obj)

   def __iter__(self):
      return self

   # For python3
   def __next__(self):
      return self.next()

   def next(self):
      return next(self.iterator)

   def __rshift__(self, other):
      if inspect.isclass(other):
         return other(self)
      
      other.iterator = self
      other._on_connect()

      return Stream(other)

   def __rrshift__(self, other):
      return Stream(other) >> self

   def __repr__(self):
      return "Stream(%s)" % repr(self.iterator)

   def _on_connect(self):
      return NotImplemented

#
# Stream Processors
#

class take(Stream):
   def __init__(self, n):
      """
         Take the first ``n`` elements, and drop the rest.

         >>> range(4) >> take(2) >> list
         [0, 1]
      """
      Stream.__init__(self)
      self.n = n

   def __iter__(self):
      return itertools.islice(self.iterator, self.n)

class takei(Stream):
   def __init__(self, indices):
      """
         Take only the elements whose indices are given in the list.

         >>> range(4) >> takei([0, 1]) >> list
         [0, 1]
      """
      Stream.__init__(self)
      self.indices = indices

   def __iter__(self):
      def _filter(i, val):
         return i in self.indices

      return _ifilter_ext(_filter, self.iterator)

class drop(Stream):
   def __init__(self, n):
      """
         Drop the first `n` elements, and take the rest.
         
         >>> range(4) >> drop(2) >> list
         [2, 3]
      """
      Stream.__init__(self)
      self.n = n

   def __iter__(self):
      collections.deque(itertools.islice(self.iterator, self.n))
      return self.iterator

class dropi(Stream):
   def __init__(self, indices):
      """
         Drop only the elements whose indices are given in the ``indices`` list.

         >>> range(4) >> dropi([0, 1]) >> list
         [2, 3]
      """
      Stream.__init__(self)
      self.indices = indices

   def __iter__(self):
      def _filter(i, val):
         return not i in self.indices

      return _ifilter_ext(_filter, self.iterator)

class chop(Stream):
   def __init__(self, n):
      """
         Split the stream into ``n``-sized chunks.

         >>> range(4) >> chop(2) >> list
         [[0, 1], [2, 3]]
      """
      Stream.__init__(self)
      self.n = n

   def __iter__(self):
      def _chop():
         while 1:
            chunk = list(itertools.islice(self.iterator, self.n))

            if not chunk:
               break

            yield chunk

      return _chop()

class map(Stream):
   def __init__(self, function):
      """
         Call the function ``func`` for every element, with the element as input.

         >>> square = lambda x: x**2
         >>> range(4) >> map(square) >> list
         [0, 1, 4, 9]
      """
      Stream.__init__(self)
      self.function = function

   def __iter__(self):
      return imap(self.function, self.iterator)

class filter(Stream):
   def __init__(self, function):
      """
         Return only the elements for which the predicate ``func`` evaluates to ``True``.

         >>> even = lambda x: x % 2 == 0
         >>> range(4) >> filter(even) >> list
         [0, 2]
      """
      Stream.__init__(self)
      self.function = function

   def __iter__(self):
      return ifilter(self.function, self.iterator)

class apply(Stream):
   def __init__(self, function):
      """
         Call the function ``func`` for every element, with the element as arguments.

         >>> sum = lambda x,y: x+y
         >>> range(4) >> chop(2) >> apply(sum) >> list
         [1, 5]
      """
      Stream.__init__(self)
      self.function = function

   def __iter__(self):
      return itertools.starmap(self.function, self.iterator)

class takewhile(Stream):
   def __init__(self, predicate):
      """
         Keep taking elements until the predicate ``func`` is ``True``, then stop.

         >>> range(4) >> takewhile(lambda x: x < 3) >> list
         [0, 1, 2]
      """
      Stream.__init__(self)
      self.predicate = predicate

   def __iter__(self):
      return itertools.takewhile(self.predicate, self.iterator)

class dropwhile(Stream):
   def __init__(self, predicate):
      """
         Keep dropping elements until the predicate ``func`` is ``True``, then stop.

         >>> range(4) >> dropwhile(lambda x: x < 3) >> list
         [3]
      """
      Stream.__init__(self)
      self.predicate = predicate

   def __iter__(self):
      return itertools.dropwhile(self.predicate, self.iterator)

class prepend(Stream):
   def __init__(self, prep_iterator):
      """
         Prepend elements to a stream.

         >>> range(4) >> prepend([10, 9]) >> list
         [10, 9, 0, 1, 2, 3]
      """
      Stream.__init__(self)
      self.prep_iterator = prep_iterator

   def __iter__(self):
      return itertools.chain(self.prep_iterator, self.iterator)

class flatten(Stream):
   """
      Flatten an arbitrarily-deep list of lists into a single list.

      >>> [0,[1,[2,[3]]]] >> flatten() >> list
      [0, 1, 2, 3]
   """
   def __iter__(self):
      def _flatten(iterator):
         stack = []

         while 1:
            try:
               item = next(iterator)
   
               if isinstance(item, collections.Iterable):
                  stack.append(iter(item))
               else:
                  yield item

            except StopIteration:
               try:
                  iterator = stack.pop()
               except IndexError:
                  break

      return _flatten(self.iterator)

#
# Paralellism
#

class LocalPool(Stream):
   def __init__(self, function, poolsize=None, args=[]):
      """
         A generic class shared by all local (executed on the same machine) pools.
      """
      Stream.__init__(self)
      self.function = function
      self.poolsize = poolsize
      self.args = args
      self.pool = []

      if self.poolsize == None:
         # No prefered poolsize? Use number of cores 
         self.poolsize = multiprocessing.cpu_count()

   def _worker(self, wid):
      try:
         for val in self.function(wid, _iterqueue(self.in_queue), *self.args):
            self.out_queue.put(val)
      except:
         # Catch all exceptions and just print them, but keep working
         traceback.print_exc()

   def _control(self):
      # Move all data from the iterator to the input queue
      for val in self.iterator:
         self.in_queue.put(val)

      # Last item in the queue is the stop-signal
      self.in_queue.put(StopIteration)

      # Wait for all workers to finish
      for p in self.pool:
         p.join()
      
      # All workers finished, stop the output queue iterator
      self.out_queue.put(StopIteration)

   def stop(self):
      """
         Terminate and wait for all workers to finish.
      """
      # Wait for all workers to finish
      for p in self.pool:
         p.terminate()

   def __iter__(self):
      return _iterqueue(self.out_queue)

   def _on_connect(self):
      # Start the control thread
      t = threading.Thread(target=self._start_workers)
      t.daemon = True
      t.start()

class ProcessPool(LocalPool):
   def __init__(self, function, poolsize=None, args=[]):
      """
         Create a process pool.

         :param int function: Function that each worker executes
         :param int poolsize: How many workers the pool should make
         :param list args: List of arguments to pass to the worker function

         A simple that calls the ``sum`` function for every pair of inputs.

         >>> def sum(wid, items):
         ...   # wid is the worker id
         ...   # items is an iterator for the inputs to the stream
         ...   for x, y in items:
         ...      yield x + y
         >>> range(6) >> chop(2) >> ProcessPool(sum) >> list # doctest: +SKIP
         [1, 5, 9]

         Note that the order of the output list is not guaranteed, as it depends
         in which order the elements were consumed. By default, the class creates 
         as many workers as there are cores. Here is a more advanced examples 
         showing ``poolsize`` control and passing additional arguments.

         >>> def sum(wid, items, arg1, arg2):
         ...   # arg1 and arg2 are additional arguments passed to the function
         ...   for x, y in items:
         ...     yield x + y
         >>> sorted(range(6) >> chop(2) >> ProcessPool(sum, poolsize=8, args=[0, 1]) >> list)
         [1, 5, 9]

         The function can yield arbitrarily many results. For example, for a single input, two or more
         yields can be made.

         >>> def sum(wid, items):
         ...   for x, y in items:
         ...     yield x + y
         ...     yield x + y
         >>> sorted(range(6) >> chop(2) >> ProcessPool(sum) >> list)
         [1, 1, 5, 5, 9, 9]
         
      """
      LocalPool.__init__(self, function, poolsize, args)
      self.in_queue = multiprocessing.Queue()
      self.out_queue = multiprocessing.Queue()

   def _start_workers(self):
      # Start the worker processes
      for x in range(self.poolsize):
         p = multiprocessing.Process(target=self._worker, args=[x])
         p.daemon = True
         p.start()
         self.pool.append(p)

      self._control()

class ThreadPool(LocalPool):
   def __init__(self, function, poolsize=None, args=[]):
      """
         Create a thread pool.

         :param int function: Function that each worker executes
         :param int poolsize: How many workers the pool should make
         :param list args: List of arguments to pass to the worker function

         >>> def sum(wid, items):
         ...   # wid is the worker id
         ...   # items is an iterator for the inputs to the stream
         ...   for x, y in items:
         ...      yield x + y
         >>> range(6) >> chop(2) >> ThreadPool(sum) >> list # doctest: +SKIP
         [1, 5, 9]
      """
      LocalPool.__init__(self, function, poolsize, args)
      self.in_queue = queue.Queue()
      self.out_queue = queue.Queue()

   def _start_workers(self):
      # Start the worker threads
      for x in range(self.poolsize):
         t = threading.Thread(target=self._worker, args=[x])
         t.daemon = True
         t.start()
         self.pool.append(t)

      self._control()

class StandaloneProcessPool(ProcessPool):
   def __init__(self, function, poolsize=None, args=[]):
      """
         The standalone process pool is exactly like the :class:`ProcessPool` class, other than 
         the fact that it does not take any input, but constantly yields output. 

         :param int function: Function that each worker executes
         :param int poolsize: How many workers the pool should make
         :param list args: List of arguments to pass to the worker function

         To illustrate, here is an example of a worker that constantly returns random numbers.
         Since there is no input stream, the pool needs to be manually terminated.

         >>> import random
         >>> def do_work(wid):
         ...   yield random.random()
         >>> pool = StandaloneProcessPool(do_work)
         >>> for x, r in enumerate(pool): # doctest: +SKIP
         ...   if x == 2:
         ...      pool.stop()
         ...      break
         ...   print r
         0.600151963181
         0.144348185086
      """
      ProcessPool.__init__(self, function, poolsize, args)
      self.iterator = _iterqueue(self.out_queue)

      multiprocessing.Process(target=self._start_workers).start()

   def _worker(self, wid):
      try:
         for val in self.function(wid, *self.args):
            self.out_queue.put(val)
      except:
         # Catch all exceptions and just print them, but keep working
         traceback.print_exc()

   def _control(self):
      # Wait for all workers to finish
      for p in self.pool:
         p.join()

      # All workers finished, stop the output queue iterator
      self.out_queue.put(StopIteration)

#
# Distributed Paralellism
#

def _dumps(obj):
   """
      Serialize and compress an object.
   """
   return zlib.compress(dill.dumps(obj))

def _loads(data):
   """
      Decompress and deserialize.
   """
   return dill.loads(zlib.decompress(data))

class Job:
   def __init__(self, target_id, args=[]):
      """
         This class is our unit of work. It it fetched by a :class:`Worker`, it's ``target`` is executed, the 
         result (``ret``) and exception (if any) is stored and sent back to the JobQueue.

         :param int target_id: ID of the code to execute. See the source of :class:`JobQueue.enqueue` for details.
         :param list args: List of arguments to pass to the worker function
      """
      self.id = random.getrandbits(32)
      self.target_id = target_id
      self.args = args

      # The return and exception values are populated by the Worker later on
      self.ret = None
      self.exception = None

class Worker:
   def __init__(self, host="localhost", port=6379, db=10):
      """
         The workhorse of our implementation. Each worker fetches a job from Redis,
         executes it, then stores the results back into Redis.

         :param str host: Redis hostname
         :param int port: Redis port
         :param int db: Redis database number
      """
      self.db = redis.Redis(host=host, port=port, db=db)
      self.target_cache = {}

   def _fetch_job(self):
      return _loads(self.db.blpop("job_queue")[1])

   def _do_job(self, target, job):
      try:
         args = job.args

         if not isinstance(args, list) and not(isinstance(args, tuple)):
            # Make sure that args are always a list/tuple
            args = [args]

         job.ret = target(*args)
      except Exception as e:
         # An exception occured, print and log it
         traceback.print_exc()
         job.exception = e

      # Aadd the job to the response queue
      self.db.rpush("response_queue", _dumps(job))

   def run(self):
      """
         In an infinite loop, wait for jobs, then execute them and return the results to Redis.
      """
      while 1:
         # Blocks until a job is available
         job = self._fetch_job()
         
         if job.target_id in self.target_cache:
            # We have the target code cached, great!
            target = self.target_cache[job.target_id]
         else:
            # Fetch the code from redis and cache it
            target = _loads(self.db.get("target_%d" % (job.target_id)))
            self.target_cache[job.target_id] = target

         print("Got job: 0x%08x" % (job.id))

         # Execute the job in a separate process
         p = multiprocessing.Process(target=self._do_job, args=(target, job))
         p.daemon = True
         p.start()

         p.join()

class JobQueue(Stream):
   def __init__(self, host="localhost", port=6379, db=10):
      """
         .. warning:: The :class:`JobQueue` flushes the selected Redis database! Be sure to specify an unused database!

         The queue that allows submission and fetching of completed jobs.

         :param str host: Redis hostname
         :param int port: Redis port
         :param int db: Redis database number

         That being said, here is an example of how to use the queue.

         >>> def sum(x, y):
         ...   return x + y
         >>> q = JobQueue()
         >>> q.enqueue(sum, (1, 2)) # doctest: +SKIP
         >>> q.enqueue(sum, (2, 3)) # doctest: +SKIP
         >>> q.enqueue(sum, (3, 4)) # doctest: +SKIP
         >>> q.finalize()
         >>> for r in q:   # doctest: +SKIP
         ...   print r.ret
         3
         5
         7
      """
      Stream.__init__(self)
      self.db = redis.Redis(host=host, port=port, db=db)
      self.db.flushdb()
      
      self.cnt_queued = 0
      self.cnt_got = 0
      self.finalized = False

   def next(self):
      if self.finalized and self.cnt_got == self.cnt_queued:
         raise StopIteration
   
      job = _loads(self.db.blpop("response_queue")[1])
      self.cnt_got += 1

      return job

   def enqueue(self, target, args):
      """
         Add a job to the queue.

         :param function target: Function to be executed
         :param list args: Arguments provided to the job
      """
      if self.finalized:
         raise Exception("No more jobs allowed")

      # Check if we have to add the target's code to redis
      target_data = _dumps(target)
      target_id = hash(target_data)

      if not self.db.get("target_%d" % (target_id)):
         # This target does not exist, add it to the cache so that we don't have to download
         # the method code every time a job is submitted/fetched.
         self.db.set("target_%d" % (target_id), target_data)

      # Add the new job to the redis list
      self.db.rpush("job_queue", _dumps(Job(target_id, args)))
      self.cnt_queued += 1

   def finalize(self):
      """
         Indicate to the queue that no more jobs will be submitted.
      """
      self.finalized = True

class DistributedPool(Stream):
   def __init__(self, function, host="localhost", port=6379, db=10):
      """
         The distributed pool is a simple wrapper around the :class:`JobQueue` that makes is even more
         convenient to use, just like :class:`ProcessPool` and :class:`ThreadPool`.

         :param str host: Redis hostname
         :param int port: Redis port
         :param int db: Redis database number

         First, on one machine let's start a single worker.

         .. code-block:: bash

            python streampie.py

         We then execute:

         >>> def mul(x, y):
         ...   return x * y
         >>> range(4) >> chop(2) >> DistributedPool(mul) >> list # doctest: +SKIP
         [0, 6]
      """
      Stream.__init__(self)
      self.in_queue = queue.Queue()
      self.out_queue = queue.Queue()
      self.function = function

      self.jq = JobQueue(host=host, port=port, db=db)

   def _input_control(self):
      # Move all data from the iterator to the input queue
      for val in self.iterator:
         self.jq.enqueue(self.function, val)

      # Indicate to the queue that no more jobs will be added
      self.jq.finalize()

   def _output_control(self):
      # Move all data from the job queue to the output queue
      for job in self.jq:
         self.out_queue.put(job.ret)

      # All workers finished, stop the output queue iterator
      self.out_queue.put(StopIteration)

   def __iter__(self):
      return _iterqueue(self.out_queue)

   def _on_connect(self):
      # Start the input and output control threads
      self._input_thread = threading.Thread(target=self._input_control)
      self._input_thread.daemon = True
      self._input_thread .start()

      self._output_control()

   def stop(self):
      """
         Currently not implemented. Is it even needed?
      """
      return NotImplemented

if __name__ == "__main__":
   # Act as a simple worker process
   print("Starting worker...")
   
   w = Worker()
   w.run()
   w.stop()

