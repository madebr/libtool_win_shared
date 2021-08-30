from conans import ConanFile, tools, AutoToolsBuildEnvironment
from conans.errors import ConanInvalidConfiguration
import textwrap


class LibtoolWinConan(ConanFile):
    name = "libtool_win_shared"
    version = "0.1"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "libdep": ["file", "dash"],
    }
    default_options = {
        "libdep": "file",
    }

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    def build_requirements(self):
        self.build_requires("libtool/2.4.6")
        if self._settings_build.os == "Windows" and not tools.get_env("CONAN_BASH_PATH"):
            self.build_requires("msys2/cci.latest")

    def validate(self):
        if self.settings.os != "Windows":
            raise ConanInvalidConfiguration("Only Windows")

    def _build_libdep(self):
        tools.save("libdep.c", textwrap.dedent("""\
            __declspec(dllexport)
            int libfunc(void) {
                return 1337;
            }
        """))
        if self.settings.compiler == "Visual Studio":
            with tools.vcvars(self):
                self.run("cl -W4 -WX libdep.c -link -dll -out:dep.dll -implib:dep.lib")
        else:
            self.run("{CC} -Wall -Werror libdep.c -fvisibility=hidden --shared -o dep.dll -Wl,--out-implib,libdep.dll.a".format(CC=tools.get_env("CC", "gcc")))

    @property
    def _libdep_name(self):
        return "dep.lib" if self.settings.compiler == "Visual Studio" else "libdep.dll.a"

    def _build_libconsumer(self):
        tools.save("consumer.c", textwrap.dedent("""\
            __declspec(dllimport) int libfunc(void);
            #ifdef DLL_EXPORT
            __declspec(dllexport)
            #endif
            int consumer_func(void) {
                return libfunc();
            }
        """))
        tools.save("configure.ac", textwrap.dedent("""\
            AC_PREREQ([2.69])
            AC_INIT([libtool_win_shared], [1.0])
            AC_CONFIG_SRCDIR([consumer.c])
            AM_INIT_AUTOMAKE([-Wall -Werror foreign])
            AC_PROG_CC
            AM_PROG_AR
            LT_PREREQ([2.4])
            LT_INIT([win32-dll])
            AC_CONFIG_FILES([Makefile])
            AC_OUTPUT
        """))
        tools.save("Makefile.am", textwrap.dedent("""\
            ACLOCAL_AMFLAGS = -I m4
            lib_LTLIBRARIES = libconsumer.la
            
            libconsumer_la_SOURCES = consumer.c
            libconsumer_la_LDFLAGS = {lib} -no-undefined
        """).format(lib="-L$(top_builddir) -ldep" if False else self._libdep_name))
        self.run("{} -fiv".format(tools.get_env("AUTORECONF")), win_bash=tools.os_info.is_windows, run_environment=True)
        autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
        autotools.configure()
        autotools.make()
        autotools.install()

    def build(self):
        self._build_libdep()
        self._build_libconsumer()


