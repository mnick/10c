#!/usr/bin/env python

# tenc - tool to convert large multigraphs to adjacency tensors
# Copyright (C) 2013 Maximilian Nickel <max@inmachina.com>

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
import sys
import os
from optparse import OptionParser
from configobj import ConfigObj
from tenc import parser, serializer
from tenc import available_parsers, available_serializers

# setup logging
log = logging.getLogger('10c')
logging.basicConfig(level=logging.DEBUG)

# import local modules
if os.path.exists('./_tenc_local.py'):
    log.info('Found _tenc_local in working directory, importing *')
    sys.path = ['.'] + sys.path
    from _tenc_local import *


def err(txt):
    print '[ERROR] %s' % txt
    sys.exit(1)


def print_registry(reg):
    for name, dat in reg.iteritems():
        print "  " + name


def check_file_exists(*files):
    return all([os.path.exists(f.replace('file://', '')) for f in files])


def main():
    # create option parser
    opt = OptionParser()
    opt.add_option('-f', '--file', dest='file', default=None,
                   help='Read N-Triples from file (if not given, read from stdin)')
    opt.add_option('-i', '--input-format', dest='parser', default='ntriples',
                   help='Which parser to use (use option -l to list available parsers)')
    opt.add_option('-o', '--output-format', dest='serializer', default='matlab',
                   help='Which serializer to use (use option -l to list available serializers)')
    opt.add_option('-l', '--list-parsers', dest='list', default=False, action='store_true',
                   help='List available parsers and serializers')
    opt.add_option('-p', '--prefix', dest='prefix', default=None,
                   help='Prepend prefix to output paths')
    opt.add_option('--min-count-pred', dest='min_count_pred', default=1,
                   help='Minimal number of entries in predicate to avoid pruning (default: 10)')
    opt.add_option('--min-count-ent', dest='min_count_ent', default=1,
                   help='Minimal number of entries for an entity to avoid pruning (default: 5)')
    opt.add_option('-n', '--no-convert', dest='do_convert', default=True, action='store_false',
                   help='Do not convert raw data into tz file, but work from precomputed one')
    opt.add_option('-v', '--verbose', dest='quiet', default=True, action='store_false',
                   help='Verbose output messages')
    opt.add_option('--init', dest='do_init', default=False, action='store_true',
                   help='Create initial config file')

    # if config file exists read its content and set as defaults for optparse
    #if os.path.exists('tenc.cfg'):
    #    conf = ConfigObj('tenc.cfg')
    #    opt.set_defaults(**conf['tenc'])

    # parse cli options
    (options, args) = opt.parse_args()

    if options.do_init is True:
        print 'HERE'
        c = ConfigObj()
        c.filename = 'tenc.cfg'
        options.do_init = False
        c['tenc'] = vars(options)
        c.write()
        sys.exit()

    # if list option exists list available parsers and exit
    if options.list is True:
        print "Available parser:"
        print_registry(available_parsers)
        print
        print "Available serializer:"
        print_registry(available_serializers)
        sys.exit()

    # handle unknown parsers
    if not options.parser in available_parsers:
        err('Unknown parser (%s)' % options.parser)
    else:
        parser_cls = available_parsers[options.parser][0]

    # handle unknown serializer
    if not options.serializer in available_serializers:
        err('Unknown serializer (%s)' % options.serializer)
    else:
        ser_cls = available_serializers[options.serializer][0]

    if not options.quiet:
        logging.basicConfig(level=logging.DEBUG)

    if isinstance(options.file, basestring):
        options.file = [options.file]
    if options.file is None:
        #fin = sys.stdin
        fin = ['']
        log.info('Reading data from stdin')
    elif not check_file_exists(*options.file):
        err('File does not exist (%s)' % options.file)
    else:
        fin = options.file
        log.info('Reading data from %s' % fin)

    if options.do_convert:
        attributes = {}
        p = parser_cls(options.prefix, attributes)
        p.convert(options.file)

    s = ser_cls(options.prefix)
    s.serialize(
        (int(options.min_count_ent), int(options.min_count_pred)),
    )
