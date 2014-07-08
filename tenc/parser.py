# tenc - tool to convert large multigraphs to adjacency tensors
# Copyright (C) 2012 Maximilian Nickel <mnick@mit.edu>

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
from collections import defaultdict
from itertools import count
import tempfile

from tenc import MAP, TZArchive, register_parser, converter
from tenc._tenc import fjoin, write_tensor_size, write_tensor_index

log = logging.getLogger('tenc.converter')


def flush_attr_dict(attr_fout, attr_dict):
    for k, v in attr_dict.iteritems():
        attr_fout.write('%d %d %d\n' % (k[0], k[1], v))


class Converter(TZArchive):

    fout_subs = None
    fout_eattr = None
    fout_rattr = None

    def __init__(self, fname='tensor', attr_map={}):
        super(Converter, self).__init__(fname, 'w:bz2')
        self.attr_map = attr_map
        self.eattr_dict = defaultdict(int)
        self.rattr_dict = defaultdict(int)

        # setup id -> idx maps
        # for semantics of array entries see MAP_ORDER
        self.idx = [count() for _ in range(MAP.length)]
        self.maps = [defaultdict(self.idx[i].next) for i in range(MAP.length)]

        # setup predicate fact counter
        self.nnz = {
            MAP.ENTITY: defaultdict(int),
            MAP.PREDICATE: defaultdict(int),
            MAP.EATTR: 0,
            MAP.RATTR: 0
        }

    def convert(self, input_files):
        # Setup temporary files
        self.fout_subs = tempfile.NamedTemporaryFile(mode='wb', prefix='tenc-')
        self.fout_eattr = tempfile.NamedTemporaryFile(mode='wb', prefix='tenc-')
        self.fout_rattr = tempfile.NamedTemporaryFile(mode='wb', prefix='tenc-')
        self.fsz = tempfile.NamedTemporaryFile(mode='wb', prefix='tenc-', delete=False)

        # parse input_files
        for fin in input_files:
            self.parse(fin)
        self.flush_attributes()

        # Write tensor size
        write_tensor_size(self.fsz, self.maps[MAP.ENTITY], self.maps[MAP.PREDICATE], self.nnz)
        self.add(self.fsz, fjoin(self.SUBS_FOUT, self.SHAPE_SUFFIX))

        # add files to archive
        self.add(self.fout_subs, fjoin(self.SUBS_FOUT, self.SUBS_SUFFIX))
        self.add(self.fout_eattr, fjoin(self.ENTITIES_FOUT, self.ATTR_SUFFIX))
        self.add(self.fout_rattr, fjoin(self.PREDICATES_FOUT, self.ATTR_SUFFIX))

        # Write index maps
        for _fname, order in [
            (self.ENTITIES_FOUT, MAP.ENTITY),
            (self.PREDICATES_FOUT, MAP.PREDICATE),
            (self.ENTITIES_FOUT + "_attr", MAP.EATTR),
            (self.PREDICATES_FOUT + "_attr", MAP.RATTR)
        ]:
            tmp = tempfile.NamedTemporaryFile(mode='wb', prefix='tenc-', delete=False)
            write_tensor_index(tmp, self.maps[order])
            self.add(tmp, fjoin(_fname, self.MAP_SUFFIX))

        self.compress()


    def parse(self, fin):
        raise NotImplementedError()

    def process_global_entity_attributes(self, sname, pname, oname):
        if 'global-entities' in self.attr_map:
            sidx = self.maps[MAP.ENTITY][sname]
            oidx = self.maps[MAP.ENTITY][oname]
            for funname in self.attr_map['global-entities']:
                fun = getattr(converter, funname)
                for attr_type, attr_id, val in fun(funname + '_entity', sname):
                    self.eattr_dict[(sidx, self.maps[MAP.EATTR][intern(val)])] += 1
                for attr_type, attr_id, val in fun(funname + '_entity', oname):
                    self.eattr_dict[(oidx, self.maps[MAP.EATTR][intern(val)])] += 1

    def process_global_relation_attributes(self, sname, pname, oname):
        if 'global-relations' in self.attr_map:
            pidx = self.maps[MAP.PREDICATE][pname]
            for funname in self.attr_map['global-relations']:
                fun = getattr(converter, funname)
                for attr_type, attr_id, val in fun(funname + '_predicate', pname):
                    self.rattr_dict[(pidx, self.maps[MAP.RATTR][intern(val)])] += 1

    def write(self, sname, pname, oname, val):
        # process global attributes
        self.process_global_entity_attributes(sname, pname, oname)
        self.process_global_relation_attributes(sname, pname, oname)

        sidx = self.maps[MAP.ENTITY][sname]
        # process specific entity attributes
        if pname in self.attr_map:
            sidx = self.maps[MAP.ENTITY][sname]
            fun = getattr(converter, self.attr_map[pname])
            for aid in fun(pname, oname):
                aid = ','.join(map(str, aid))
                self.eattr_dict[(sidx, self.maps[MAP.EATTR][intern(aid)])] += 1
        # process relations
        else:
            oidx = self.maps[MAP.ENTITY][oname]
            pidx = self.maps[MAP.PREDICATE][pname]

            self.fout_subs.write(self.SUBS_TEMPLATE % (sidx, oidx, pidx, val))

            # count predicte and entity occurrences
            self.nnz[MAP.PREDICATE][pidx] += 1
            self.nnz[MAP.ENTITY][sidx] += 1
            self.nnz[MAP.ENTITY][oidx] += 1

    def flush_attributes(self):
        # process attributes
        flush_attr_dict(self.fout_eattr, self.eattr_dict)
        flush_attr_dict(self.fout_rattr, self.rattr_dict)
        self.nnz[MAP.EATTR] = len(self.eattr_dict)
        self.nnz[MAP.RATTR] = len(self.rattr_dict)


