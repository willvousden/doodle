Doodle API
==========

Quickstart
----------

To run:

    $ pipenv install
    $ pipenv run ./app.py

To run an example:

    $ ./test.sh

Examples
--------

Four operations are supported:

1. Adding a new candidate/interviewer (``POST``):
    
    $ curl -X POST -F name=Carl http://localhost:5000/candidate/
    {"id":1,"name":"Carl","times":[]}
    $ curl -X POST -F name=Philipp http://localhost:5000/interviewer/
    {"id":2,"name":"Philipp","times":[]}

2. Setting the available times for a person in ISO-8601 format (``PUT``):
    
    $ curl -X PUT -F time=2018-10-15T09 -F time=2018-10-15T10 http://localhost:5000/candidate/1
    {"id":1,"name":"Carl","times":["2018-10-15 09:00:00","2018-10-15 10:00:00"]}
    $ curl -X PUT -F time=2018-10-15T10 -F time=2018-10-15T11 http://localhost:5000/interviewer/2
    {"id":2,"name":"Philipp","times":["2018-10-15 10:00:00","2018-10-15 11:00:00"]}

3. Retrieving the available times for a person (``GET``)?
    
    $ curl http://localhost:5000/candidate/1
    {"id":1,"name":"Carl","times":["2018-10-15 09:00:00","2018-10-15 10:00:00"]}

4. Finding the overlap between several people's availabilities:
    
    $ curl 'http://localhost:5000/interview?id=1&id=2
    {"ids":[1,2],"times":["2018-10-18 09:00:00"]}


Notes/wish list
---------------

1. Currently, a PUT request adds and/or overwrites times.  Perhaps it should replace all existing
   times for a person?
2. Database connection management should be tied to the request lifetime.
3. More operations should be supported (e.g., ``DELETE`` for unsetting availability).
4. More convenient API? E.g., set a range of times.
5. Tests!  Use pytest to implement the contents of ``test.sh`` more rigorously.
