# tenc - tool to convert large multigraphs to adjacency tensors
# Copyright (C) 2012 Maximilian Nickel <nickel@dbs.ifi.lmu.de>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import re

ATTR_ID = 0
ATTR_ZEROONE = 1
ATTR_WORD = 2
ATTR_DATE = 3
ATTR_CURRENCY = 4
ATTR_AGGREGATION = 10

log = logging.getLogger('tenc.converter')

# Check if NLTK is present
try:
    import nltk
    from nltk.corpus import wordnet as wn
    _STOPWORDS = set(nltk.corpus.stopwords.words())
    _STOPWORDS = _STOPWORDS.union(['http', 'www'])
    USE_NLTK = True
except ImportError:
    log.warn('Could not import NLTK, switching to fallback')
    USE_NLTK = False


def has_word(prop, value):
    """
    Splits textual data into tokens. When NLTK is present,
    also removes stopword and performs stemming on tokens.

    Parameter
    ---------
    prop: String, property name
    value: String, textual data to be processed

    >>> has_word('hw', 'this is a complicated doctest') #doctest: +ELLIPSIS
    <generator object has_word at 0x...>

    >>> list(has_word('hw', 'this is a complicated doctest'))
    [(2, 'hw', 'COMPLIC'), (2, 'hw', 'DOCTEST')]
    """
    prop = str(unicode(prop, errors="replace"))
    value = str(unicode(value, errors="replace"))
    if USE_NLTK:
        tok = nltk.tokenize.WordPunctTokenizer()
        tokens = tok.tokenize(value)
        tokens = [t for t in tokens if t not in _STOPWORDS and re.match(r'\w+', t) is not None]
        stemmer = nltk.stem.porter.PorterStemmer()
        for t in tokens:
            yield (ATTR_WORD, prop, stemmer.stem(t).upper())
    else:
        # fall back to simple whitespace tokenization when nltk is missing
        for t in value.split():
            yield (ATTR_WORD, prop, t.upper())


def has_class_word(prop, value):
    """
    >>> has_class_word('hcw', 'this_is_a_complicated_doctest') #doctest: +ELLIPSIS
    <generator object has_class_word at 0x...>

    >>> list(has_class_word('hcw','this_is_a_complicated_doctest'))
    [(2, 'hcw', 'THIS'), (2, 'hcw', 'IS'), (2, 'hcw', 'A'), (2, 'hcw', 'COMPLICATED'), (2, 'hcw', 'DOCTEST')]
    """
    prop = str(prop)
    value = str(value)
    tokens = value.split('_')
    for t in tokens:
        yield (ATTR_WORD, prop, t.upper())


def has_id(prop, value):
    """
    >>> has_id('has_id', 2) #doctest: +ELLIPSIS
    <generator object has_id at 0x...>

    >>> list(has_id('id', 2))
    [(0, 'id', '2')]
    """
    yield (ATTR_ID, str(prop), str(value))


def synset(prop, value, pos=None):
    hyps = set()
    tok = nltk.tokenize.WordPunctTokenizer()
    tokens = tok.tokenize(value)
    for tok in tokens:
        syntree = [s.tree(lambda x: x.hypernyms()) for s in wn.synsets(tok)]
        for el in syntree:
            __flatten_synset(el, hyps)
    for s in hyps:
        yield (ATTR_WORD, prop, s.name)


def year_month(prop, value):
    value = str(value)
    value = value.split('-')
    #return [(u'YEAR ' + unicode(prop), value[0]), (u'YEAR-MONTH ' + unicode(prop), '-'.join([value[0], value[1]]))]
    return [(ATTR_DATE, u'YEAR ' + str(prop), value[0])]


def zeroone(prop, value):
    value = unicode(value).split('#')[0]
    return [(ATTR_ZEROONE, unicode(prop), float(value))]


def yago_currency(prop, value):
    value = unicode(value).split('#')[0]
    return [(ATTR_CURRENCY, unicode(prop), float(value))]


def yago_geocoordinates(prop, value):
    long, lat = unicode(value).split('/')
    return [(ATTR_ZEROONE, u'LONG ' + unicode(prop), long), (ATTR_ZEROONE, u'LAT ' + unicode(prop), lat)]


def __flatten_synset(s, result):
    result.add(s[0])
    for i in xrange(1, len(s)):
        __flatten_synset(s[i], result)
