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

from twisted.trial import unittest

from buildbot.db import projects
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces


def project_key(builder):
    return builder.id


class Tests(interfaces.InterfaceTests):
    def test_signature_find_project_id(self):
        @self.assertArgSpecMatches(self.db.projects.find_project_id)
        def find_project_id(self, name, auto_create=True):
            pass

    def test_signature_get_project(self):
        @self.assertArgSpecMatches(self.db.projects.get_project)
        def get_project(self, projectid):
            pass

    def test_signature_get_projects(self):
        @self.assertArgSpecMatches(self.db.projects.get_projects)
        def get_projects(self):
            pass

    def test_signature_update_project_info(self):
        @self.assertArgSpecMatches(self.db.projects.update_project_info)
        def update_project_info(
            self,
            projectid,
            slug,
            description,
            description_format,
            description_html,
        ):
            pass

    async def test_update_project_info(self):
        await self.insert_test_data([
            fakedb.Project(id=7, name='fake_project7'),
        ])

        await self.db.projects.update_project_info(
            7, "slug7", "project7 desc", "format", "html desc"
        )
        dbdict = await self.db.projects.get_project(7)
        self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=7,
                name="fake_project7",
                slug="slug7",
                description="project7 desc",
                description_format="format",
                description_html="html desc",
            ),
        )

    async def test_find_project_id_new(self):
        id = await self.db.projects.find_project_id('fake_project')
        dbdict = await self.db.projects.get_project(id)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=id,
                name="fake_project",
                slug="fake_project",
                description=None,
                description_format=None,
                description_html=None,
            ),
        )

    async def test_find_project_id_new_no_auto_create(self):
        id = await self.db.projects.find_project_id('fake_project', auto_create=False)
        self.assertIsNone(id)

    async def test_find_project_id_exists(self):
        await self.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        id = await self.db.projects.find_project_id('fake_project')
        self.assertEqual(id, 7)

    async def test_get_project(self):
        await self.insert_test_data([
            fakedb.Project(id=7, name='fake_project'),
        ])
        dbdict = await self.db.projects.get_project(7)
        self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dbdict,
            projects.ProjectModel(
                id=7,
                name="fake_project",
                slug="fake_project",
                description=None,
                description_format=None,
                description_html=None,
            ),
        )

    async def test_get_project_missing(self):
        dbdict = await self.db.projects.get_project(7)
        self.assertIsNone(dbdict)

    async def test_get_projects(self):
        await self.insert_test_data([
            fakedb.Project(id=7, name="fake_project7"),
            fakedb.Project(id=8, name="fake_project8"),
            fakedb.Project(id=9, name="fake_project9"),
        ])
        dblist = await self.db.projects.get_projects()
        for dbdict in dblist:
            self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            sorted(dblist, key=project_key),
            sorted(
                [
                    projects.ProjectModel(
                        id=7,
                        name="fake_project7",
                        slug="fake_project7",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                    projects.ProjectModel(
                        id=8,
                        name="fake_project8",
                        slug="fake_project8",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                    projects.ProjectModel(
                        id=9,
                        name="fake_project9",
                        slug="fake_project9",
                        description=None,
                        description_format=None,
                        description_html=None,
                    ),
                ],
                key=project_key,
            ),
        )

    async def test_get_projects_empty(self):
        dblist = await self.db.projects.get_projects()
        self.assertEqual(dblist, [])

    async def test_get_active_projects(self):
        await self.insert_test_data([
            fakedb.Project(id=1, name='fake_project1'),
            fakedb.Project(id=2, name='fake_project2'),
            fakedb.Project(id=3, name='fake_project3'),
            fakedb.Master(id=100),
            fakedb.Builder(id=200, name="builder_200", projectid=2),
            fakedb.Builder(id=201, name="builder_201", projectid=3),
            fakedb.BuilderMaster(id=300, builderid=200, masterid=100),
        ])
        dblist = await self.db.projects.get_active_projects()
        for dbdict in dblist:
            self.assertIsInstance(dbdict, projects.ProjectModel)
        self.assertEqual(
            dblist,
            [
                projects.ProjectModel(
                    id=2,
                    name="fake_project2",
                    slug="fake_project2",
                    description=None,
                    description_format=None,
                    description_html=None,
                )
            ],
        )


class RealTests(Tests):
    # tests that only "real" implementations will pass

    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    async def setUp(self):
        await self.setUpConnectorComponent()


class TestRealDB(unittest.TestCase, connector_component.ConnectorComponentMixin, RealTests):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=["projects", "builders", "masters", "builder_masters"]
        )

        self.db.projects = projects.ProjectsConnectorComponent(self.db)
        self.master = self.db.master
        self.master.db = self.db

    def tearDown(self):
        return self.tearDownConnectorComponent()
