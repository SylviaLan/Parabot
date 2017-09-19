# -*- coding: utf-8 -*-

import os,time
import subprocess
from robot.conf import RobotSettings
from robot.output import LOGGER
from robot.running import TestSuiteBuilder
from robot.utils import Application, unic
from multiprocessing import cpu_count
from multiprocessing import Pool as ProcessPool


import sys
reload(sys)
sys.setdefaultencoding('gbk')

USAGE = """Robot Framework -- A generic test automation framework
Version:  <VERSION>

Usage:  Parabot [options] data_sources, like pybot
   or:  python -m Parabot [options] data_sources

Robot Framework is open source software released under Apache License 2.0.
For more information about the framework and the rich ecosystem around it
see http://robotframework.org/.

Options
=======

 -d --outputdir dir       Where to create output files. The default is the
                          directory where tests are run from and the given path
                          is considered relative to that unless it is absolute.
 -i --include tag *       Select test cases to run by tag. Similarly as name
                          with --test, tag is case and space insensitive and it
                          is possible to use patterns with `*` and `?` as
                          wildcards. Tags and patterns can also be combined
                          together with `AND`, `OR`, and `NOT` operators.
                          Examples: --include foo --include bar*
                                    --include fooANDbar*
 -e --exclude tag *       Select test cases not to run by tag. These tests are
                          not run even if included with --include. Tags are
                          matched using the rules explained with --include.
 -p --processes num       How many processes to be run.                                
                          
 -v --variable name:value *  Set variables in the test data. Only scalar
                          variables with string value are supported and name is
                          given without `${}`. See --escape for how to use
                          special characters and --variablefile for a more
                          powerful variable setting mechanism.
                          Examples:
                          --variable str:Hello       =>  ${str} = `Hello`
                          -v hi:Hi_World -E space:_  =>  ${hi} = `Hi World`
                          -v x: -v y:42              =>  ${x} = ``, ${y} = `42`
 -V --variablefile path *  Python or YAML file file to read variables from.
                          Possible arguments to the variable file can be given
                          after the path using colon or semicolon as separator.
                          Examples: --variablefile path/vars.yaml
                                    --variablefile environment.py:testing
 -h -? --help             Print usage instructions.
                          """

class Parabot(Application):

    def __init__(self):
        Application.__init__(self, USAGE, arg_limits=(1,),
                             env_options='ROBOT_OPTIONS', logger=LOGGER)

    def main(self, datasources, **options):
        for key,value in options.items():
            if not value:
                options.pop(key)
        settings = RobotSettings(options)
        LOGGER.register_console_logger(**settings.console_output_config)
        LOGGER.info('Settings:\n%s' % unic(settings))
        suite = TestSuiteBuilder(settings['SuiteNames'],
                                 settings['WarnOnSkipped'],
                                 settings['Extension']).build(*datasources)
        suite.configure(**settings.suite_config)

        data_sources ='"' + '" "'.join(datasources) + '"'

        logFolder =settings['OutputDir']
        if options.has_key('processes'):
            p_num = int(options['processes'])
        else:
            p_num = 2 * cpu_count()  #默认两倍cpu核数



        longname=[]
        testnames = self._split_tests(suite,longname) #递归，找到所有的tests

        extra_options_cmd = self.unresolve_options(options)

        #运行前先清理环境，主要是把一些Output文件和图片文件清除
        self.clear_env(logFolder)

        #生成并行运行命令并运行
        self.parallel_run(testnames, logFolder, data_sources, extra_options_cmd, p_num)

        #合并报告
        rebotCommand = 'rebot --outputdir "' + logFolder + '" --merge "' + logFolder + '/*_Output.xml"'
        print(rebotCommand)
        merge_proc = subprocess.Popen(rebotCommand, shell=True)
        merge_proc.communicate()


    def parallel_run(self,testnames, logFolder,data_sources,extra_options_cmd='',processnum = 1):
        starttime = time.time()
        print 'start at: ', time.ctime()

        commands_list = []
        for tests in testnames:
            output = "%s/%s_Output.xml" % (logFolder,tests)
            PybotCommand = 'pybot ' + extra_options_cmd + '-t "'+ tests + '" -o "' + output  +'" ' + data_sources
            print(PybotCommand)
            commands_list.append(PybotCommand)


        pool = ProcessPool(processnum)  #多进程方式并行
        results = pool.map(os.system,commands_list)
        pool.close()
        pool.join()

        time.sleep(1) #报告生成需要点时间，sleep一下下
        endtime = time.time()
        print 'end at: ', time.ctime()
        print 'elapsed time:', endtime-starttime

    def _split_tests(self, suite, testlong):
        if suite.suites:
            for suites in suite.suites:
                self._split_tests(suites,testlong)
        else:
            for test in suite.tests:
                print test.longname
                testnames = test.longname.decode()
                testlong.append(testnames)
        return testlong

    def unresolve_options(self,options):
        extra_options_cmd = ''
        _extra_options = ['variable',
                          'variablefile',
                          'outputdir'] #如需再拓展其他tag无关的参数，需在这加上
        for key,value in options.items():
            if key not in _extra_options:
                options.pop(key)
            elif isinstance(value,unicode):
                extra_options_cmd = extra_options_cmd + '--' + key + ' ' + value + ' '
            elif value != []:
                for action in value:
                    extra_options_cmd = extra_options_cmd + '--' + key  + ' ' + action + ' '
        return extra_options_cmd

    def clear_env(self, logFolder):
        for files in os.listdir(logFolder):
            if files.endswith('_Output.xml') or files.endswith('.png'):
                os.remove(logFolder +'/' + files)

def parabot_cli(arguments, exit=True):
    """Command line execution entry point for running tests.

    :param arguments: Command line options and arguments as a list of strings.
    :param exit: If ``True``, call ``sys.exit`` with the return code denoting
        execution status, otherwise just return the rc. New in RF 3.0.1.

    Entry point used when running tests from the command line, but can also
    be used by custom scripts that execute tests. Especially useful if the
    script itself needs to accept same arguments as accepted by Robot Framework,
    because the script can just pass them forward directly along with the
    possible default values it sets itself.

    Example::

        from robot import run_cli

        # Run tests and return the return code.
        rc = run_cli(['--name', 'Example', 'tests.robot'], exit=False)

        # Run tests and exit to the system automatically.
        run_cli(['--name', 'Example', 'tests.robot'])

    See also the :func:`run` function that allows setting options as keyword
    arguments like ``name="Example"`` and generally has a richer API for
    programmatic test execution.
    """
    return Parabot().execute_cli(arguments, exit=exit)

if __name__ == '__main__':
    parabot_cli(sys.argv[1:])

