BuildSteps
==========

.. py:module:: buildbot.process.buildstep

There are a few parent classes that are used as base classes for real buildsteps.
This section describes the base classes.
The "leaf" classes are described in :doc:`../manual/configuration/steps/index`.

See :ref:`Writing-New-BuildSteps` for a guide to implementing new steps.

BuildStep
---------

.. py:class:: BuildStep(name, description, descriptionDone, descriptionSuffix, locks, haltOnFailure, flunkOnWarnings, flunkOnFailure, warnOnWarnings, warnOnFailure, alwaysRun, progressMetrics, useProgress, doStepIf, hideStepIf)

    All constructor arguments must be given as keyword arguments.
    Each constructor parameter is copied to the corresponding attribute.

    .. py:attribute:: name

        The name of the step.
        Note that this value may change when the step is started, if the existing name was not unique.

    .. py:attribute:: stepid

        The ID of this step in the database.
        This attribute is not set until the step starts.

    .. py:attribute:: description

        The description of the step.

    .. py:attribute:: descriptionDone

        The description of the step after it has finished.

    .. py:attribute:: descriptionSuffix

        Any extra information to append to the description.

    .. py:attribute:: locks

        List of locks for this step; see :ref:`Interlocks`.

    .. py:attribute:: progressMetrics

        List of names of metrics that should be used to track the progress of this build and build ETA's for users.

    .. py:attribute:: useProgress

        If true (the default), then ETAs will be calculated for this step using progress metrics.
        If the step is known to have unpredictable timing (e.g., an incremental build), then this should be set to false.

    .. py:attribute:: doStepIf

        A callable or bool to determine whether this step should be executed.
        See :ref:`Buildstep-Common-Parameters` for details.

    .. py:attribute:: hideStepIf

        A callable or bool to determine whether this step should be shown in the waterfall and build details pages.
        See :ref:`Buildstep-Common-Parameters` for details.

    The following attributes affect the behavior of the containing build:

    .. py:attribute:: haltOnFailure

        If true, the build will halt on a failure of this step, and not execute subsequent steps (except those with ``alwaysRun``).

    .. py:attribute:: flunkOnWarnings

        If true, the build will be marked as a failure if this step ends with warnings.

    .. py:attribute:: flunkOnFailure

        If true, the build will be marked as a failure if this step fails.

    .. py:attribute:: warnOnWarnings

        If true, the build will be marked as warnings, or worse, if this step ends with warnings.

    .. py:attribute:: warnOnFailure

        If true, the build will be marked as warnings, or worse, if this step fails.

    .. py:attribute:: alwaysRun

        If true, the step will run even if a previous step halts the build with ``haltOnFailure``.

    .. py:attribute:: logEncoding

        The log encoding to use for logs produced in this step, or None to use the global default.
        See :ref:`Log-Encodings`.

    .. py:attribute:: rendered

        At the beginning of the step, the renderable attributes are rendered against the properties.
        There is a slight delay however when those are not yet rendered, which leads to weird and difficult to reproduce bugs.
        To address this problem, a ``rendered`` attribute is available for methods that could be called early in the buildstep creation.

    .. py:attribute:: results

        This is the result (a code from :py:mod:`buildbot.process.results`) of the step.
        This attribute only exists after the step is finished, and should only be used in :py:meth:`getResultSummary`.

    A few important pieces of information are not available when a step is constructed and are added later.
    These are set by the following methods; the order in which these methods are called is not defined.

    .. py:method:: setBuild(build)

        :param build: the :class:`~buildbot.process.build.Build` instance controlling this step.

        This method is called during setup to set the build instance controlling this worker.
        Subclasses can override this to get access to the build object as soon as it is available.
        The default implementation sets the :attr:`build` attribute.

    .. py:attribute:: build

        The build object controlling this step.

    .. py:method:: setWorker(worker)

        :param worker: the :class:`~buildbot.worker.Worker` instance on which this step will run.

        Similarly, this method is called with the worker that will run this step.
        The default implementation sets the :attr:`worker` attribute.

    .. py:attribute:: worker

        The worker that will run this step.

    .. py:attribute:: workdir

        Directory where actions of the step will take place.
        The workdir is set by order of priority:

        * workdir of the step, if defined via constructor argument

        * workdir of the BuildFactory (itself defaults to 'build')

        BuildFactory workdir can also be a function of a sourcestamp (see :ref:`Factory-Workdir-Functions`).

    .. py:method:: setDefaultWorkdir(workdir)

        :param workdir: the default workdir, from the build

        .. note::

           This method is deprecated and should not be used anymore, as workdir is calculated automatically via a property.

    .. py:method:: setupProgress()

        This method is called during build setup to give the step a chance to set up progress tracking.
        It is only called if the build has :attr:`useProgress` set.
        There is rarely any reason to override this method.

    Execution of the step itself is governed by the following methods and attributes.

    .. py:method:: run()

        :returns: result via Deferred

        Execute the step.
        When this method returns (or when the Deferred it returns fires), the step is complete.
        The method's return value must be an integer, giving the result of the step -- a constant from :mod:`buildbot.process.results`.
        If the method raises an exception or its Deferred fires with failure, then the step will be completed with an EXCEPTION result.
        Any other output from the step (logfiles, status strings, URLs, etc.) is the responsibility of the ``run`` method.

        The function is not called if the step is skipped or otherwise not run.

        Subclasses should override this method.

    .. py:method:: interrupt(reason)

        :param reason: why the build was interrupted
        :type reason: string or :class:`~twisted.python.failure.Failure`

        This method is used from various control interfaces to stop a running step.
        The step should be brought to a halt as quickly as possible, by cancelling a remote command, killing a local process, etc.

        The ``reason`` parameter can be a string or, when a worker is lost during step processing, a :exc:`~twisted.internet.error.ConnectionLost` failure.

        The parent method handles any pending lock operations, and should be called by implementations in subclasses.

    .. py:attribute:: stopped

        If false, then the step is running.
        If true, the step is not running, or has been interrupted.

    .. py:attribute:: timed_out

        If ``True``, then one or more remote commands of the step timed out.

    A step can indicate its up-to-the-moment status using a short summary string.
    These methods allow step subclasses to produce such summaries.

    .. py:method:: updateSummary()

        Update the summary, calling :py:meth:`getCurrentSummary` or :py:meth:`getResultSummary` as appropriate.
        Build steps should call this method any time the summary may have changed.
        This method is debounced, so even calling it for every log line is acceptable.

    .. py:method:: getCurrentSummary()

        :returns: dictionary, optionally via Deferred

        Returns a dictionary containing status information for a running step.
        The dictionary can have a ``step`` key with a unicode value giving a summary for display with the step.
        This method is only called while the step is running.

        Build steps may override this method to provide a more interesting summary than the default ``"running"``.

    .. py:method:: getResultSummary()

        :returns: dictionary, optionally via Deferred

        Returns a dictionary containing status information for a completed step.
        The dictionary can have keys ``step`` and ``build``, each with unicode values.
        The ``step`` key gives a summary for display with the step, while the ``build`` key gives a summary for display with the entire build.
        The latter should be used sparingly, and include only information that the user would find relevant for the entire build, such as a number of test failures.
        Either or both keys can be omitted.

        This method is only called when the step is finished.
        The step's result is available in ``self.results`` at that time.

        Build steps may override this method to provide a more interesting summary than the default, or to provide any build summary information.


    .. py:method:: getBuildResultSummary()

        :returns: dictionary, optionally via Deferred

        Returns a dictionary containing status information for a completed step.
        This method calls :py:meth:`getResultSummary`, and automatically computes a ``build`` key from the ``step`` key according to the ``updateBuildSummaryPolicy``.


    .. py:method:: describe(done=False)

        :param done: If true, the step is finished.
        :returns: list of strings

        Describe the step succinctly.
        The return value should be a sequence of short strings suitable for display in a horizontally constrained space.

        .. note::

            Be careful not to assume that the step has been started in this method.
            In relatively rare circumstances, steps are described before they have started.
            Ideally, unit tests should be used to ensure that this method is resilient.

        .. note::

            This method is not called for new-style steps.
            Instead, override :py:meth:`getCurrentSummary` and :py:meth:`getResultSummary`.


    .. py:method:: addTestResultSets()

        The steps may override this to add any test result sets for this step via ``self.addTestResultSet()``.
        This function is called just before the step execution is started.
        The function is not called if the step is skipped or otherwise not run.

    .. py:method:: addTestResultSet(description, category, value_unit)

        :param description: Description of the test result set
        :param category: Category of the test result set
        :param value_unit: The value unit of the test result set
        :returns: The ID of the created test result set via a Deferred.

        Creates a new test result set to which test results can be associated.

        There are standard values of the ``category`` and ``value_unit`` parameters, see TODO.

    .. py:method:: addTestResult(setid, value, test_name=None, test_code_path=None, line=None, duration_ns=None)

        :param setid: The ID of a test result set returned by ``addTestResultSet``
        :param value: The value of the result as a string
        :param test_name: The name of the test
        :param test_code_path: The path to the code file that resulted in this test result
        :param line: The line within ``test_code_path`` file that resulted in this test result
        :param duration_ns: The duration of the test itself, in nanoseconds

        Creates a test result.
        Either ``test_name`` or ``test_code_path`` must be specified.
        The function queues the test results and will submit them to the database when enough test
        results are added so that performance impact is minimized.

    .. py:method:: finishTestResultSets()

        The steps may override this to finish submission of any test results for the step.

    Build steps have statistics, a simple key-value store of data which can later be aggregated over all steps in a build.
    Note that statistics are not preserved after a build is complete.

    .. py:method:: setBuildData(self, name, value, source)

        :param unicode name: the name of the data
        :param bytestr value: the value of the data as ``bytes``
        :param unicode source: the source of the data
        :returns: Deferred

    Builds can have transient data attached to them which allows steps to communicate to reporters and among themselves.
    The data is a byte string and its interpretation depends on the particular step or reporter.

    .. py:method:: hasStatistic(stat)

        :param string stat: name of the statistic
        :returns: True if the statistic exists on this step

    .. py:method:: getStatistic(stat, default=None)

        :param string stat: name of the statistic
        :param default: default value if the statistic does not exist
        :returns: value of the statistic, or the default value

    .. py:method:: getStatistics()

        :returns: a dictionary of all statistics for this step

    .. py:method:: setStatistic(stat, value)

        :param string stat: name of the statistic
        :param value: value to assign to the statistic
        :returns: value of the statistic

    Build steps support progress metrics - values that increase roughly linearly during the execution of the step, and can thus be used to calculate an expected completion time for a running step.
    A metric may be a count of lines logged, tests executed, or files compiled.
    The build mechanics will take care of translating this progress information into an ETA for the user.

    .. py:method:: setProgress(metric, value)

        :param metric: the metric to update
        :type metric: string
        :param value: the new value for the metric
        :type value: integer

        Update a progress metric.
        This should be called by subclasses that can provide useful progress-tracking information.

        The specified metric name must be included in :attr:`progressMetrics`.

    The following methods are provided as utilities to subclasses.
    These methods should only be invoked after the step has started.

    .. py:method:: workerVersion(command, oldversion=None)

        :param command: command to examine
        :type command: string
        :param oldversion: return value if the worker does not specify a version
        :returns: string

        Fetch the version of the named command, as specified on the worker.
        In practice, all commands on a worker have the same version, but passing ``command`` is still useful to ensure that the command is implemented on the worker.
        If the command is not implemented on the worker, :meth:`workerVersion` will return ``None``.

        Versions take the form ``x.y`` where ``x`` and ``y`` are integers, and are compared as expected for version numbers.

        Buildbot versions older than 0.5.0 did not support version queries; in this case, :meth:`workerVersion` will return ``oldVersion``.
        Since such ancient versions of Buildbot are no longer in use, this functionality is largely vestigial.

    .. py:method:: workerVersionIsOlderThan(command, minversion)

        :param command: command to examine
        :type command: string
        :param minversion: minimum version
        :returns: boolean

        This method returns true if ``command`` is not implemented on the worker, or if it is older than ``minversion``.

    .. py:method:: checkWorkerHasCommand(command)

        :param command: command to examine
        :type command: string

        This method raise :py:class:`~buildbot.interfaces.WorkerSetupError` if ``command`` is not implemented on the worker

    .. py:method:: getWorkerName()

        :returns: string

        Get the name of the worker assigned to this step.

    Most steps exist to run commands.
    While the details of exactly how those commands are constructed are left to subclasses, the execution of those commands comes down to this method:

    .. py:method:: runCommand(command)

        :param command: :py:class:`~buildbot.process.remotecommand.RemoteCommand` instance
        :returns: Deferred

        This method connects the given command to the step's worker and runs it, returning the Deferred from :meth:`~buildbot.process.remotecommand.RemoteCommand.run`.

    The :class:`BuildStep` class provides methods to add log data to the step.
    Subclasses provide a great deal of user-configurable functionality on top of these methods.
    These methods can be called while the step is running, but not before.

    .. py:method:: addLog(name, type="s", logEncoding=None)

        :param name: log name
        :param type: log type; see :bb:rtype:`logchunk`
        :param logEncoding: the log encoding, or None to use the step or global default (see :ref:`Log-Encodings`)
        :returns: :class:`~buildbot.process.log.Log` instance via Deferred

        Add a new logfile with the given name to the step, and return the log file instance.

    .. py:method:: getLog(name)

        :param name: log name
        :raises KeyError: if there is no such log
        :returns: :class:`~buildbot.process.log.Log` instance
        :raises KeyError: if no such log is defined

        Return an existing logfile, previously added with :py:meth:`addLog`.
        Note that this return value is synchronous, and only available after :py:meth:`addLog`'s deferred has fired.

    .. py:method:: addCompleteLog(name, text)

        :param name: log name
        :param text: content of the logfile
        :returns: Deferred

        This method adds a new log and sets ``text`` as its content.
        This is often useful to add a short logfile describing activities performed on the master.
        The logfile is immediately closed, and no further data can be added.

        If the logfile's content is a bytestring, it is decoded with the step's log encoding or the global default log encoding.
        To add a logfile with a different character encoding, perform the decode operation directly and pass the resulting unicode string to this method.

    .. py:method:: addHTMLLog(name, html)

        :param name: log name
        :param html: content of the logfile
        :returns: Deferred

        Similar to :meth:`addCompleteLog`, this adds a logfile containing pre-formatted HTML, allowing more expressiveness than the text format supported by :meth:`addCompleteLog`.

    .. py:method:: addLogObserver(logname, observer)

        :param logname: log name
        :param observer: log observer instance

        Add a log observer for the named log.
        The named log need not have been added already.
        The observer will be connected when the log is added.

        See :ref:`Adding-LogObservers` for more information on log observers.

    .. py:method:: addLogWithFailure(why, logprefix='')

        :param Failure why: the failure to log
        :param logprefix: prefix for the log name
        :returns: Deferred

        Add log files displaying the given failure, named ``<logprefix>err.text`` and ``<logprefix>err.html``.

    .. py:method:: addLogWithException(why, logprefix='')

        :param Exception why: the exception to log
        :param logprefix: prefix for the log name
        :returns: Deferred

        Similar to ``addLogWithFailure``, but for an Exception instead of a Failure.

    Along with logs, build steps have an associated set of links that can be used to provide additional information for developers.
    Those links are added during the build with this method:

    .. py:method:: addURL(name, url)

        :param name: URL name
        :param url: the URL

        Add a link to the given ``url``, with the given ``name`` to displays of this step.
        This allows a step to provide links to data that is not available in the log files.

