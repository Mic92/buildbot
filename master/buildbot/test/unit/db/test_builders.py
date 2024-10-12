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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db import builders
from buildbot.db import tags
from buildbot.db import workers
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.util.twisted import async_to_deferred


def builderKey(builder: builders.BuilderModel) -> int:
    return builder.id


class Tests(interfaces.InterfaceTests):
    # common sample data

    builder_row = [
        fakedb.Builder(id=7, name="some:builder"),
    ]

    # tests

    def test_signature_findBuilderId(self):
        @self.assertArgSpecMatches(self.db.builders.findBuilderId)
        def findBuilderId(self, name, autoCreate=True):
            pass

    def test_signature_addBuilderMaster(self):
        @self.assertArgSpecMatches(self.db.builders.addBuilderMaster)
        def addBuilderMaster(self, builderid=None, masterid=None):
            pass

    def test_signature_removeBuilderMaster(self):
        @self.assertArgSpecMatches(self.db.builders.removeBuilderMaster)
        def removeBuilderMaster(self, builderid=None, masterid=None):
            pass

    def test_signature_getBuilder(self):
        @self.assertArgSpecMatches(self.db.builders.getBuilder)
        def getBuilder(self, builderid):
            pass

    def test_signature_getBuilders(self):
        @self.assertArgSpecMatches(self.db.builders.getBuilders)
        def getBuilders(self, masterid=None, projectid=None, workerid=None):
            pass

    def test_signature_updateBuilderInfo(self):
        @self.assertArgSpecMatches(self.db.builders.updateBuilderInfo)
        def updateBuilderInfo(
            self, builderid, description, description_format, description_html, projectid, tags
        ):
            pass

    @defer.inlineCallbacks
    def test_updateBuilderInfo(self):
        yield self.insert_test_data([
            fakedb.Project(id=123, name="fake_project123"),
            fakedb.Project(id=124, name="fake_project124"),
            fakedb.Builder(id=7, name='some:builder7'),
            fakedb.Builder(id=8, name='some:builder8'),
        ])

        yield self.db.builders.updateBuilderInfo(
            7, 'a string which describe the builder', None, None, 123, ['cat1', 'cat2']
        )
        yield self.db.builders.updateBuilderInfo(
            8, 'a string which describe the builder', None, None, 124, []
        )
        builderdict7 = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict7,
            builders.BuilderModel(
                id=7,
                name='some:builder7',
                tags=["cat1", "cat2"],
                description="a string which describe the builder",
                projectid=123,
            ),
        )

        builderdict8 = yield self.db.builders.getBuilder(8)
        self.assertEqual(
            builderdict8,
            builders.BuilderModel(
                id=8,
                name='some:builder8',
                description="a string which describe the builder",
                projectid=124,
            ),
        )

    @defer.inlineCallbacks
    def test_update_builder_info_tags_case(self):
        yield self.insert_test_data([
            fakedb.Project(id=107, name='fake_project'),
            fakedb.Builder(id=7, name='some:builder7', projectid=107),
        ])

        yield self.db.builders.updateBuilderInfo(7, 'builder_desc', None, None, 107, ['Cat', 'cat'])
        builder_dict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builder_dict,
            builders.BuilderModel(
                id=7,
                name='some:builder7',
                tags=['Cat', 'cat'],
                description='builder_desc',
                projectid=107,
            ),
        )

    @defer.inlineCallbacks
    def test_findBuilderId_new(self):
        id = yield self.db.builders.findBuilderId('some:builder')
        builderdict = yield self.db.builders.getBuilder(id)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=id,
                name='some:builder',
            ),
        )

    @defer.inlineCallbacks
    def test_findBuilderId_new_no_autoCreate(self):
        id = yield self.db.builders.findBuilderId('some:builder', autoCreate=False)
        self.assertIsNone(id)

    @defer.inlineCallbacks
    def test_findBuilderId_exists(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
        ])
        id = yield self.db.builders.findBuilderId('some:builder')
        self.assertEqual(id, 7)

    @defer.inlineCallbacks
    def test_addBuilderMaster(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        yield self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[9, 10],
            ),
        )

    @defer.inlineCallbacks
    def test_addBuilderMaster_already_present(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
        ])
        yield self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[9],
            ),
        )

    @defer.inlineCallbacks
    def test_removeBuilderMaster(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='some:master'),
            fakedb.Master(id=10, name='other:master'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        yield self.db.builders.removeBuilderMaster(builderid=7, masterid=9)
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[10],
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilder_no_masters(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
        ])
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilder_with_masters(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=7, masterid=4),
        ])
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[3, 4],
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilder_missing(self):
        builderdict = yield self.db.builders.getBuilder(7)
        self.assertEqual(builderdict, None)

    @defer.inlineCallbacks
    def test_getBuilders(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Builder(id=8, name='other:builder'),
            fakedb.Builder(id=9, name='third:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = yield self.db.builders.getBuilders()
        self.assertEqual(
            sorted(builderlist, key=builderKey),
            sorted(
                [
                    builders.BuilderModel(
                        id=7,
                        name='some:builder',
                        masterids=[3],
                    ),
                    builders.BuilderModel(
                        id=8,
                        name='other:builder',
                        masterids=[3, 4],
                    ),
                    builders.BuilderModel(
                        id=9,
                        name='third:builder',
                    ),
                ],
                key=builderKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilders_masterid(self):
        yield self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Builder(id=8, name='other:builder'),
            fakedb.Builder(id=9, name='third:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = yield self.db.builders.getBuilders(masterid=3)
        self.assertEqual(
            sorted(builderlist, key=builderKey),
            sorted(
                [
                    builders.BuilderModel(
                        id=7,
                        name='some:builder',
                        masterids=[3],
                    ),
                    builders.BuilderModel(
                        id=8,
                        name='other:builder',
                        masterids=[3, 4],
                    ),
                ],
                key=builderKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilders_projectid(self):
        yield self.insert_test_data([
            fakedb.Project(id=201, name="p201"),
            fakedb.Project(id=202, name="p202"),
            fakedb.Builder(id=101, name="b101"),
            fakedb.Builder(id=102, name="b102", projectid=201),
            fakedb.Builder(id=103, name="b103", projectid=201),
            fakedb.Builder(id=104, name="b104", projectid=202),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=101, masterid=3),
            fakedb.BuilderMaster(builderid=102, masterid=3),
            fakedb.BuilderMaster(builderid=103, masterid=4),
            fakedb.BuilderMaster(builderid=104, masterid=4),
        ])
        builderlist = yield self.db.builders.getBuilders(projectid=201)
        self.assertEqual(
            sorted(builderlist, key=builderKey),
            sorted(
                [
                    builders.BuilderModel(
                        id=102,
                        name="b102",
                        masterids=[3],
                        projectid=201,
                    ),
                    builders.BuilderModel(
                        id=103,
                        name="b103",
                        masterids=[4],
                        projectid=201,
                    ),
                ],
                key=builderKey,
            ),
        )

    @async_to_deferred
    async def test_getBuilders_workerid(self):
        await self.insert_test_data([
            fakedb.Builder(id=101, name="b101"),
            fakedb.Builder(id=102, name="b102"),
            fakedb.Builder(id=103, name="b103"),
            fakedb.Builder(id=104, name="b104"),
            fakedb.Master(id=3, name='m1'),
            fakedb.BuilderMaster(id=1, builderid=101, masterid=3),
            fakedb.BuilderMaster(id=2, builderid=102, masterid=3),
            fakedb.BuilderMaster(id=3, builderid=103, masterid=3),
            fakedb.BuilderMaster(id=4, builderid=104, masterid=3),
            fakedb.Worker(id=1, name='zero'),
            fakedb.ConnectedWorker(id=1, workerid=1, masterid=3),
            fakedb.ConfiguredWorker(id=1, workerid=1, buildermasterid=2),
            fakedb.ConfiguredWorker(id=2, workerid=1, buildermasterid=3),
        ])
        builderlist = await self.db.builders.getBuilders(workerid=1)
        self.assertEqual(
            sorted(builderlist, key=builderKey),
            sorted(
                [
                    builders.BuilderModel(
                        id=102,
                        name="b102",
                        masterids=[3],
                    ),
                    builders.BuilderModel(
                        id=103,
                        name="b103",
                        masterids=[3],
                    ),
                ],
                key=builderKey,
            ),
        )

    @defer.inlineCallbacks
    def test_getBuilders_empty(self):
        builderlist = yield self.db.builders.getBuilders()
        self.assertEqual(sorted(builderlist), [])


class RealTests(Tests):
    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent()


class TestRealDB(unittest.TestCase, connector_component.ConnectorComponentMixin, RealTests):
    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpConnectorComponent(
            table_names=[
                'projects',
                'builders',
                'masters',
                'builder_masters',
                'builders_tags',
                'tags',
                'workers',
                'connected_workers',
                'configured_workers',
            ]
        )

        self.db.builders = builders.BuildersConnectorComponent(self.db)
        self.db.tags = tags.TagsConnectorComponent(self.db)
        self.db.workers = workers.WorkersConnectorComponent(self.db)
        self.master = self.db.master
        self.master.db = self.db

    def tearDown(self):
        return self.tearDownConnectorComponent()