class Redland(Converter):

    parser = None

    def parse(self, fin):
        log.debug('Reading RDF from %s' % fin)
        import RDF
        parser = RDF.Parser(name=self.parser)
        stream = parser.parse_as_stream(fin)
        for triple in stream:
            self.write(triple.subject, triple.predicate, triple.object, 1)
            #sidx = self.maps[MAP.ENTITY][triple.subject]
            #pidx = self.maps[MAP.PREDICATE][triple.predicate]
            # handle entities
            #if triple.object.is_resource() or triple.object.is_blank():
            #    oidx = self.maps[MAP.ENTITY][triple.object]
            #    self.fout_subs.write(self.TEMPLATE % (sidx, oidx, pidx))
            #    self.nnz[pidx] += 1
            # handle attributes
            #elif triple.object.is_literal():
            #    raise NotImplementedError('Attribute processing is not implemented yet')
            #else:
            #    raise RuntimeError('Unknown object format (%s)' % triple.object)


class TabDelimited(Converter):

    offset = 0
    val_idx = None

    def parse(self, fin):
        log.debug('Reading tab-delimited data from %s (offset %d, value index %s)' % (fin, self.offset, self.val_idx))
        from nltk.corpus import wordnet as wn

        f = open(fin, 'r')
        for line in f:
            data = line.strip().split('\t')

            # tensor
            sname = data[0 + self.offset]
            oname = data[2 + self.offset]
            pname = data[1 + self.offset]
            val = 1 if self.val_idx is None else float(data[self.val_idx])
            self.write(sname, pname, oname, val)

            # has_word attributes
            #for attr_type, attr_id, val in has_word('noun', data[0 + offset]):
            #    eattr_dict[(sidx, maps[MAP.EATTR][intern(val)])] += 1
            #for attr_type, attr_id, val in has_word('noun', data[2 + offset]):
            #    eattr_dict[(oidx, maps[MAP.EATTR][intern(val)])] += 1
            #for attr_type, attr_id, val in has_word('pattern', data[1 + offset]):
            #    rattr_dict[(pidx, maps[MAP.RATTR][intern(val)])] += 1

            # synset attributes
            #for attr_type, attr_id, val in synset('synset_noun', data[0 + self.offset], pos=wn.NOUN):
            #    eattr_dict[(sidx, self.maps[MAP.EATTR][intern(val)])] += 1
            #for attr_type, attr_id, val in synset('synset_noun', data[2 + self.offset], pos=wn.NOUN):
            #    eattr_dict[(oidx, self.maps[MAP.EATTR][intern(val)])] += 1
        f.close()


@register_parser('mln', 'Markov Logic Network data')
class MarkovLogicNetworks(Converter):

    import re
    pattern = re.compile('(!)?(\w+)\((\w+),\s*(\w+)\)')

    def parse(self, fin):
        log.debug('Reading Markov Logic Network data from %s' % fin)

        f = open(fin, 'r')
        for line in f:
            line = line.strip()
            if line in ['', '\n']:
                continue
            m = self.pattern.match(line)
            pname = m.group(2).strip()
            sname = m.group(3).strip()
            oname = m.group(4).strip()
            val = 1 if m.group(1) is None else -1
            self.write(sname, pname, oname, val)
        f.close()


@register_parser('tab-delimited', '')
class TabPublic(TabDelimited):
    pass

@register_parser('ntriples', '')
class NTriples(Redland):
    """
    Parser for N-Triples format, based on redland parser
    """
    parser = 'ntriples'


@register_parser('rdfxml', '')
class RDFXML(Redland):
    """
    Parser for RDF/XML format, based on redland parser
    """
    parser = 'rdfxml'


@register_parser('turtle', '')
class Turtle(Redland):
    """
    Parser for Turtle format, based on redland parser
    """
    parser = 'turtle'


@register_parser('reverb', '')
class ReVerb(TabDelimited):
    """
    Parser for ReVerb format, based on tab parser
    For ReVerb see: http://reverb.cs.washington.edu
    """
    offset = 4
    val_idx = 8


@register_parser('ypss-surface', '')
class YPSSSurface(TabDelimited):
    """
    Parser for semi-synthethic Patty data, based on tab parser
    """
    val_idx = 6

@register_parser('ypss-facts', '')
class YPSSFacts(TabDelimited):
    """
    Parser for semi-synthethic Patty data, based on tab parser
    """
    val_idx = 6
    offset = 3
