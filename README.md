10&#162; - Tensor Conversion Tools for Large Multigraphs
=======================================================

tenc ("10 cent") are a collection of tools to efficiently convert large multigraphs in various formats (e.g. RDF) to a sparse tensor format. Conversion is done using only one pass over the original data.
The package provides an executable 10c to readily convert various existing file formats such as RDF, tab-delimited lists, ReVerb, etc. into Python or Matlab formats. Furthermore, library functions are provided to easily write custom conversion tools.

Installing
----------
Simply run

	python setup.py install

and you should be all set


Usage
-----
Run `10c -h` for a list of options


Available Converters
--------------------
The following converters are currently available in tenc:

* `tab` - converter for tab-delimited lists of triples i.e. in the form of
  
  		<entity>\t<predicate>\t<entity>\n

  a offset can be specified when the entity-relation-entity triples are not at the beginning of an tab-delimited line. This format is well suited for large-scale data, since only one line has to be processed at a time.

* `ntriples` - converter for the N-Triples format using the redland library. This format is well suited for large-scale data, since only one line has to be processed at a time.

(C) 2013 Maximilian Nickel <max@inmachina.com>
