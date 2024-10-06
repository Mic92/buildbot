# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import annotations

import calendar
from typing import TYPE_CHECKING

from buildbot.data import resultspec
from buildbot.process import properties
from buildbot.process.results import SKIPPED

if TYPE_CHECKING:
    from buildbot.db.buildrequests import BuildRequestModel


class BuildRequestCollapser:
    # brids is a list of the new added buildrequests id
    # This class is called before generated the 'new' event for the
    # buildrequest

    # Before adding new buildset/buildrequests, we must examine each unclaimed
    # buildrequest.
    # EG:
    #  1. get the list of all unclaimed buildrequests:
    #     - We must exclude all buildsets which have at least 1 claimed buildrequest
    #  2. For each unclaimed buildrequests, if compatible with the new request
    #     (sourcestamps match, except for revision) Then:
    #     2.1. claim it
    #     2.2. complete it with result SKIPPED

    def __init__(self, master, brids):
        self.master = master
        self.brids = brids

    async def _getUnclaimedBrs(self, builderid):
        # Retrieve the list of Brs for all unclaimed builds
        unclaim_brs = await self.master.data.get(
            ('builders', builderid, 'buildrequests'), [resultspec.Filter('claimed', 'eq', [False])]
        )
        # sort by submitted_at, so the first is the oldest
        unclaim_brs.sort(key=lambda brd: brd['submitted_at'])
        return unclaim_brs

    async def collapse(self):
        brids_to_collapse = set()

        for brid in self.brids:
            # Get the BuildRequest object
            br = await self.master.data.get(('buildrequests', brid))
            # Retrieve the buildername
            builderid = br['builderid']
            bldrdict = await self.master.data.get(('builders', builderid))
            # Get the builder object
            bldr = self.master.botmaster.builders.get(bldrdict['name'])
            if not bldr:
                continue
            # Get the Collapse BuildRequest function (from the configuration)
            collapseRequestsFn = bldr.getCollapseRequestsFn()
            unclaim_brs = await self._getUnclaimedBrs(builderid)

            # short circuit if there is no merging to do
            if not collapseRequestsFn or not unclaim_brs:
                continue

            for unclaim_br in unclaim_brs:
                if unclaim_br['buildrequestid'] == br['buildrequestid']:
                    continue

                canCollapse = await collapseRequestsFn(self.master, bldr, br, unclaim_br)
                if canCollapse is True:
                    brids_to_collapse.add(unclaim_br['buildrequestid'])

        collapsed_brids = []
        for brid in brids_to_collapse:
            claimed = await self.master.data.updates.claimBuildRequests([brid])
            if claimed:
                await self.master.data.updates.completeBuildRequests([brid], SKIPPED)
                collapsed_brids.append(brid)

        return collapsed_brids


class TempSourceStamp:
    # temporary fake sourcestamp

    ATTRS = ('branch', 'revision', 'repository', 'project', 'codebase')

    PATCH_ATTRS = (
        ('patch_level', 'level'),
        ('patch_body', 'body'),
        ('patch_subdir', 'subdir'),
        ('patch_author', 'author'),
        ('patch_comment', 'comment'),
    )

    def __init__(self, ssdict):
        self._ssdict = ssdict

    def __getattr__(self, attr):
        patch = self._ssdict.get('patch')
        if attr == 'patch':
            if patch:
                return (patch['level'], patch['body'], patch['subdir'])
            return None
        elif attr == 'patch_info':
            if patch:
                return (patch['author'], patch['comment'])
            return (None, None)
        elif attr in self.ATTRS or attr == 'ssid':
            return self._ssdict[attr]
        raise AttributeError(attr)

    def asSSDict(self):
        return self._ssdict

    def asDict(self):
        # This return value should match the kwargs to
        # SourceStampsConnectorComponent.findSourceStampId
        result = {}
        for attr in self.ATTRS:
            result[attr] = self._ssdict.get(attr)

        patch = self._ssdict.get('patch') or {}
        for patch_attr, attr in self.PATCH_ATTRS:
            result[patch_attr] = patch.get(attr)

        assert all(
            isinstance(val, (str, int, bytes, type(None))) for attr, val in result.items()
        ), result
        return result


