"""Basic reporters and reporter factories."""

from pkgcore.config import configurable
from snakeoil import formatters
from snakeoil.demandload import demandload

from . import base

demandload(
    'collections:defaultdict',
    'json',
    'xml.sax.saxutils:escape@xml_escape',
    'snakeoil:currying,pickling',
    'pkgcheck:errors',
)


class StrReporter(base.Reporter):
    """Simple string reporter, pkgcheck-0.1 behaviour.

    Example::

        sys-apps/portage-2.1-r2: sys-apps/portage-2.1-r2.ebuild has whitespace in indentation on line 169
        sys-apps/portage-2.1-r2: rdepend  ppc-macos: unsolvable default-darwin/macos/10.4, solutions: [ >=app-misc/pax-utils-0.1.13 ]
        sys-apps/portage-2.1-r2: no change in 75 days, keywords [ ~x86-fbsd ]
    """

    # simple reporter; fallback default
    priority = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._first_report = True

    def process_report(self, result):
        if self._first_report:
            self.out.write()
            self._first_report = False
        if result.threshold == base.versioned_feed:
            self.out.write(
                f"{result.category}/{result.package}-{result.version}: {result.desc}")
        elif result.threshold == base.package_feed:
            self.out.write(f"{result.category}/{result.package}: {result.desc}")
        elif result.threshold == base.category_feed:
            self.out.write(f"{result.category}: {result.desc}")
        else:
            self.out.write(result.desc)

    def finish(self):
        if not self._first_report:
            self.out.write()


class FancyReporter(base.Reporter):
    """grouped colored output

    Example::

        sys-apps/portage
          WrongIndentFound: sys-apps/portage-2.1-r2.ebuild has whitespace in indentation on line 169
          NonsolvableDeps: sys-apps/portage-2.1-r2: rdepend  ppc-macos: unsolvable default-darwin/macos/10.4, solutions: [ >=app-misc/pax-utils-0.1.13 ]
          StaleUnstableKeyword: sys-apps/portage-2.1-r2: no change in 75 days, keywords [ ~x86-fbsd ]
    """

    # default report, akin to repoman
    priority = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = None

    def process_report(self, result):
        if result.threshold in (base.versioned_feed, base.package_feed):
            key = f'{result.category}/{result.package}'
        elif result.threshold == base.category_feed:
            key = result.category
        else:
            key = 'repo'

        if key != self.key:
            self.out.write()
            self.out.write(self.out.bold, key)
            self.key = key
        self.out.first_prefix.append('  ')
        self.out.later_prefix.append('    ')
        s = ''
        if result.threshold == base.versioned_feed:
            s = f"version {result.version}: "
        self.out.write(
            self.out.fg(result.color),
            result.__class__.__name__, self.out.reset,
            ': ', s, result.desc)
        self.out.first_prefix.pop()
        self.out.later_prefix.pop()


class NullReporter(base.Reporter):
    """reporter used for timing tests; no output"""

    priority = -10000000

    def __init__(self, *args, **kwargs):
        pass

    def process_report(self, result):
        pass


class JsonReporter(base.Reporter):
    """Dump a json feed of reports.

    Note that the format is newline-delimited JSON with each line being related
    to a separate report. To merge the objects together something like jq can
    be leveraged similar to the following:

        jq -c -s 'reduce.[]as$x({};.*$x)' orig.json > new.json
    """

    # json report should only be used if requested
    priority = -1000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._json_dict = lambda: defaultdict(self._json_dict)

    def process_report(self, result):
        data = self._json_dict()

        if result.threshold == base.repository_feed:
            d = data
        elif result.threshold == base.category_feed:
            d = data[result.category]
        elif result.threshold == base.package_feed:
            d = data[result.category][result.package]
        else:
            # versioned or ebuild feed
            d = data[result.category][result.package][result.version]

        name = result.__class__.__name__
        d['_' + result.level][name] = [result.desc]

        self.out.write(json.dumps(data))
        # flush output so partial objects aren't written
        self.out.stream.flush()


