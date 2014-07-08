from _tenc import TZArchive
from _tenc import MAP_ORDER as MAP

available_parsers = dict()
available_serializers = dict()

# -- Convenience Functions --
def entities_index(archive_path, prefix=None, fprune=None):
    elements = __extract_index(archive_path, TZArchive.ENTITIES_FOUT, prefix)
    return __prune_elements(elements, fprune)

def predicates_index(archive_path, prefix=None, fprune=None):
    elements = __extract_index(archive_path, TZArchive.PREDICATES_FOUT, prefix)
    return __prune_elements(elements, fprune)


def entity_attributes_index(archive_path, prefix=None):
    return __extract_index(archive_path, TZArchive.ENTITIES_FOUT + '_attr', prefix)


def predicate_attributes_index(archive_path, prefix=None):
    return __extract_index(archive_path, TZArchive.PREDICATES_FOUT + '_attr', prefix)


def __extract_index(farc, fin, prefix=None):
    import tarfile
    from _tenc import read_tensor_index, fjoin

    with tarfile.open(farc, 'r:bz2') as arc:
        m = arc.extractfile(fjoin(fin, TZArchive.MAP_SUFFIX, prefix))
        idx = read_tensor_index(m)
    return idx

def __prune_elements(elements, fprune):
    from _tenc import read_tensor_index

    if fprune is not None:
        with open(fprune, 'rb') as fin:
            idx = read_tensor_index(fin)
            elements = [elements[int(i)] for i in idx]
    return elements

def register_parser(name, description):
    def _reg(cls):
        available_parsers[name] = (cls, description)
    return _reg


def register_serializer(name, description):
    def _reg(cls):
        available_serializers[name] = (cls, description)
    return _reg
