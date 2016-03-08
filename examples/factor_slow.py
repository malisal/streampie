# A set of integers, each a product of two primes
ints = [2498834631017, 14536621517459, 6528633441793, 1941760544137, 7311548077279, 
        8567757849149, 5012823744127, 806981130983, 15687248010773, 7750678781801, 
        2703878052163, 3581512537619, 12656415588017, 468180585877, 19268446801283, 
        5719647740869, 11493581481859, 366611086739]

def factor(n):
   """
      Integer factorization.
   """
   result = set()
   for i in range(1, int(n ** 0.5) + 1):
      div, mod = divmod(n, i)
      if mod == 0:
         result |= {i, div}
   return sorted(list(result))[:-1]

print map(factor, ints)