class TempChange:
    # temporary fake change

    def __init__(self, d):
        self._chdict = d

    def __getattr__(self, attr):
        if attr == 'who':
            return self._chdict['author']
        elif attr == 'properties':
            return properties.Properties.fromDict(self._chdict['properties'])
        return self._chdict[attr]

    def asChDict(self):
        return self._chdict


class BuildRequest:
    """

    A rolled-up encapsulation of all of the data relevant to a build request.

    This class is used by the C{nextBuild} and C{collapseRequests} configuration
    parameters, as well as in starting a build.  Construction of a BuildRequest
    object is a heavyweight process involving a lot of database queries, so
    it should be avoided where possible.  See bug #1894.

    @type reason: string
    @ivar reason: the reason this Build is being requested. Schedulers provide
    this, but for forced builds the user requesting the build will provide a
    string.  It comes from the buildsets table.

    @type properties: L{properties.Properties}
    @ivar properties: properties that should be applied to this build, taken
    from the buildset containing this build request

    @ivar submittedAt: a timestamp (seconds since epoch) when this request was
    submitted to the Builder. This is used by the CVS step to compute a
    checkout timestamp, as well as by the master to prioritize build requests
    from oldest to newest.

    @ivar buildername: name of the requested builder

    @ivar priority: request priority

    @ivar id: build request ID

    @ivar bsid: ID of the parent buildset
    """

    submittedAt = None
    sources = {}

    @classmethod
    def fromBrdict(cls, master, brdict: BuildRequestModel):
        """
        Construct a new L{BuildRequest} from a L{BuildRequestModel} as returned by
        L{BuildRequestsConnectorComponent.getBuildRequest}.

        This method uses a cache, which may result in return of stale objects;
        for the most up-to-date information, use the database connector
        methods.

        @param master: current build master
        @param brdict: build request dictionary

        @returns: L{BuildRequest}, via Deferred
        """
        cache = master.caches.get_cache("BuildRequests", cls._make_br)
        return cache.get(brdict.buildrequestid, brdict=brdict, master=master)

    @classmethod
    async def _make_br(cls, brid: int, brdict: BuildRequestModel, master):
        buildrequest = cls()
        buildrequest.id = brid
        buildrequest.bsid = brdict.buildsetid
        buildrequest.buildername = brdict.buildername
        buildrequest.builderid = brdict.builderid
        buildrequest.priority = brdict.priority
        dt = brdict.submitted_at
        buildrequest.submittedAt = dt and calendar.timegm(dt.utctimetuple())
        buildrequest.master = master
        buildrequest.waitedFor = brdict.waited_for

        # fetch the buildset to get the reason
        buildset = await master.db.buildsets.getBuildset(brdict.buildsetid)
        assert buildset  # schema should guarantee this
        buildrequest.reason = buildset.reason

        # fetch the buildset properties, and convert to Properties
        buildset_properties = await master.db.buildsets.getBuildsetProperties(brdict.buildsetid)

        buildrequest.properties = properties.Properties.fromDict(buildset_properties)

        # make a fake sources dict (temporary)
        bsdata = await master.data.get(('buildsets', str(buildrequest.bsid)))
        assert bsdata['sourcestamps'], "buildset must have at least one sourcestamp"
        buildrequest.sources = {}
        for ssdata in bsdata['sourcestamps']:
            ss = buildrequest.sources[ssdata['codebase']] = TempSourceStamp(ssdata)
            changes = await master.data.get(("sourcestamps", ss.ssid, "changes"))
            ss.changes = [TempChange(change) for change in changes]

        return buildrequest

    @staticmethod
    def filter_buildset_props_for_collapsing(bs_props):
        return {
            name: value
            for name, (value, source) in bs_props.items()
            if name != 'scheduler' and source == 'Scheduler'
        }

    @staticmethod
    async def canBeCollapsed(master, new_br, old_br):
        """
        Returns true if both buildrequest can be merged, via Deferred.

        This implements Buildbot's default collapse strategy.
        """
        # short-circuit: if these are for the same buildset, collapse away
        if new_br['buildsetid'] == old_br['buildsetid']:
            return True

        # the new buildrequest must actually be newer than the old build request, otherwise we
        # may end up with situations where two build requests submitted at the same time will
        # cancel each other.
        if new_br['buildrequestid'] < old_br['buildrequestid']:
            return False

        # get the buildsets for each buildrequest
        selfBuildsets = await master.data.get(('buildsets', str(new_br['buildsetid'])))
        otherBuildsets = await master.data.get(('buildsets', str(old_br['buildsetid'])))

        # extract sourcestamps, as dictionaries by codebase
        selfSources = dict((ss['codebase'], ss) for ss in selfBuildsets['sourcestamps'])
        otherSources = dict((ss['codebase'], ss) for ss in otherBuildsets['sourcestamps'])

        # if the sets of codebases do not match, we can't collapse
        if set(selfSources) != set(otherSources):
            return False

        for c, selfSS in selfSources.items():
            otherSS = otherSources[c]
            if selfSS['repository'] != otherSS['repository']:
                return False

            if selfSS['branch'] != otherSS['branch']:
                return False

            if selfSS['project'] != otherSS['project']:
                return False

            # anything with a patch won't be collapsed
            if selfSS['patch'] or otherSS['patch']:
                return False
            # get changes & compare
            selfChanges = await master.data.get(('sourcestamps', selfSS['ssid'], 'changes'))
            otherChanges = await master.data.get(('sourcestamps', otherSS['ssid'], 'changes'))
            # if both have changes, proceed, else fail - if no changes check revision instead
            if selfChanges and otherChanges:
                continue

            if selfChanges and not otherChanges:
                return False

            if not selfChanges and otherChanges:
                return False

            # else check revisions
            if selfSS['revision'] != otherSS['revision']:
                return False

        # don't collapse build requests if the properties injected by the scheduler differ
        new_bs_props = await master.data.get(('buildsets', str(new_br['buildsetid']), 'properties'))
        old_bs_props = await master.data.get(('buildsets', str(old_br['buildsetid']), 'properties'))

        new_bs_props = BuildRequest.filter_buildset_props_for_collapsing(new_bs_props)
        old_bs_props = BuildRequest.filter_buildset_props_for_collapsing(old_bs_props)
        if new_bs_props != old_bs_props:
            return False

        return True

    def mergeSourceStampsWith(self, others):
        """Returns one merged sourcestamp for every codebase"""
        # get all codebases from all requests
        all_codebases = set(self.sources)
        for other in others:
            all_codebases |= set(other.sources)

        all_merged_sources = {}
        # walk along the codebases
        for codebase in all_codebases:
            all_sources = []
            if codebase in self.sources:
                all_sources.append(self.sources[codebase])
            for other in others:
                if codebase in other.sources:
                    all_sources.append(other.sources[codebase])
            assert all_sources, "each codebase should have at least one sourcestamp"

            # TODO: select the sourcestamp that best represents the merge,
            # preferably the latest one.  This used to be accomplished by
            # looking at changeids and picking the highest-numbered.
            all_merged_sources[codebase] = all_sources[-1]

        return list(all_merged_sources.values())

    def mergeReasons(self, others):
        """Return a reason for the merged build request."""
        reasons = []
        for req in [self, *others]:
            if req.reason and req.reason not in reasons:
                reasons.append(req.reason)
        return ", ".join(reasons)

    def getSubmitTime(self):
        return self.submittedAt
