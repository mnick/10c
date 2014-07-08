import logging
import numpy as np
from scipy.io.matlab import savemat
from scipy.sparse import coo_matrix

from tenc import MAP, register_serializer
from _tenc import TZArchive, Counter
from _tenc import fjoin, write_tensor_index, read_tensor_size, prune
# setup logging
log = logging.getLogger('serializer')


class Serializer(TZArchive):

    fin_subs = None
    fin_eattr = None
    fin_rattr = None
    eidx = None
    pidx = None
    nnz = None

    def __init__(self, fname='tensor', attr_map={}):
        TZArchive.__init__(self, fname, 'r:bz2')
        self.attr_map = attr_map

    def write_prune_idx(self, idx, fname):
        pout = open(fjoin(fname + '_pruned', self.MAP_SUFFIX, self.fname), 'wb')
        write_tensor_index(pout, idx, sort=True)
        pout.close()

    def serialize(self, min_count):
        # open archive
        N, K, self.nnz = read_tensor_size(self.arc.extractfile(
            fjoin(self.SUBS_FOUT, self.SHAPE_SUFFIX)
        ))

        # extract files for subscripts and attributes
        self.fin_subs = self.arc.extractfile(fjoin(self.SUBS_FOUT, self.SUBS_SUFFIX))
        self.fin_eattr = self.arc.extractfile(fjoin(self.ENTITIES_FOUT, self.ATTR_SUFFIX))
        self.fin_rattr = self.arc.extractfile(fjoin(self.PREDICATES_FOUT, self.ATTR_SUFFIX))

        self.eidx = prune(min_count[0], self.nnz[MAP.ENTITY], N, 'entity')
        self.pidx = prune(min_count[1], self.nnz[MAP.PREDICATE], K, 'predicate')
        self.nnz[MAP.PREDICATE] = self.nnz[MAP.PREDICATE][self.pidx.keys()]
        self.nnz[MAP.ENTITY] = self.nnz[MAP.ENTITY][self.eidx.keys()]

        self.write()

        # write pruned predicates index
        self.write_prune_idx(self.pidx, self.PREDICATES_FOUT)
        # write pruned entities index
        self.write_prune_idx(self.eidx, self.ENTITIES_FOUT)

    def write(self):
        raise NotImplementedError()

    def relations(self):
        """
        Iterator over all triples that involve entities and predicates that
        have not been pruned
        """
        s, o, p, val = 0, 0, 0, 0.0
        for line in self.fin_subs:
            s, o, p, val = line.strip().split()
            s, o, p, val = int(s), int(o), int(p), float(val)
            # check if pruned
            if p in self.pidx and s in self.eidx and o in self.eidx:
                yield (self.eidx[s], self.pidx[p], self.eidx[o], val)

    @staticmethod
    def attributes(fin, keep_idx):
        """
        Iterator over item, attribute tuples for all items that have not been pruned
        """
        for line in fin:
            e, a, v = line.strip().split()
            e, a, v = int(e), int(a), float(v)
            if e in keep_idx:
                yield (keep_idx[e], a, v)

    def entity_attributes(self):
        """
        Iterator over entity, attribute tuples for all entities that have not been pruned
        """
        for a in self.attributes(self.fin_eattr, self.eidx):
            yield a

    def predicate_attributes(self):
        """
        Iterator over predicate, attribute tuples for all predicates that have not been pruned
        """
        for a in self.attributes(self.fin_rattr, self.pidx):
            yield a


@register_serializer('matlab', '')
class Matlab(Serializer):
    """
    Serialize tensor archive in matlab format
    """

    def write(self):
        from postprocess import tfidf
        K = len(self.nnz[MAP.PREDICATE])
        N = len(self.nnz[MAP.ENTITY])
        nnz_tensor = sum(self.nnz[0])
        subs = np.zeros((nnz_tensor, 3), dtype=np.int)
        vals = np.zeros((nnz_tensor, 1), dtype=np.double)
        offset = 0
        for s, p, o, val in self.relations():
            # awesome matlab start-at-1 indexing...
            subs[offset, :] = (s + 1, o + 1, p + 1)
            vals[offset] = val
            offset += 1

        # remove zeros
        nnzidx = vals.nonzero()[0]
        vals = vals[nnzidx]
        subs = subs[nnzidx, :]

        eattr = self.__create_matlab_attr(self.entity_attributes, N, self.nnz[MAP.EATTR], postprocessor=tfidf)
        rattr = self.__create_matlab_attr(self.predicate_attributes, K, self.nnz[MAP.RATTR], postprocessor=tfidf)

        log.debug('Writing MATLAB tensor')
        savemat(fjoin(TZArchive.SUBS_FOUT, 'mat', self.fname), {
            'subs': subs,
            'vals': vals,
            'size': (N, N, K),
            'eattr': eattr,
            'rattr': rattr
        }, oned_as='column')
        return subs, vals

    def __create_matlab_attr(self, attr_generator, N, nnz, min_count=1, postprocessor=None):
        _subs = np.zeros((nnz, 2), dtype=np.int)
        _vals = np.zeros(nnz, dtype=np.double)
        offset = 0
        A = -1
        for e, a, v in attr_generator():
            # get number of attributes
            A = max(a, A)
            _subs[offset, :] = (e, a)
            _vals[offset] = v
            offset += 1
        # handle empty attribute files
        if A == -1:
            return []

        # normal attribute handling
        _subs = zip(*_subs.tolist())
        attr = coo_matrix((_vals, _subs), shape=(N, A + 1))

        # prune attribute
        c = Counter(attr.nonzero()[1])  # count attibute occurrences
        idx = [i[0] for i in c.iteritems() if i[1] > min_count]
        log.debug('Pruned attributes %d -> %d (min_count: %d)' % (attr.shape[1], len(idx), min_count))
        attr = attr.tocsc()[:, idx]

        # postprocessing
        if postprocessor is not None:
            attr = postprocessor(attr)
        return attr


