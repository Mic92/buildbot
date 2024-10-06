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

from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import httpclientservice
from buildbot.util import service


class myTestedService(service.BuildbotService):
    name = 'myTestedService'

    def reconfigService(self, baseurl):
        self._http = httpclientservice.HTTPSession(self.master.httpservice, baseurl)

    async def doGetRoot(self):
        res = await self._http.get("/")
        # note that at this point, only the http response headers are received
        if res.code != 200:
            raise RuntimeError(f"{res.code}: server did not succeed")
        res_json = await res.json()
        # res.json() returns a deferred to represent the time needed to fetch the entire body
        return res_json


class Test(unittest.TestCase, TestReactorMixin):
    async def setUp(self):
        await self.setup_test_reactor()

        baseurl = 'http://127.0.0.1:8080'
        master = fakemaster.make_master(self)

        self._http = await fakehttpclientservice.HTTPClientService.getService(master, self, baseurl)
        self.tested = myTestedService(baseurl)

        await self.tested.setServiceParent(master)
        await master.startService()

    async def test_root(self):
        self._http.expect("get", "/", content_json={'foo': 'bar'})

        response = await self.tested.doGetRoot()
        self.assertEqual(response, {'foo': 'bar'})

    async def test_root_error(self):
        self._http.expect("get", "/", content_json={'foo': 'bar'}, code=404)

        try:
            await self.tested.doGetRoot()
        except Exception as e:
            self.assertEqual(str(e), '404: server did not succeed')
