/* Native app executable: embed CPython but expose its real bundled interpreter
 * for ordinary case-scoped MCP subprocesses. No shell or inherited Python paths. */
#include <Python.h>
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char raw[PATH_MAX], executable[PATH_MAX], resources[PATH_MAX];
    char home[PATH_MAX], python[PATH_MAX];
    uint32_t size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &size) || !realpath(raw, executable)) return 70;
    char *slash = strrchr(executable, '/'); if (!slash) return 70; *slash = 0;
    if (snprintf(resources, sizeof(resources), "%s/../Resources", executable) >= sizeof(resources)) return 70;
    if (!realpath(resources, raw)) return 70;
    snprintf(resources, sizeof(resources), "%s", raw);
    snprintf(home, sizeof(home), "%s/runtime", resources);
    snprintf(python, sizeof(python), "%s/bin/python3", home);
    setenv("VOLATILITY_WORKBENCH_RESOURCES", resources, 1);
    chdir(resources);
    /* Finder has no shell locale. Force UTF-8 before Python chooses codecs or
     * subprocess text decoding; catalog labels contain Unicode middots. */
    PyPreConfig preconfig; PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    PyStatus status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) Py_ExitStatusException(status);
    PyConfig config; PyConfig_InitIsolatedConfig(&config);
    config.write_bytecode = 0;
    config.parse_argv = 0;
    status = PyConfig_SetBytesString(&config, &config.home, home);
    if (!PyStatus_Exception(status)) status = PyConfig_SetBytesString(&config, &config.executable, python);
    if (!PyStatus_Exception(status)) status = PyConfig_SetBytesArgv(&config, argc, argv);
    if (!PyStatus_Exception(status) && argc == 2 && !strcmp(argv[1], "--check-bundled-runtime")) {
        status = PyConfig_SetString(&config, &config.run_command,
            L"import sys, subprocess, json, locale; assert sys.flags.utf8_mode; assert sys.dont_write_bytecode; "
            L"value=subprocess.check_output([sys.executable,'-I','-c','print(chr(183))'],text=True).strip(); "
            L"assert value==chr(183); print(json.dumps({'native_launcher':'passed','utf8_mode':sys.flags.utf8_mode,'subprocess_unicode':True}))");
    } else if (!PyStatus_Exception(status)) {
        status = PyConfig_SetString(&config, &config.run_module, L"volatility_workbench.desktop");
    }
    if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) Py_ExitStatusException(status);
    return Py_RunMain();
}