CommandMixin
------------

The :py:meth:`~buildbot.process.buildstep.BuildStep.runCommand` method can run a :py:class:`~buildbot.process.remotecommand.RemoteCommand` instance, but it's no help in building that object or interpreting the results afterward.
This mixin class adds some useful methods for running commands.

This class can only be used in new-style steps.

.. py:class:: buildbot.process.buildstep.CommandMixin

    Some remote commands are simple enough that they can boil down to a method call.
    Most of these take an ``abandonOnFailure`` argument which, if true, will abandon the entire buildstep on command failure.
    This is accomplished by raising :py:exc:`~buildbot.process.buildstep.BuildStepFailed`.

    These methods all write to the ``stdio`` log (generally just for errors).
    They do not close the log when finished.

    .. py:method:: runRmdir(dir, abandonOnFailure=True)

        :param dir: directory to remove
        :param abndonOnFailure: if true, abandon step on failure
        :returns: Boolean via Deferred

        Remove the given directory, using the ``rmdir`` command.
        Returns False on failure.

    .. py:method:: runMkdir(dir, abandonOnFailure=True)

        :param dir: directory to create
        :param abndonOnFailure: if true, abandon step on failure
        :returns: Boolean via Deferred

        Create the given directory and any parent directories, using the ``mkdir`` command.
        Returns False on failure.

    .. py:method:: pathExists(path)

        :param path: path to test
        :returns: Boolean via Deferred

        Determine if the given path exists on the worker (in any form - file, directory, or otherwise).
        This uses the ``stat`` command.

    .. py:method:: runGlob(path)

        :param path: path to test
        :returns: list of filenames

        Get the list of files matching the given path pattern on the worker.
        This uses Python's ``glob`` module.
        If the ``runGlob`` method fails, it aborts the step.

    .. py:method:: getFileContentFromWorker(path, abandonOnFailure=False)

        :param path: path of the file to download from worker
        :returns: string via deferred (content of the file)

        Get the content of a file on the worker.


