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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2013 Cray Inc.

import hashlib
from unittest import mock

from twisted.trial import unittest

import buildbot.test.fake.openstack as novaclient
from buildbot import config
from buildbot import interfaces
from buildbot.process.properties import Interpolate
from buildbot.process.properties import Properties
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.worker import openstack


class TestOpenStackWorker(TestReactorMixin, unittest.TestCase):
    os_auth = {
        "os_username": 'user',
        "os_password": 'pass',
        "os_tenant_name": 'tenant',
        "os_auth_url": 'auth',
    }

    os_auth_custom = {"token": 'openstack-token', "auth_type": 'token', "auth_url": 'auth'}

    bs_image_args = {"flavor": 1, "image": '28a65eb4-f354-4420-97dc-253b826547f7', **os_auth}

    def setUp(self):
        self.setup_test_reactor()
        self.patch(openstack, "client", novaclient)
        self.patch(openstack, "loading", novaclient)
        self.patch(openstack, "session", novaclient)
        self.patch(openstack, "NotFound", novaclient.NotFound)
        self.build = Properties(
            image=novaclient.TEST_UUIDS['image'],
            flavor=novaclient.TEST_UUIDS['flavor'],
            meta_value='value',
        )
        self.masterhash = hashlib.sha1(b'fake:/master').hexdigest()[:6]

    async def setupWorker(self, *args, **kwargs):
        worker = openstack.OpenStackLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(self, wantData=True)
        fakemaster.master = master
        worker.setServiceParent(master)
        await master.startService()
        self.addCleanup(master.stopService)
        return worker

    async def test_constructor_nonova(self):
        self.patch(openstack, "client", None)
        with self.assertRaises(config.ConfigErrors):
            await self.setupWorker('bot', 'pass', **self.bs_image_args)

    async def test_constructor_nokeystoneauth(self):
        self.patch(openstack, "loading", None)
        with self.assertRaises(config.ConfigErrors):
            await self.setupWorker('bot', 'pass', **self.bs_image_args)

    async def test_constructor_minimal(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 1)
        self.assertEqual(bs.image, '28a65eb4-f354-4420-97dc-253b826547f7')
        self.assertEqual(bs.block_devices, None)
        self.assertIsInstance(bs.novaclient, novaclient.Client)

    async def test_builds_may_be_incompatible(self):
        # Minimal set of parameters
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        self.assertEqual(bs.builds_may_be_incompatible, True)

    async def test_constructor_minimal_keystone_v3(self):
        bs = await self.setupWorker(
            'bot',
            'pass',
            os_user_domain='test_oud',
            os_project_domain='test_opd',
            **self.bs_image_args,
        )
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 1)
        self.assertEqual(bs.image, '28a65eb4-f354-4420-97dc-253b826547f7')
        self.assertEqual(bs.block_devices, None)
        self.assertIsInstance(bs.novaclient, novaclient.Client)
        self.assertEqual(bs.novaclient.session.auth.user_domain_name, 'test_oud')
        self.assertEqual(bs.novaclient.session.auth.project_domain_name, 'test_opd')

    async def test_constructor_token_keystone_v3(self):
        bs = await self.setupWorker(
            'bot', 'pass', os_auth_args=self.os_auth_custom, **self.bs_image_args
        )
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.flavor, 1)
        self.assertEqual(bs.image, '28a65eb4-f354-4420-97dc-253b826547f7')
        self.assertEqual(bs.block_devices, None)
        self.assertIsInstance(bs.novaclient, novaclient.Client)
        self.assertEqual(bs.novaclient.session.auth.user_domain_name, 'token')
        self.assertEqual(bs.novaclient.session.auth.project_domain_name, 'token')

    async def test_constructor_region(self):
        bs = await self.setupWorker('bot', 'pass', region="test-region", **self.bs_image_args)
        self.assertEqual(bs.novaclient.client.region_name, "test-region")

    async def test_constructor_block_devices_default(self):
        block_devices = [{'uuid': 'uuid', 'volume_size': 10}]
        bs = await self.setupWorker(
            'bot', 'pass', flavor=1, block_devices=block_devices, **self.os_auth
        )
        self.assertEqual(bs.image, None)
        self.assertEqual(len(bs.block_devices), 1)
        self.assertEqual(
            bs.block_devices,
            [
                {
                    'boot_index': 0,
                    'delete_on_termination': True,
                    'destination_type': 'volume',
                    'device_name': 'vda',
                    'source_type': 'image',
                    'volume_size': 10,
                    'uuid': 'uuid',
                }
            ],
        )

    async def test_constructor_block_devices_get_sizes(self):
        block_devices = [
            {'source_type': 'image', 'uuid': novaclient.TEST_UUIDS['image']},
            {'source_type': 'image', 'uuid': novaclient.TEST_UUIDS['image'], 'volume_size': 4},
            {'source_type': 'volume', 'uuid': novaclient.TEST_UUIDS['volume']},
            {'source_type': 'snapshot', 'uuid': novaclient.TEST_UUIDS['snapshot']},
        ]

        def check_volume_sizes(_images, _flavors, block_devices, nova_args, metas):
            self.assertEqual(len(block_devices), 4)
            self.assertEqual(block_devices[0]['volume_size'], 1)
            self.assertIsInstance(
                block_devices[0]['volume_size'], int, "Volume size is an integer."
            )
            self.assertEqual(block_devices[1]['volume_size'], 4)
            self.assertEqual(block_devices[2]['volume_size'], 4)
            self.assertEqual(block_devices[3]['volume_size'], 2)

        lw = await self.setupWorker(
            'bot', 'pass', flavor=1, block_devices=block_devices, **self.os_auth
        )
        self.assertEqual(lw.image, None)
        self.assertEqual(
            lw.block_devices,
            [
                {
                    'boot_index': 0,
                    'delete_on_termination': True,
                    'destination_type': 'volume',
                    'device_name': 'vda',
                    'source_type': 'image',
                    'volume_size': None,
                    'uuid': novaclient.TEST_UUIDS['image'],
                },
                {
                    'boot_index': 0,
                    'delete_on_termination': True,
                    'destination_type': 'volume',
                    'device_name': 'vda',
                    'source_type': 'image',
                    'volume_size': 4,
                    'uuid': novaclient.TEST_UUIDS['image'],
                },
                {
                    'boot_index': 0,
                    'delete_on_termination': True,
                    'destination_type': 'volume',
                    'device_name': 'vda',
                    'source_type': 'volume',
                    'volume_size': None,
                    'uuid': novaclient.TEST_UUIDS['volume'],
                },
                {
                    'boot_index': 0,
                    'delete_on_termination': True,
                    'destination_type': 'volume',
                    'device_name': 'vda',
                    'source_type': 'snapshot',
                    'volume_size': None,
                    'uuid': novaclient.TEST_UUIDS['snapshot'],
                },
            ],
        )
        self.patch(lw, "_start_instance", check_volume_sizes)
        await lw.start_instance(self.build)

    async def test_constructor_block_devices_missing(self):
        block_devices = [
            {'source_type': 'image', 'uuid': 'image-uuid'},
        ]

        lw = await self.setupWorker(
            'bot', 'pass', flavor=1, block_devices=block_devices, **self.os_auth
        )
        await self.assertFailure(lw.start_instance(self.build), novaclient.NotFound)

    async def test_constructor_no_image(self):
        """
        Must have one of image or block_devices specified.
        """
        with self.assertRaises(ValueError):
            await self.setupWorker('bot', 'pass', flavor=1, **self.os_auth)

    async def test_getImage_string(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        image_uuid = await bs._getImage(self.build)
        self.assertEqual('28a65eb4-f354-4420-97dc-253b826547f7', image_uuid)

    async def test_getImage_renderable(self):
        bs = await self.setupWorker(
            'bot', 'pass', flavor=1, image=Interpolate('%(prop:image)s'), **self.os_auth
        )
        image_uuid = await bs._getImage(self.build)
        self.assertEqual(novaclient.TEST_UUIDS['image'], image_uuid)

    async def test_getImage_name(self):
        bs = await self.setupWorker('bot', 'pass', flavor=1, image='CirrOS 0.3.4', **self.os_auth)
        image_uuid = await bs._getImage(self.build)
        self.assertEqual(novaclient.TEST_UUIDS['image'], image_uuid)

    async def test_getFlavor_string(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        flavor_uuid = await bs._getFlavor(self.build)
        self.assertEqual(1, flavor_uuid)

    async def test_getFlavor_renderable(self):
        bs = await self.setupWorker(
            'bot', 'pass', image="1", flavor=Interpolate('%(prop:flavor)s'), **self.os_auth
        )
        flavor_uuid = await bs._getFlavor(self.build)
        self.assertEqual(novaclient.TEST_UUIDS['flavor'], flavor_uuid)

    async def test_getFlavor_name(self):
        bs = await self.setupWorker('bot', 'pass', image="1", flavor='m1.small', **self.os_auth)
        flavor_uuid = await bs._getFlavor(self.build)
        self.assertEqual(novaclient.TEST_UUIDS['flavor'], flavor_uuid)

    async def test_start_instance_already_exists(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs.instance = mock.Mock()
        await self.assertFailure(bs.start_instance(self.build), ValueError)

    async def test_start_instance_first_fetch_fail(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        self.patch(novaclient.Servers, 'gets_until_disappears', 0)
        await self.assertFailure(
            bs.start_instance(self.build), interfaces.LatentWorkerFailedToSubstantiate
        )

    async def test_start_instance_fail_to_find(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_get', True)
        await self.assertFailure(
            bs.start_instance(self.build), interfaces.LatentWorkerFailedToSubstantiate
        )

    async def test_start_instance_fail_to_start(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        self.patch(novaclient.Servers, 'fail_to_start', True)
        await self.assertFailure(
            bs.start_instance(self.build), interfaces.LatentWorkerFailedToSubstantiate
        )

    async def test_start_instance_success(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = await bs.start_instance(self.build)
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, '28a65eb4-f354-4420-97dc-253b826547f7')
        self.assertTrue(time_waiting)

    async def test_start_instance_check_meta(self):
        meta_arg = {'some_key': 'some-value', 'BUILDBOT:instance': self.masterhash}
        bs = await self.setupWorker('bot', 'pass', meta=meta_arg, **self.bs_image_args)
        bs._poll_resolution = 0
        await bs.start_instance(self.build)
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertEqual(bs.instance.metadata, meta_arg)

    async def test_start_instance_check_meta_renderable(self):
        meta_arg = {'some_key': Interpolate('%(prop:meta_value)s')}
        bs = await self.setupWorker('bot', 'pass', meta=meta_arg, **self.bs_image_args)
        bs._poll_resolution = 0
        await bs.start_instance(self.build)
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertEqual(
            bs.instance.metadata, {'some_key': 'value', 'BUILDBOT:instance': self.masterhash}
        )

    async def test_start_instance_check_nova_args(self):
        nova_args = {'some-key': 'some-value'}

        bs = await self.setupWorker('bot', 'pass', nova_args=nova_args, **self.bs_image_args)
        bs._poll_resolution = 0
        await bs.start_instance(self.build)
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertEqual(bs.instance.boot_kwargs['some-key'], 'some-value')

    async def test_start_instance_check_nova_args_renderable(self):
        nova_args = {'some-key': Interpolate('%(prop:meta_value)s')}

        bs = await self.setupWorker('bot', 'pass', nova_args=nova_args, **self.bs_image_args)
        bs._poll_resolution = 0
        await bs.start_instance(self.build)
        self.assertIn('meta', bs.instance.boot_kwargs)
        self.assertEqual(bs.instance.boot_kwargs['some-key'], 'value')

    async def test_interpolate_renderables_for_new_build(self):
        build1 = Properties(image=novaclient.TEST_UUIDS['image'], block_device="some-device")
        build2 = Properties(image="build2-image")
        block_devices = [{'uuid': Interpolate('%(prop:block_device)s'), 'volume_size': 10}]
        bs = await self.setupWorker(
            'bot', 'pass', block_devices=block_devices, **self.bs_image_args
        )
        bs._poll_resolution = 0
        await bs.start_instance(build1)
        await bs.stop_instance(build1)
        self.assertTrue((yield bs.isCompatibleWithBuild(build2)))

    async def test_reject_incompatible_build_while_running(self):
        build1 = Properties(image=novaclient.TEST_UUIDS['image'], block_device="some-device")
        build2 = Properties(image="build2-image")
        block_devices = [{'uuid': Interpolate('%(prop:block_device)s'), 'volume_size': 10}]
        bs = await self.setupWorker(
            'bot', 'pass', block_devices=block_devices, **self.bs_image_args
        )
        bs._poll_resolution = 0
        await bs.start_instance(build1)
        self.assertFalse((yield bs.isCompatibleWithBuild(build2)))

    async def test_stop_instance_cleanup(self):
        """
        Test cleaning up leftover instances before starting new.
        """
        self.patch(novaclient.Servers, 'fail_to_get', False)
        self.patch(novaclient.Servers, 'gets_until_disappears', 9)
        novaclient.Servers().create(
            ['bot', novaclient.TEST_UUIDS['image'], novaclient.TEST_UUIDS['flavor']],
            meta={'BUILDBOT:instance': self.masterhash},
        )
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs._poll_resolution = 0
        uuid, image_uuid, time_waiting = await bs.start_instance(self.build)
        self.assertTrue(uuid)
        self.assertEqual(image_uuid, '28a65eb4-f354-4420-97dc-253b826547f7')
        self.assertTrue(time_waiting)

    async def test_stop_instance_not_set(self):
        """
        Test stopping the instance but with no instance to stop.
        """
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        bs.instance = None
        stopped = await bs.stop_instance()
        self.assertEqual(stopped, None)

    async def test_stop_instance_missing(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        instance = mock.Mock()
        instance.id = 'uuid'
        bs.instance = instance
        # TODO: Check log for instance not found.
        bs.stop_instance()

    async def test_stop_instance_fast(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        self.assertIn(inst.id, s.instances)
        bs.stop_instance(fast=True)
        self.assertNotIn(inst.id, s.instances)

    async def test_stop_instance_notfast(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        self.assertIn(inst.id, s.instances)
        bs.stop_instance(fast=False)
        self.assertNotIn(inst.id, s.instances)

    async def test_stop_instance_unknown(self):
        bs = await self.setupWorker('bot', 'pass', **self.bs_image_args)
        # Make instance immediately active.
        self.patch(novaclient.Servers, 'gets_until_active', 0)
        s = novaclient.Servers()
        bs.instance = inst = s.create()
        # Set status to DELETED. Instance should not be deleted when shutting
        # down as it already is.
        inst.status = novaclient.DELETED
        self.assertIn(inst.id, s.instances)
        bs.stop_instance()
        self.assertIn(inst.id, s.instances)
