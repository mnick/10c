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
import tarfile
import os
import json
import numpy as np

try:
    from collections import Counter
except ImportError:
    # python 2.6 compat
    class Counter(object):
        def __init__(self, lst):
            self.c = defaultdict(int)
            for e in lst:
                self.c[e] += 1
            self.c = dict(self.c)

        def iteritems(self):
            return self.c.iteritems()

# setup logging
log = logging.getLogger('tenc')


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    enums['length'] = len(enums)
    return type('Enum', (), enums)

MAP_ORDER = enum(
    'ENTITY',
    'PREDICATE',
    'EATTR',
    'RATTR'
)


def serialize(fname, min_count, serfun):
    tzf = TZArchive(fname)
    tzf.serialize(min_count, serfun)


class TZArchive(object):

    # Default values for file paths
    # Basename for subscripts
    SUBS_FOUT = 'tensor'
    # Basename for entities index
    ENTITIES_FOUT = 'entities'
    # Basename for predicates index
    PREDICATES_FOUT = 'predicates'
    # Suffix for subscripts
    SUBS_SUFFIX = 'ten'
    # Suffix for attribute subscripts
    ATTR_SUFFIX = 'attr'
    # Suffix for size file
    SHAPE_SUFFIX = 'size'
    # Suffix for entities / predicates index
    MAP_SUFFIX = 'idx'
    # Suffix for archive
    ARC_SUFFIX = 'tz'

    # MATLAB format is whitespace delimited numbers
    # for possible compatibility, we'll stick with that
    SUBS_TEMPLATE = '%d %d %d %f\n'

    def __init__(self, fname, mode):
        log.debug('Opening archive %s in mode %s' % (fname, mode))
        self.fname = fname
        self.files = dict()
        self.arc = tarfile.open(fjoin(fname, self.ARC_SUFFIX), mode)

    def __del__(self):
        if self.arc is not None:
            self.arc.close()

    def add(self, f, arcname):
        """add file to archive"""
        self.files[os.path.abspath(f.name)] = arcname
        f.flush()

    def compress(self):
        from io import StringIO
        metainfo = unicode(json.dumps({
            'fname': self.fname,
        }))

        for f, aname in self.files.iteritems():
            log.debug('Adding %s -> %s to archive' % (f, aname))
            self.arc.add(f, arcname=aname)
        self.arc.close()
        self.arc = None

    def __get_index(self, mode, prune_idx=None):
        f = fjoin(mode, self.MAP_SUFFIX)
        idx = read_tensor_index(self.arc.extractfile(f))
        if prune_idx:
            nidx = [None for _ in xrange(len(prune_idx))]
            for orig_idx, new_idx in prune_idx.iteritems():
                nidx[new_idx] = idx[orig_idx]
            idx = nidx
        return idx

    def entity_index(self, prune_idx=None):
        return self.__get_index(self.ENTITIES_FOUT, prune_idx)

    def predicate_index(self, prune_idx=None):
        return self.__get_index(self.PREDICATES_FOUT, prune_idx)

    def entity_attributes_index(self):
        return self.__get_index(self.ENTITIES_FOUT + '_attr')

    def predicate_attributes_index(self):
        return self.__get_index(self.PREDICATES_FOUT + '_attr')


def fjoin(fname, suffix, prefix=None):
    """
    Helper function, creates file name for basename, suffix and prefix
    """
    template = '%s.%s'
    if prefix is not None:
        template = '%s-%s' % (prefix, template)
    return template % (fname, suffix)


def write_tensor_size(fout, entity_map, predicate_map, nnz):
    """
    Write size of the tensor to file

    File Format
    -----------
    line 1: Number entities
    line 2: Number predicates
    line 3: For all entities: number of occurrences
    line 4: For all predicates: number of occurrences
    line 5: Number of entity attributes
    line 6: Number of predicate attributes
    """
    log.debug('Writing tensor size to %s' % fout.name)
    N = len(entity_map)
    K = len(predicate_map)
    sizes = [N, K] + \
        [nnz[MAP_ORDER.ENTITY][i] for i in xrange(N)] + \
        [nnz[MAP_ORDER.PREDICATE][i] for i in xrange(K)] + \
        [nnz[MAP_ORDER.EATTR], nnz[MAP_ORDER.RATTR]]
    for c in sizes:
        fout.write('%d\n' % c)


def write_tensor_index(fout, index, sort=True):
    """
    Write mapping of id -> tensor index to file

    Parameter
    ---------
      fout: file-like object
      index: dict with key = id and value = tensor index entries

    File Format
    -----------
    length: %(number of entries)
    %(name for entry with idx 0)
    %(name for entry with idx 1)
    ...
    %(name for entry with idx n)

    """
    log.debug('Writing index map to %s' % fout.name)
    # since we have interned strings, creating a new array "is not a
    # problem"(tm)
    if sort:
        sorted_names = [name for name, _ in sorted(index.iteritems(), key=lambda (k, v): v)]
    else:
        # we already have a sorted array
        sorted_names = index
    fout.write("length: %d\n" % len(sorted_names))
    for name in sorted_names:
        fout.write('%s\n' % name)


def read_tensor_index(fin):
    sz = fin.readline().strip().split('length: ')[1]
    idx = [None] * int(sz)
    i = 0
    for line in fin.readlines():
        idx[i] = line.strip()
        i += 1
    return idx


def read_tensor_size(fin):
    """
    Read size of tensor, for format see write_tensor_index
    """
    log.debug('Reading tensor size')
    N = int(fin.readline().strip())
    K = int(fin.readline().strip())
    nnz = [np.zeros(N, dtype=np.int), np.zeros(K, dtype=np.int), 0, 0]
    # read attribute nnz
    for n in xrange(N):
        nnz[MAP_ORDER.ENTITY][n] = int(fin.readline().strip())
    # read predicate nnz
    for k in xrange(K):
        nnz[MAP_ORDER.PREDICATE][k] = int(fin.readline().strip())
    # read number eattr
    nnz[MAP_ORDER.EATTR] = int(fin.readline().strip())
    # read number rattr
    nnz[MAP_ORDER.RATTR] = int(fin.readline().strip())
    log.debug('  tensor has size N: %d, K: %d, nnz: %d, eattr %d, rattr %d' % (
        N, K,
        nnz[MAP_ORDER.PREDICATE].sum(),
        nnz[MAP_ORDER.EATTR],
        nnz[MAP_ORDER.RATTR]
    ))
    return N, K, nnz


def prune(min_count, nnz, SZ, name='object'):
    log.debug('Pruning %s', name)
    pidx = dict()
    counter = 0
    for k in xrange(SZ):
        if nnz[k] > min_count:
            pidx[k] = counter
            counter += 1
        #else:
        #    log.debug('  pruned %s %d (nnz: %d)' % (name, k, nnz[k]))
    log.debug('Pruned %s %d -> %d (min count: %d)' % (name, SZ, len(pidx), min_count))
    return pidx


# code from
# http://stackoverflow.com/questions/845058/how-to-get-line-count-cheaply-in-python
def linecount(filename):
    f = open(filename)
    lines = 0
    buf_size = 1024 * 1024
    read_f = f.read  # loop optimization

    buf = read_f(buf_size)
    while buf:
        lines += buf.count('\n')
        buf = read_f(buf_size)
    return lines