ShellMixin
----------

Most Buildbot steps run shell commands on the worker, and Buildbot has an impressive array of configuration parameters to control that execution.
The ``ShellMixin`` mixin provides the tools to make running shell commands easy and flexible.

This class can only be used in new-style steps.

.. py:class:: buildbot.process.buildstep.ShellMixin

    This mixin manages the following step configuration parameters, the contents of which are documented in the manual.
    Naturally, all of these are renderable.

    .. py:attribute:: command
    .. py:attribute:: workdir
    .. py:attribute:: env
    .. py:attribute:: want_stdout
    .. py:attribute:: want_stderr
    .. py:attribute:: usePTY
    .. py:attribute:: logfiles
    .. py:attribute:: lazylogfiles
    .. py:attribute:: timeout
    .. py:attribute:: maxTime
    .. py:attribute:: logEnviron
    .. py:attribute:: interruptSignal
    .. py:attribute:: sigtermTime
    .. py:attribute:: initialStdin
    .. py:attribute:: decodeRC

    .. py:method:: setupShellMixin(constructorArgs, prohibitArgs=[])

        :param dict constructorArgs: constructor keyword arguments
        :param list prohibitArgs: list of recognized arguments to reject
        :returns: keyword arguments destined for :py:class:`BuildStep`

        This method is intended to be called from the shell constructor, and be passed any keyword arguments not otherwise used by the step.
        Any attributes set on the instance already (e.g., class-level attributes) are used as defaults.
        Attributes named in ``prohibitArgs`` are rejected with a configuration error.

        The return value should be passed to the :py:class:`BuildStep` constructor.

    .. py:method:: makeRemoteShellCommand(collectStdout=False, collectStderr=False, **overrides)

        :param collectStdout: if true, the command's stdout will be available in ``cmd.stdout`` on completion
        :param collectStderr: if true, the command's stderr will be available in ``cmd.stderr`` on completion
        :param overrides: overrides arguments that might have been passed to :py:meth:`setupShellMixin`
        :returns: :py:class:`~buildbot.process.remotecommand.RemoteShellCommand` instance via Deferred

        This method constructs a :py:class:`~buildbot.process.remotecommand.RemoteShellCommand` instance based on the instance attributes and any supplied overrides.
        It must be called while the step is running, as it examines the worker capabilities before creating the command.
        It takes care of just about everything:

         * Creating log files and associating them with the command
         * Merging environment configuration
         * Selecting the appropriate workdir configuration

        All that remains is to run the command with :py:meth:`~buildbot.process.buildstep.BuildStep.runCommand`.

    The :py:class:`ShellMixin` class implements :py:meth:`~buildbot.process.buildstep.BuildStep.getResultSummary`, returning a summary of the command.
    If no command was specified or run, it falls back to the default ``getResultSummary`` based on ``descriptionDone``.
    Subclasses can override this method to return a more appropriate status.

Exceptions
----------

.. py:exception:: BuildStepFailed

    This exception indicates that the buildstep has failed.
    It is useful as a way to skip all subsequent processing when a step goes wrong.
