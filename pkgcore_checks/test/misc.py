# Copyright: 2007 Brian Harring <ferringb@gmail.com>
# License: GPL2

from pkgcore.test import TestCase
from pkgcore.ebuild.ebuild_src import package
from pkgcore.ebuild.cpv import CPV
from pkgcore.ebuild.atom import atom
from pkgcore.repository.util import SimpleTree
from pkgcore.ebuild.misc import collapsed_restrict_to_data
from pkgcore.restrictions.packages import AlwaysTrue
from pkgcore_checks.addons import ArchesAddon

default_arches = ArchesAddon.default_arches


class FakePkg(package):
    def __init__(self, cpvstr, data=None, shared=None, repo=None):
        if data is None:
            data = {}

        for x in ("DEPEND", "RDEPEND", "PDEPEND", "IUSE", "LICENSE"):
            data.setdefault(x, "")
        
        cpv = CPV(cpvstr)
        package.__init__(self, shared, repo, cpv.category, cpv.package,
            cpv.fullver)
        object.__setattr__(self, "data", data)


class FakeTimedPkg(package):
    __slots__ = "_mtime_"
    
    def __init__(self, cpvstr, mtime, data=None, shared=None, repo=None):
        if data is None:
            data = {}
        cpv = CPV(cpvstr)
        package.__init__(self, shared, repo, cpv.category, cpv.package,
            cpv.fullver)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "_mtime_", mtime)


class ReportTestCase(TestCase):

    def assertNoReport(self, check, data):
        l = []
        r = fake_reporter(lambda r:l.append(r))
        check.feed(data, r)
        self.assertEqual(l, [], list(report.to_str() for report in l))

    def assertReports(self, check, data):
        l = []
        r = fake_reporter(lambda r:l.append(r))
        check.feed(data, r)
        self.assertTrue(l)
        return l

    def assertIsInstance(self, obj, kls):
        self.assertTrue(isinstance(obj, kls), 
            msg="%r must be %r" % (obj, kls))

    def assertReport(self, check, data):
        r = self.assertReports(check, data)
        self.assertEqual(len(r), 1)
        return r[0]


class fake_reporter(object):
    def __init__(self, callback):
        self.add_report = callback


class Options(dict):
    __setattr__ = dict.__setitem__
    __getattr__ = dict.__getitem__
    __delattr__ = dict.__delitem__


class FakeProfile(object):

    def __init__(self, masked_use={}, forced_use={},
        provides={}, masks=[], virtuals={}, arch='x86', name='none'):
        self.provides_repo = SimpleTree(provides)
        self.masked_use = dict((atom(k), v) for k,v in masked_use.iteritems())
        self.forced_use = dict((atom(k), v) for k,v in forced_use.iteritems())
        self.masks = tuple(map(atom, masks))
        self.virtuals = SimpleTree(virtuals)
        self.arch = arch
        self.name = name

        self.forced_data = collapsed_restrict_to_data(
            [(AlwaysTrue, (self.arch,))],
            self.forced_use.iteritems())

        self.masked_data = collapsed_restrict_to_data(
            [(AlwaysTrue, default_arches)],
            self.masked_use.iteritems())
            
    def make_virtuals_repo(self, repo):
        return self.virtuals
