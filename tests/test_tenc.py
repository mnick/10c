from tenc._tenc import *
from StringIO import StringIO


class MockFile(StringIO):
    name = 'mock'


class TestTenc(object):
    def setup(self):
        self.emap = {'e1': 0, 'e0': 1}
        self.pmap = {'r1': 0, 'r2': 1, 'r0': 2}
        self.nnz = [
            [3, 4],
            [2, 8, 53],
            25,
            103
        ]

    def test_fjoin(self):
        assert 'super-test.wow' == fjoin('test', 'wow', 'super')
        assert 'test.wow' == fjoin('test', 'wow')


    def test_write_tensor_size(self):
        fout = MockFile()
        write_tensor_size(fout, self.emap, self.pmap, self.nnz)
        expected = '\n'.join(map(str, [2, 3, 3, 4, 2, 8, 53, 25, 103])) + '\n'
        assert expected == fout.getvalue(), '%s != expected %s' % (fout.getvalue(), expected)

    def test_write_tensor_index(self):
        # check that names are sorted by idx
        fout = MockFile()
        write_tensor_index(fout, self.emap, True)
        assert 'length: 2\ne1\ne0\n' == fout.getvalue()

        # assume we have already sorted names
        idx = ['e0', 'e1']
        fout = MockFile()
        write_tensor_index(fout, idx, False)
        assert 'length: 2\ne0\ne1\n' == fout.getvalue()