@register_serializer('mln', '')
class MarkovLogicSerializer(Serializer):

    template = '%s%s(%s,%s)\n'

    def write(self):
        fout = open('%s-generated.db' % self.fname, 'wb')

        # write relations
        enames = self.entity_index(self.eidx)
        pnames = self.predicate_index(self.pidx)
        for s, p, o, val in self.relations():
            modifier = '!' if val == -1 else ''
            fout.write(self.template % (modifier, pnames[p], enames[s], enames[o]))

        # write attributes
        aname = self.entity_attributes_index()
        for e, a, val in self.entity_attributes():
            attr_type, attr_id, val = aname[a].split(',')
            modifier = '!' if val == -1 else ''
            fout.write(self.template % (modifier, attr_id, enames[e], val))
        fout.close()


@register_serializer('ntriples', '')
class NTriples(Serializer):
    entity_template = '<file://localhost/%s/%%s>'
    relation_template = '%s %s %s .\n'
    attribute_template = '%s %s "%%s" .\n'

    def __init__(self, fname='tensor', attr_map={}):
        Serializer.__init__(self, fname, attr_map)
        self.entity_template = self.entity_template % fname
        self.relation_template = self.relation_template % (self.entity_template, self.entity_template, self.entity_template)
        self.attribute_template = self.attribute_template % (self.entity_template, self.entity_template)

    def write(self):
        fout = open('%s-generated.nt' % self.fname, 'wb')

        # write relations
        enames = self.entity_index(self.eidx)
        pnames = self.predicate_index(self.pidx)
        for s, p, o, val in self.relations():
            fout.write(self.relation_template % (enames[s], pnames[p], enames[o]))

        # write attributes
        aname = self.entity_attributes_index()
        for e, a, val in self.entity_attributes():
            _, attr_id, val = aname[a].split(',')
            fout.write(self.attribute_template % (enames[e], attr_id, val))
        fout.close()


@register_serializer('turtle', '')
class Turtle(Serializer):
    relation_template = 'l:%s l:%s l:%s .\n'
    attribute_template = 'l:%s l:%s "%s" .\n'

    def write(self):
        fout = open('%s-generated.ttl' % self.fname, 'wb')
        fout.write('@prefix l: <file://localhost/%s/> .\n' % self.fname)

        # write relations
        enames = self.entity_index(self.eidx)
        pnames = self.predicate_index(self.pidx)
        for s, p, o, val in self.relations():
            fout.write(self.relation_template % (enames[s], pnames[p], enames[o]))

        # write attributes
        aname = self.entity_attributes_index()
        for e, a, val in self.entity_attributes():
            _, attr_id, val = aname[a].split(',')
            fout.write(self.attribute_template % (enames[e], attr_id, val))


def python(fin, eidx, pidx, nnz, prefix, fin_eattr=None, fin_rattr=None):
    import cPickle

    # create x,y subs for each predicate
    subs = [None for _ in xrange(len(nnz))]
    for k in xrange(len(nnz)):
        subs[k] = [np.zeros(nnz[k], dtype=np.int), np.zeros(nnz[k], dtype=np.int)]

    # read subs
    log.debug('Reading tensor subscripts')
    offset = [0 for _ in xrange(len(subs))]
    for line in fin:
        s, o, p = np.int_(line.strip().split())
        subs[p][0][offset[p]] = s
        subs[p][1][offset[p]] = o
        offset[p] += 1

    log.debug('Creating COO-format tensors')
    T = [None for _ in xrange(len(pidx))]
    for k in xrange(len(pidx)):
        p = pidx[k]
        vals = np.ones(len(subs[p][0]))
        T[k] = coo_matrix((vals, (subs[p][0], subs[p][1])), shape=(N, N))

    cPickle.dump(open(__fjoin(TZArchive.SUBS_FOUT, 'bin', prefix), 'wb'),
                 T, protocol=cPickle.HIGHEST_PROTOCOL)



