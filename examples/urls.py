import urllib2
from streampie import *

URLs = [
   "http://www.cnn.com/",
   "http://www.bbc.co.uk/",
   "http://www.economist.com/",
   "http://nonexistant.website.at.baddomain/",
   "http://slashdot.org/",
   "http://reddit.com/",
   "http://news.ycombinator.com/",
]

def retrieve(wid, items):
   for url in items:
      yield url, urllib2.urlopen(url).read()

for url, content in URLs >> ThreadPool(retrieve, poolsize=4):
   print url, len(content)