class XmlReporter(base.Reporter):
    """dump an xml feed of reports"""

    # xml report, shouldn't be used but in worst case.
    priority = -1000

    repo_template = (
        "<result><class>%(class)s</class>"
        "<msg>%(msg)s</msg></result>")
    cat_template = (
        "<result><category>%(category)s</category>"
        "<class>%(class)s</class><msg>%(msg)s</msg></result>")
    pkg_template = (
        "<result><category>%(category)s</category>"
        "<package>%(package)s</package><class>%(class)s</class>"
        "<msg>%(msg)s</msg></result>")
    ver_template = (
        "<result><category>%(category)s</category>"
        "<package>%(package)s</package><version>%(version)s</version>"
        "<class>%(class)s</class><msg>%(msg)s</msg></result>")

    threshold_map = {
        base.repository_feed: repo_template,
        base.category_feed: cat_template,
        base.package_feed: pkg_template,
        base.versioned_feed: ver_template,
        base.ebuild_feed: ver_template,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def start(self):
        self.out.write('<checks>')

    def process_report(self, result):
        d = dict((k, getattr(result, k, '')) for k in
                 ("category", "package", "version"))
        d["class"] = xml_escape(result.__class__.__name__)
        d["msg"] = xml_escape(result.desc)
        self.out.write(self.threshold_map[result.threshold] % d)

    def finish(self):
        self.out.write('</checks>')


class PickleStream(base.Reporter):
    """Generate a stream of pickled objects.

    For each specific target for checks, a header is pickled
    detailing the checks used, possible results, and search
    criteria.
    """
    priority = -1001
    protocol = 0

    def __init__(self, *args, **kwargs):
        """Initialize.

        :type out: L{snakeoil.formatters.Formatter}.
        """
        super().__init__(*args, **kwargs)
        self.dump = pickling.dump

    def start(self):
        self.out.wrap = False
        self.out.autoline = False

    def start_check(self, checks, target):
        self.dump(base.StreamHeader(checks, target), self.out)

    def process_report(self, result):
        try:
            self.dump(result, self.out, self.protocol)
        except TypeError as t:
            raise TypeError(result, str(t))


class BinaryPickleStream(PickleStream):
    """Dump a binary pickle stream (highest protocol).

    For details of the stream, see PickleStream.
    """
    priority = -1002
    protocol = -1


class MultiplexReporter(base.Reporter):

    def __init__(self, reporters, *args, **kwargs):
        if len(reporters) < 2:
            raise ValueError("need at least two reporters")
        super().__init__(*args, **kwargs)
        self.reporters = tuple(reporters)

    def start(self):
        for x in self.reporters:
            x.start()

    def process_report(self, result):
        for x in self.reporters:
            x.process_report(result)

    def finish(self):
        for x in self.reporters:
            x.finish()


def make_configurable_reporter_factory(klass):
    @configurable({'dest': 'str'}, typename='pkgcheck_reporter_factory')
    def configurable_reporter_factory(dest=None):
        if dest is None:
            return klass

        def reporter_factory(out):
            try:
                f = open(dest, 'w')
            except EnvironmentError as e:
                raise errors.ReporterInitError(f'Cannot write to {dest!r} ({e})')
            return klass(formatters.PlainTextFormatter(f))

        return reporter_factory
    return configurable_reporter_factory


json_reporter = make_configurable_reporter_factory(JsonReporter)
json_reporter.__name__ = 'json_reporter'
xml_reporter = make_configurable_reporter_factory(XmlReporter)
xml_reporter.__name__ = 'xml_reporter'
plain_reporter = make_configurable_reporter_factory(StrReporter)
plain_reporter.__name__ = 'plain_reporter'
fancy_reporter = make_configurable_reporter_factory(FancyReporter)
fancy_reporter.__name__ = 'fancy_reporter'
picklestream_reporter = make_configurable_reporter_factory(PickleStream)
picklestream_reporter.__name__ = 'picklestream_reporter'
binarypicklestream_reporter = make_configurable_reporter_factory(BinaryPickleStream)
binarypicklestream_reporter.__name__ = 'binarypicklestream_reporter'
null_reporter = make_configurable_reporter_factory(NullReporter)
null_reporter.__name__ = 'null'


@configurable({'reporters': 'refs:pkgcheck_reporter_factory'},
              typename='pkgcheck_reporter_factory')
def multiplex_reporter(reporters):
    def make_multiplex_reporter(out):
        return MultiplexReporter([factory(out) for factory in reporters])
    return make_multiplex_reporter
