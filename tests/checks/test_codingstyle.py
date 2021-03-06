from itertools import chain

from pkgcore.ebuild.eapi import EAPI

from pkgcheck.checks import codingstyle

from .. import misc


class TestBadInsIntoUsage(misc.ReportTestCase):

    check_kls = codingstyle.BadInsIntoCheck

    def test_it(self):
        fake_pkg = misc.FakePkg("dev-util/diffball-0.5")
        fake_src = [
            "# This is our first fake ebuild\n",
            "\n",
            "\tinsinto /usr/bin\n",
            "\tinsinto /etc/env.d\n",
            "\tinsinto /etc/conf.d\n",
            "\tinsinto /etc/init.d/\n",
            "\tinsinto /etc/pam.d\n",
            "\tinsinto /usr/share/applications\n",
            "\tinsinto /usr/share/applications/\n",
            "\tinsinto //usr/share//applications//\n",
            "\tinsinto /etc/cron.d\n",
            "\tinsinto /etc/cron.hourly\n",
            "\tinsinto /etc/cron.daily\n",
            "\tinsinto /etc/cron.weekly\n",
            "# That's it for now\n",
        ]

        bad = (
            "/etc/env.d", "/etc/conf.d", "/etc/init.d", "/etc/pam.d",
            "/usr/share/applications", "/usr/share/applications",
            "//usr/share//applications", "/etc/cron.d", "/etc/cron.hourly",
            "/etc/cron.daily", "/etc/cron.weekly")
        check = self.check_kls(options=None)

        reports = self.assertReports(check, [fake_pkg, fake_src])
        dirs = [x.insintodir for x in reports]
        assert dirs == list(bad)


class TestAbsoluteSymlink(misc.ReportTestCase):

    check_kls = codingstyle.AbsoluteSymlinkCheck

    def test_it(self):
        absolute = (
            ("/bin/blah", "/bin/baz"),
            ('"/bin/blah baz"', "/bin/blahbaz"),
            ("'/bin/blah baz'", "/bin/blahbaz"),
            ("/etc/Boo", "/etc/boo"),
        )

        relative = (
            ("blah", "/bin/baz"),
            ('"blah baz"', "/bin/blahbaz"),
            ("Boo", "/etc/boo"),
        )

        unhandled = (
            ("/crazy/root/dir", "/crazy/symlink"),
        )

        fake_pkg = misc.FakePkg("dev-util/diffball-0.5")
        fake_src = [
            "# This is our first fake ebuild\n",
            "\n",
        ]
        for src, dest in chain.from_iterable((absolute, relative, unhandled)):
            fake_src.append(f"\tdosym {src} {dest}\n")
        fake_src.append("# That's it for now\n")

        check = self.check_kls(options=None)
        reports = self.assertReports(check, [fake_pkg, fake_src])
        abspaths = [x.abspath for x in reports]

        assert len(reports) == len(absolute)
        assert abspaths == [x[0].strip('"\'').split()[0] for x in absolute]


class TestPathVariablesCheck(misc.ReportTestCase):

    check_kls = codingstyle.PathVariablesCheck
    check = check_kls(options=None)

    def _found(self, cls, suffix=''):
        # check single and multiple matches across all specified variables
        for lines in (1, 2):
            for path_var in self.check_kls.variables:
                fake_src = ["src_install() {\n"]
                for x in range(lines):
                    fake_src.append(f'   rm "${{{path_var}{suffix}}}"a/file{x} || die\n')
                fake_src.extend(["}\n", "\n"])
                for eapi_str, eapi in EAPI.known_eapis.items():
                    fake_pkg = misc.FakePkg("dev-util/diff-0.5", data={'EAPI': eapi_str})
                    if eapi.options.trailing_slash:
                        self.assertNoReport(self.check, [fake_pkg, fake_src])
                    else:
                        r = self.assertReport(self.check, [fake_pkg, fake_src])
                        assert isinstance(r, cls)
                        assert r.variable == f'${{{path_var}{suffix}}}'
                        assert r.lines == tuple(x + 2 for x in range(lines))
                        assert path_var in str(r)

    def _unfound(self, cls, suffix=''):
        for path_var in self.check_kls.variables:
            fake_src = [
                "src_install() {\n",
                f'   rm "${{S}}"a/random/file || die\n',
                "}\n",
                "\n",
            ]
            for eapi_str, eapi in EAPI.known_eapis.items():
                fake_pkg = misc.FakePkg("dev-util/diffball-0.5", data={'EAPI': eapi_str})
                self.assertNoReport(self.check, [fake_pkg, fake_src])

    def test_missing_found(self):
        self._found(codingstyle.MissingSlash)

    def test_missing_unfound(self):
        self._unfound(codingstyle.MissingSlash)

    def test_unnecessary_found(self):
        self._found(codingstyle.UnnecessarySlashStrip, suffix='%/')

    def test_unnecessary_unfound(self):
        self._unfound(codingstyle.UnnecessarySlashStrip, suffix='%/')
