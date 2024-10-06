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

from twisted.trial import unittest

from buildbot.db import builders
from buildbot.db import tags
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces


def builderKey(builder: builders.Builder):
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
        def getBuilders(self, masterid=None, projectid=None):
            pass

    def test_signature_updateBuilderInfo(self):
        @self.assertArgSpecMatches(self.db.builders.updateBuilderInfo)
        def updateBuilderInfo(
            self, builderid, description, description_format, description_html, projectid, tags
        ):
            pass

    async def test_updateBuilderInfo(self):
        await self.insert_test_data([
            fakedb.Project(id=123, name="fake_project123"),
            fakedb.Project(id=124, name="fake_project124"),
            fakedb.Builder(id=7, name='some:builder7'),
            fakedb.Builder(id=8, name='some:builder8'),
        ])

        await self.db.builders.updateBuilderInfo(
            7, 'a string which describe the builder', None, None, 123, ['cat1', 'cat2']
        )
        await self.db.builders.updateBuilderInfo(
            8, 'a string which describe the builder', None, None, 124, []
        )
        builderdict7 = await self.db.builders.getBuilder(7)
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

        builderdict8 = await self.db.builders.getBuilder(8)
        self.assertEqual(
            builderdict8,
            builders.BuilderModel(
                id=8,
                name='some:builder8',
                description="a string which describe the builder",
                projectid=124,
            ),
        )

    async def test_update_builder_info_tags_case(self):
        await self.insert_test_data([
            fakedb.Project(id=107, name='fake_project'),
            fakedb.Builder(id=7, name='some:builder7', projectid=107),
        ])

        await self.db.builders.updateBuilderInfo(7, 'builder_desc', None, None, 107, ['Cat', 'cat'])
        builder_dict = await self.db.builders.getBuilder(7)
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

    async def test_findBuilderId_new(self):
        id = await self.db.builders.findBuilderId('some:builder')
        builderdict = await self.db.builders.getBuilder(id)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=id,
                name='some:builder',
            ),
        )

    async def test_findBuilderId_new_no_autoCreate(self):
        id = await self.db.builders.findBuilderId('some:builder', autoCreate=False)
        self.assertIsNone(id)

    async def test_findBuilderId_exists(self):
        await self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
        ])
        id = await self.db.builders.findBuilderId('some:builder')
        self.assertEqual(id, 7)

    async def test_addBuilderMaster(self):
        await self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        await self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[9, 10],
            ),
        )

    async def test_addBuilderMaster_already_present(self):
        await self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='abc'),
            fakedb.Master(id=10, name='def'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
        ])
        await self.db.builders.addBuilderMaster(builderid=7, masterid=9)
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[9],
            ),
        )

    async def test_removeBuilderMaster(self):
        await self.insert_test_data([
            fakedb.Builder(id=7),
            fakedb.Master(id=9, name='some:master'),
            fakedb.Master(id=10, name='other:master'),
            fakedb.BuilderMaster(builderid=7, masterid=9),
            fakedb.BuilderMaster(builderid=7, masterid=10),
        ])
        await self.db.builders.removeBuilderMaster(builderid=7, masterid=9)
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[10],
            ),
        )

    async def test_getBuilder_no_masters(self):
        await self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
        ])
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
            ),
        )

    async def test_getBuilder_with_masters(self):
        await self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=7, masterid=4),
        ])
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(
            builderdict,
            builders.BuilderModel(
                id=7,
                name='some:builder',
                masterids=[3, 4],
            ),
        )

    async def test_getBuilder_missing(self):
        builderdict = await self.db.builders.getBuilder(7)
        self.assertEqual(builderdict, None)

    async def test_getBuilders(self):
        await self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Builder(id=8, name='other:builder'),
            fakedb.Builder(id=9, name='third:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = await self.db.builders.getBuilders()
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

    async def test_getBuilders_masterid(self):
        await self.insert_test_data([
            fakedb.Builder(id=7, name='some:builder'),
            fakedb.Builder(id=8, name='other:builder'),
            fakedb.Builder(id=9, name='third:builder'),
            fakedb.Master(id=3, name='m1'),
            fakedb.Master(id=4, name='m2'),
            fakedb.BuilderMaster(builderid=7, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=3),
            fakedb.BuilderMaster(builderid=8, masterid=4),
        ])
        builderlist = await self.db.builders.getBuilders(masterid=3)
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

    async def test_getBuilders_projectid(self):
        await self.insert_test_data([
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
        builderlist = await self.db.builders.getBuilders(projectid=201)
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

    async def test_getBuilders_empty(self):
        builderlist = await self.db.builders.getBuilders()
        self.assertEqual(sorted(builderlist), [])


class RealTests(Tests):
    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    async def setUp(self):
        await self.setUpConnectorComponent()


class TestRealDB(unittest.TestCase, connector_component.ConnectorComponentMixin, RealTests):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=[
                'projects',
                'builders',
                'masters',
                'builder_masters',
                'builders_tags',
                'tags',
            ]
        )

        self.db.builders = builders.BuildersConnectorComponent(self.db)
        self.db.tags = tags.TagsConnectorComponent(self.db)
        self.master = self.db.master
        self.master.db = self.db

    def tearDown(self):
        return self.tearDownConnectorComponent()
