from _tenc import TZArchive
from _tenc import MAP_ORDER as MAP

available_parsers = dict()
available_serializers = dict()


def entities_index(archive_path, prefix):
    return __extract_index(archive_path, TZArchive.ENTITIES_FOUT, prefix)


def predicates_index(archive_path, prefix):
    return __extract_index(archive_path, TZArchive.PREDICATES_FOUT, prefix)


def entity_attributes_index(archive_path, prefix):
    return __extract_index(archive_path, TZArchive.ENTITIES_FOUT + '_attr', prefix)


def predicate_attributes_index(archive_path, prefix):
    return __extract_index(archive_path, TZArchive.PREDICATES_FOUT + '_attr', prefix)


def __extract_index(fin, mode, prefix):
    import tarfile
    from _tenc import read_tensor_index, fjoin

    arc = tarfile.open(fin, 'r:bz2')
    m = arc.extractfile(fjoin(mode, TZArchive.MAP_SUFFIX, prefix))
    return read_tensor_index(m)


def register_parser(name, description):
    def _reg(cls):
        available_parsers[name] = (cls, description)
    return _reg


def register_serializer(name, description):
    def _reg(cls):
        available_serializers[name] = (cls, description)
    return _reg
