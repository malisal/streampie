Getting Started
===============

Installing
----------

You can install the library through ``pip``

.. code-block:: bash

   pip install streampie

or head over to the github repository `streampie <https://github.com/malisal/streampie/>`_. The whole library is contained in a single file.

Streams
-------

Streams (:class:`~streampie.Stream`) are the basic class of the library. Each stream can be thought of as a class that takes an element from the input iterator, performs some work on the element, and then passes it on to the next stream in line. When working with streams, we overload the ``>>`` operator as it intuitively captures the notion of "passing on" the results from one stream into another.

Let's first start by including the library

.. ipython:: python

   from streampie import *

To illustrate the concept of streams and processors, let's take the following example

.. ipython:: python
   
   [0, 1, 2, 3] >> take(2) >> list
 
In this example, we took our list and passed it to the :class:`~streampie.take` processor that took the first two elements of the list and discarded the rest. The final outcome was then converted to a plain list. Another common task in stream processing is splitting inputs into equally-sized chunks. For that purpose we can use :class:`~streampie.chop`.

.. ipython:: python
   
   range(4) >> chop(2) >> list

We are not limited to a single processor; we can chain arbitrarily many blocks

.. ipython:: python
   
   range(4) >> chop(2) >> take(2) >> list

For a full list of processors, see :class:`streampie`. To illustrate where Streampie is useful, let's consider two examples that naturally benefit from paralellism. 

URL Retrieval
-------------

Retrieving URLs is not a CPU-intensive task. To retrieve URLs in parallel (with four threads), we can utilize the :class:`~streampie.ThreadPool` to code the following program

.. literalinclude:: ../examples/urls.py

Integer Factorization
---------------------

The second example is integer factorization, which is CPU intensive. Running a :class:`~streampie.ThreadPool` would not result in large performance gains due to the python global lock. However, we can use :class:`~streampie.ProcessPool`. Let's first look at a simple, iterative solution.

.. literalinclude:: ../examples/factor_slow.py

The program just iterates over the list of composite integers (each integer is a product of two primes). We can re-code the example in the following way.

.. literalinclude:: ../examples/factor_pool.py

We now use 8 parallel local processes, and the task of factoring the numbers will be ~8 times as fast. But what if we want to compute the same task on a small cluster (e.g., two machines)? For that purpose, we can use the :class:`~streampie.DistributedPool`.

.. literalinclude:: ../examples/factor_distrib.py

This code will now wait for workers to perform the job. We can start a single-process worker with

.. code-block:: bash

   python streampie.py


