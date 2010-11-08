#!/usr/bin/env python
#

import os, re, logging
import wsgiref.handlers
from urllib import quote
from itertools import repeat

from google.appengine.ext import webapp
from google.appengine.api import urlfetch, memcache

DEBUG = os.getenv('SERVER_SOFTWARE').split('/')[0] == "Development" if os.getenv('SERVER_SOFTWARE') else False

error_response = '-1'
empty_response = ','.join(repeat('0', 10))

# Google News Archive search - years 1900 to 2010
url = 'http://news.google.com/archivesearch?as_user_ldate=1900&as_user_hdate=2010&scoring=t&q="%s"'

# Pattern to match the Google chart extended encoding data 
pat = re.compile(r'#timelinemain[^#]*chd=e:(?P<points>[^&]+)&')

# Valid chars in Google chart extended encoding character set
chart_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-.'
char_len = len(chart_chars)

# Split a list into chunks
def chunk(data, size):
  data = list(data)
  m, n = divmod(len(data), size)
  for i in range(m+bool(n)):
    yield data[i*size:(i+1)*size]
      

# Decode Google chart extended encoding data
def decode(datapoints):
  # Each datapoint consists of a pair of characters
  for datapoint in chunk(datapoints, 2):
    yield (chart_chars.find(datapoint[0]) * char_len) + chart_chars.find(datapoint[1])


# Average the dataset chunks
def average_chunk(dataset, period):

  # Each datapoint consists of a pair of characters
  for period_data in chunk(dataset, period):
    logging.debug(period_data)

    # yield the average of the chunk
    yield sum(period_data)/period

  
  

class MainHandler(webapp.RequestHandler):
  def get(self):
    
    try:
      term = self.request.get('q')

      assert(term)
      
      # Attempt to pull response from the cache
      res = memcache.get(term)
      if res is None:
        
        # Call the Google News url
        logging.debug("calling %s" % (url % quote(term)))
        result = urlfetch.fetch(url % quote(term))
      
        assert(result.status_code == 200)
        
        # Look for the charts url in the response
        mat = pat.search(result.content)
        if not mat:
          res = empty_response
          
        else:
          points = mat.group('points')
          logging.debug("dataset %s" % points)
          
          assert(len(points) == 220)
          
          # Strip the unwanted data from the chart dataset (1900-1908 & 2010)
          points = points[18:]
          points = points[:-2]
              
          # Decode and average the chart data for a decade
          res = ','.join((str(x) for x in average_chunk(decode(points), 10)))

        # Cache the response for 24 hours
        memcache.set(term, res, 86400)

    except AssertionError, e:
      logging.error(e)
      res = error_response
    
    if not DEBUG:   
      self.response.headers["Content-Type"] = "text/plain"
    self.response.out.write(res)



def main():
  logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.WARN)
  
  application = webapp.WSGIApplication([('/', MainHandler)], debug=DEBUG)
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
