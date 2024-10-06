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

from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.data import workers
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

testData = [
    fakedb.Builder(id=40, name='b1'),
    fakedb.Builder(id=41, name='b2'),
    fakedb.Master(id=13),
    fakedb.Master(id=14),
    fakedb.BuilderMaster(id=4013, builderid=40, masterid=13),
    fakedb.BuilderMaster(id=4014, builderid=40, masterid=14),
    fakedb.BuilderMaster(id=4113, builderid=41, masterid=13),
    fakedb.Worker(id=1, name='linux', info={}),
    fakedb.ConfiguredWorker(id=14013, workerid=1, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=14014, workerid=1, buildermasterid=4014),
    fakedb.ConnectedWorker(id=113, masterid=13, workerid=1),
    fakedb.Worker(id=2, name='windows', info={"a": "b"}),
    fakedb.ConfiguredWorker(id=24013, workerid=2, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=24014, workerid=2, buildermasterid=4014),
    fakedb.ConfiguredWorker(id=24113, workerid=2, buildermasterid=4113),
    fakedb.ConnectedWorker(id=214, masterid=14, workerid=2),
]


def configuredOnKey(worker):
    return (worker.get('masterid', 0), worker.get('builderid', 0))


def _filt(bs, builderid, masterid):
    bs['connected_to'] = sorted([
        d for d in bs['connected_to'] if not masterid or masterid == d['masterid']
    ])
    bs['configured_on'] = sorted(
        [
            d
            for d in bs['configured_on']
            if (not masterid or masterid == d['masterid'])
            and (not builderid or builderid == d['builderid'])
        ],
        key=configuredOnKey,
    )
    return bs


def w1(builderid=None, masterid=None):
    return _filt(
        {
            'workerid': 1,
            'name': 'linux',
            'workerinfo': {},
            'paused': False,
            'graceful': False,
            "pause_reason": None,
            'connected_to': [
                {'masterid': 13},
            ],
            'configured_on': sorted(
                [
                    {'builderid': 40, 'masterid': 13},
                    {'builderid': 40, 'masterid': 14},
                ],
                key=configuredOnKey,
            ),
        },
        builderid,
        masterid,
    )


def w2(builderid=None, masterid=None):
    return _filt(
        {
            'workerid': 2,
            'name': 'windows',
            'workerinfo': {'a': 'b'},
            'paused': False,
            "pause_reason": None,
            'graceful': False,
            'connected_to': [
                {'masterid': 14},
            ],
            'configured_on': sorted(
                [
                    {'builderid': 40, 'masterid': 13},
                    {'builderid': 41, 'masterid': 13},
                    {'builderid': 40, 'masterid': 14},
                ],
                key=configuredOnKey,
            ),
        },
        builderid,
        masterid,
    )


class WorkerEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = workers.WorkerEndpoint
    resourceTypeClass = workers.Worker

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insert_test_data(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    async def test_get_existing(self):
        worker = await self.callGet(('workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2())

    async def test_get_existing_name(self):
        worker = await self.callGet(('workers', 'linux'))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w1())

    async def test_get_existing_masterid(self):
        worker = await self.callGet(('masters', 14, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(masterid=14))

    async def test_get_existing_builderid(self):
        worker = await self.callGet(('builders', 40, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(builderid=40))

    async def test_get_existing_masterid_builderid(self):
        worker = await self.callGet(('masters', 13, 'builders', 40, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(masterid=13, builderid=40))

    async def test_get_missing(self):
        worker = await self.callGet(('workers', 99))

        self.assertEqual(worker, None)

    async def test_set_worker_paused(self):
        await self.master.data.updates.set_worker_paused(2, True, "reason")
        worker = await self.callGet(('workers', 2))
        self.validateData(worker)
        self.assertEqual(worker['paused'], True)
        self.assertEqual(worker["pause_reason"], "reason")

    async def test_set_worker_graceful(self):
        await self.master.data.updates.set_worker_graceful(2, True)
        worker = await self.callGet(('workers', 2))
        self.validateData(worker)
        self.assertEqual(worker['graceful'], True)

    async def test_actions(self):
        for action in ("stop", "pause", "unpause", "kill"):
            await self.callControl(action, {}, ('masters', 13, 'builders', 40, 'workers', 2))
            self.master.mq.assertProductions([
                (('control', 'worker', '2', action), {'reason': 'no reason'})
            ])

    async def test_bad_actions(self):
        with self.assertRaises(exceptions.InvalidControlException):
            await self.callControl("bad_action", {}, ('masters', 13, 'builders', 40, 'workers', 2))


class WorkersEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = workers.WorkersEndpoint
    resourceTypeClass = workers.Worker

    def setUp(self):
        self.setUpEndpoint()
        return self.db.insert_test_data(testData)

    def tearDown(self):
        self.tearDownEndpoint()

    async def test_get(self):
        workers = await self.callGet(('workers',))

        for b in workers:
            self.validateData(b)
            b['configured_on'] = sorted(b['configured_on'], key=configuredOnKey)
        self.assertEqual(
            sorted(workers, key=configuredOnKey), sorted([w1(), w2()], key=configuredOnKey)
        )

    async def test_get_masterid(self):
        workers = await self.callGet((
            'masters',
            '13',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey),
            sorted([w1(masterid=13), w2(masterid=13)], key=configuredOnKey),
        )

    async def test_get_builderid(self):
        workers = await self.callGet((
            'builders',
            '41',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey), sorted([w2(builderid=41)], key=configuredOnKey)
        )

    async def test_get_masterid_builderid(self):
        workers = await self.callGet((
            'masters',
            '13',
            'builders',
            '41',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey),
            sorted([w2(masterid=13, builderid=41)], key=configuredOnKey),
        )

    async def test_set_worker_paused_find_by_paused(self):
        await self.master.data.updates.set_worker_paused(2, True, None)
        resultSpec = resultspec.OptimisedResultSpec(
            filters=[resultspec.Filter('paused', 'eq', [True])]
        )

        workers = await self.callGet(('workers',), resultSpec=resultSpec)
        self.assertEqual(len(workers), 1)
        worker = workers[0]
        self.validateData(worker)
        self.assertEqual(worker['paused'], True)


class Worker(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = workers.Worker(self.master)
        return self.master.db.insert_test_data([
            fakedb.Master(id=13),
            fakedb.Master(id=14),
        ])

    def test_signature_findWorkerId(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.findWorkerId,  # fake
            self.rtype.findWorkerId,
        )  # real
        def findWorkerId(self, name):
            pass

    def test_signature_workerConfigured(self):
        @self.assertArgSpecMatches(
            self.master.data.updates.workerConfigured,  # fake
            self.rtype.workerConfigured,
        )  # real
        def workerConfigured(self, workerid, masterid, builderids):
            pass

    def test_signature_set_worker_paused(self):
        @self.assertArgSpecMatches(self.master.data.updates.set_worker_paused)
        def set_worker_paused(self, workerid, paused, pause_reason=None):
            pass

    def test_signature_set_worker_graceful(self):
        @self.assertArgSpecMatches(self.master.data.updates.set_worker_graceful)
        def set_worker_graceful(self, workerid, graceful):
            pass

    def test_findWorkerId(self):
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.workers.findWorkerId = mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.findWorkerId('foo'), rv)

    def test_findWorkerId_not_id(self):
        with self.assertRaises(ValueError):
            self.rtype.findWorkerId(b'foo')
        with self.assertRaises(ValueError):
            self.rtype.findWorkerId('123/foo')
