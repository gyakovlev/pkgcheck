from snakeoil.strings import pluralism as _pl

from ..base import Template, package_feed, Warning, versioned_feed


class RedundantVersion(Warning):
    """Redundant version(s) of a package in a specific slot."""

    __slots__ = ("category", "package", "version", "slot", "later_versions")
    threshold = versioned_feed

    def __init__(self, pkg, higher_pkgs):
        super().__init__()
        self._store_cpv(pkg)
        self.slot = pkg.slot
        self.later_versions = tuple(x.fullver for x in higher_pkgs)

    @property
    def short_desc(self):
        return "slot(%s) keywords are overshadowed by version%s: %s" % (
            self.slot, _pl(self.later_versions), ', '.join(self.later_versions))


class RedundantVersionReport(Template):
    """Scan for overshadowed package versions.

    Scan for versions that are likely shadowed by later versions from a
    keywords standpoint (ignoring -9999 versioned packages)

    Example: pkga-1 is keyworded amd64, pkga-2 is amd64.
    pkga-1 can potentially be removed.
    """

    feed_type = package_feed
    known_results = (RedundantVersion,)

    def feed(self, pkgset, reporter):
        if len(pkgset) == 1:
            return

        # algo is roughly thus; spot stable versions, hunt for subset
        # keyworded pkgs that are less then the max version;
        # repeats this for every overshadowing detected
        # finally, does version comparison down slot lines
        stack = []
        bad = []
        for pkg in reversed(pkgset):
            # reduce false positives for idiot keywords/ebuilds
            if pkg.live:
                continue
            curr_set = set(x for x in pkg.keywords if not x.startswith("-"))
            if not curr_set:
                continue

            matches = [ver for ver, keys in stack if ver.slot == pkg.slot and
                       not curr_set.difference(keys)]

            # we've done our checks; now we inject unstable for any stable
            # via this, earlier versions that are unstable only get flagged
            # as "not needed" since their unstable flag is a subset of the
            # stable.

            # also, yes, have to use list comp here- we're adding as we go
            curr_set.update(["~"+x for x in curr_set if not x.startswith("~")])

            stack.append([pkg, curr_set])
            if matches:
                bad.append((pkg, matches))

        for pkg, matches in reversed(bad):
            reporter.add_report(RedundantVersion(pkg, matches))
