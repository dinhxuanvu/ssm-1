#!/usr/bin/env python
#
# (C)2012 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Unittests for the system storage manager btrfs backend


import unittest
from ssmlib import main
from ssmlib.backends import btrfs
from tests.unittests.common import *

class BtrfsFunctionCheck(MockSystemDataSource):

    def setUp(self):
        super(BtrfsFunctionCheck, self).setUp()
        self._addDevice('/dev/sda', 11489037516)
        self._addDevice('/dev/sdb', 234566451)
        self._addDevice('/dev/sdc', 2684354560)
        self._addDevice('/dev/sdc1', 894784853, 1)
        self._addDevice('/dev/sdc2', 29826161, 2)
        self._addDevice('/dev/sdc3', 1042177280, 3)
        self._addDevice('/dev/sdd', 11673)
        self._addDevice('/dev/sde', 1042177280)
        main.SSM_DEFAULT_BACKEND = 'btrfs'

    def mock_run(self, cmd, *args, **kwargs):
        self.run_data.append(" ".join(cmd))
        output = ""
        if cmd[:3] == ['btrfs', 'filesystem', 'show']:
            for pool, p_data in self.pool_data.iteritems():
                output += "Label: {0} uuid: some_random_uuid\n".format(pool)
                count = 0
                d_output = ""
                for dev, d_data in sorted(self.dev_data.iteritems()):
                    if 'pool_name' not in d_data or \
                       d_data['pool_name'] != pool:
                           continue
                    count += 1
                    d_output += " devid {0} size {1}.00K used {2} path {3}\n".format(
                            count, d_data['dev_size'], d_data['dev_used'], dev)
                output += " Total devices {0} FS bytes used 44.00KB\n".format(count)
                output += d_output
        elif cmd[:3] == ['btrfs', 'subvolume', 'list']:
            mpoint = cmd[3]
            for pool, p_data in self.pool_data.iteritems():
                if 'mount' not in p_data or p_data['mount'] != mpoint:
                    continue
                count = 0
                for vol, v_data in self.vol_data.iteritems():
                    if v_data['pool_name'] != pool:
                        continue
                    count += 1
                    output += "ID {0} top level 5 path {1}\n".format(count,
                              v_data['dev_name'])
        if 'return_stdout' in kwargs and not kwargs['return_stdout']:
            output = None
        return (0, output)

    def test_btrfs_create(self):
        default_pool = btrfs.SSM_BTRFS_DEFAULT_POOL

        # Create volume using single device from non existent default pool
        self._checkCmd("ssm create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -f create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -v create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm -f -v create", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))

        self._checkCmd("ssm create", ['-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L {0} -b 2858730232217 /dev/sda".format(default_pool))

        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 1', '-s 512k', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid1 -d raid1 -b 524288 /dev/sda".format(default_pool))
        self._checkCmd("ssm create", ['-r 10', '-s 10M', '/dev/sda'],
            "mkfs.btrfs -L btrfs_pool -m raid10 -d raid10 -b 10485760 /dev/sda".format(default_pool))

        # Create volume using single device from non existent my_pool
        self._checkCmd("ssm create", ['--pool my_pool', '/dev/sda'],
            "mkfs.btrfs -L my_pool /dev/sda")

        self._checkCmd("ssm create", ['-p my_pool', '-r 0', '-s 2.6T', '/dev/sda'],
            "mkfs.btrfs -L my_pool -m raid0 -d raid0 -b 2858730232217 /dev/sda")

        # Create volume using multiple devices
        self._checkCmd("ssm create /dev/sda /dev/sdb", [],
            "mkfs.btrfs -L {0} /dev/sda /dev/sdb".format(default_pool))

        # Create volume using single device from existing pool
        self._addPool(default_pool, ['/dev/sdb', '/dev/sdd'])
        self._addPool("my_pool", ['/dev/sdc2', '/dev/sdc3'])
        self._checkCmd("ssm create", ['-n myvolume'],
            "btrfs subvolume create /tmp/mount/myvolume")

        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume'],
            "btrfs subvolume create /tmp/mount/myvolume")

        self._addVol('vol002', 1172832, 1, 'my_pool', ['/dev/sdc2'], '/mnt/test')
        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume'],
            "btrfs subvolume create /mnt/test/myvolume")

        # Create volume using multiple devices which one of the is in already
        # in the pool
        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb'],
            "btrfs subvolume create /tmp/mount/myvolume")
        self._cmdEq("btrfs device add /dev/sda /tmp/mount", -2)

        self._checkCmd("ssm create", ['-p my_pool', '-n myvolume', '/dev/sdc2 /dev/sda'],
            "btrfs subvolume create /mnt/test/myvolume")
        self._cmdEq("btrfs device add /dev/sda /mnt/test", -2)

        self._checkCmd("ssm create", ['-n myvolume', '/dev/sda /dev/sdb /dev/sde'],
            "btrfs subvolume create /tmp/mount/myvolume")
        self._cmdEq("btrfs device add /dev/sda /dev/sde /tmp/mount", -2)

    def test_btrfs_remove(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])

        # remove volume
        self._checkCmd("ssm remove default_pool", [], "wipefs -p /dev/sda")
        self._cmdEq("wipefs -p /dev/sdb", -2)

        self._checkCmd("ssm remove my_pool", [], "wipefs -p /dev/sdc3")
        self._cmdEq("wipefs -p /dev/sdc1", -2)
        self._cmdEq("wipefs -p /dev/sdc2", -3)

        # remove subvolume
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'], '/mnt/test')
        self._checkCmd("ssm remove default_pool:/dev/default_pool/vol001", [],
            "btrfs subvolume delete /mnt/test//dev/default_pool/vol001")
        # remove device
        self._checkCmd("ssm remove /dev/sdc1", [],
            "btrfs device delete /dev/sdc1 /tmp/mount")
        # remove multiple devices
        self._checkCmd("ssm remove /dev/sdc1 /dev/sdb", [],
            "btrfs device delete /dev/sdb /mnt/test")
        self._cmdEq("btrfs device delete /dev/sdc1 /tmp/mount", -2)
        # remove combination
        self._addPool('other_pool', ['/dev/sdd', '/dev/sde'])
        self._checkCmd("ssm remove /dev/sdd /dev/sdb other_pool my_pool default_pool:/dev/default_pool/vol001", [],
            "btrfs subvolume delete /mnt/test//dev/default_pool/vol001")
        self._cmdEq("wipefs -p /dev/sdc1", -2)
        self._cmdEq("wipefs -p /dev/sdc3", -3)
        self._cmdEq("wipefs -p /dev/sdc2", -4)
        self._cmdEq("wipefs -p /dev/sde", -5)
        self._cmdEq("wipefs -p /dev/sdd", -6)
        self._cmdEq("btrfs device delete /dev/sdb /mnt/test", -7)
        self._cmdEq("btrfs device delete /dev/sdd /tmp/mount", -8)

        self._removeMount("/dev/sda")
        # remove all
        self._checkCmd("ssm remove --all", [],
            "wipefs -p /dev/sde")
        self._cmdEq("wipefs -p /dev/sdd", -2)
        self._cmdEq("wipefs -p /dev/sdc1", -3)
        self._cmdEq("wipefs -p /dev/sdc3", -4)
        self._cmdEq("wipefs -p /dev/sdc2", -5)
        self._cmdEq("wipefs -p /dev/sda", -6)
        self._cmdEq("wipefs -p /dev/sdb", -7)

        # TODO
        # remove force
        # remove verbose
        # remove verbose + force

    def test_btrfs_snapshot(self):

        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3', '/dev/sdc1'])
        self._addVol('vol001', 117283225, 1, 'default_pool', ['/dev/sda'])
        self._addVol('vol002', 237284225, 1, 'default_pool', ['/dev/sda'],
                    '/mnt/mount1')
        self._addVol('vol003', 1024, 1, 'default_pool', ['/dev/sdd'])
        self._addVol('vol004', 209715200, 2, 'default_pool', ['/dev/sda',
                     '/dev/sdb'], '/mnt/mount')

        # Create snapshot
        self._checkCmd("ssm snapshot --name new_snap", ['default_pool'],
            "btrfs subvolume snapshot /mnt/mount /mnt/mount/new_snap")
        self._checkCmd("ssm snapshot --name new_snap", ['default_pool:/dev/default_pool/vol001'],
            "btrfs subvolume snapshot /mnt/mount//dev/default_pool/vol001 /mnt/mount//dev/default_pool/vol001/new_snap")
        self._checkCmd("ssm snapshot --name new_snap", ['my_pool'],
            "btrfs subvolume snapshot /tmp/mount /tmp/mount/new_snap")

        # Create snapshot verbose
        self._checkCmd("ssm -v snapshot --name new_snap", ['default_pool'],
            "btrfs -v subvolume snapshot /mnt/mount /mnt/mount/new_snap")

    def test_btrfs_resize(self):
        # Generate some storage data
        self._addPool('default_pool', ['/dev/sda', '/dev/sdb'])
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3'])
        self._addVol('vol001', 2982616, 1, 'my_pool', ['/dev/sdc2'],
                    '/mnt/test1')

        # Extend Volume
        self._checkCmd("ssm resize --size +4m", ['default_pool /dev/sde'],
            "btrfs filesystem resize 11723608063K /tmp/mount");
        self._cmdEq("btrfs device add /dev/sde /tmp/mount", -2)
        self._checkCmd("ssm resize --size +1g", ['my_pool /dev/sde'],
            "btrfs filesystem resize 1073052017K /mnt/test1");
        self._cmdEq("btrfs device add /dev/sde /mnt/test1", -2)

        # Shrink volume
        self._checkCmd("ssm resize", ['-s-100G', 'default_pool'],
            "btrfs filesystem resize 11618746367K /tmp/mount");
        self._checkCmd("ssm resize -s-500G", ['my_pool /dev/sde'],
            "btrfs filesystem resize 547715441K /mnt/test1");
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sde /mnt/test1")

        # Set volume size
        self._checkCmd("ssm resize", ['-s 10M', 'default_pool'],
            "btrfs filesystem resize 10240K /tmp/mount");
        self._checkCmd("ssm resize", ['-s 10M', 'my_pool'],
            "btrfs filesystem resize 10240K /mnt/test1");

        # Set volume and add devices
        self._checkCmd("ssm resize -s 12T default_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 12884901888K /tmp/mount");
        self.assertEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")
        self._checkCmd("ssm resize -s 1T my_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 1073741824K /mnt/test1");
        self.assertEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /mnt/test1")
        self._checkCmd("ssm resize -s 1T my_pool /dev/sde /dev/sdc2",
            [], "btrfs filesystem resize 1073741824K /mnt/test1");
        self.assertEqual(self.run_data[-2],
            "btrfs device add /dev/sde /mnt/test1")

        # Set volume in without the need adding more devices
        self._checkCmd("ssm resize -s 10G default_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 10485760K /tmp/mount");
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")
        self._checkCmd("ssm resize -s 10G my_pool /dev/sdd /dev/sde",
            [], "btrfs filesystem resize 10485760K /mnt/test1");
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /mnt/test1")

        # Extend volume and add devices to cover the size
        self._checkCmd("ssm resize -s +500G default_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 12247891967K /tmp/mount");
        self.assertEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /tmp/mount")

        # Extend volume in without the need adding more devices
        self._checkCmd("ssm resize -s 1k default_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 1K /tmp/mount");
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")

        # Shrink volume with devices provided
        self._checkCmd("ssm resize -s-10G default_pool /dev/sdc1 /dev/sde",
            [], "btrfs filesystem resize 11713118207K /tmp/mount");
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")
        self.assertNotEqual(self.run_data[-2],
            "btrfs device add /dev/sdc1 /dev/sde /tmp/mount")

    def test_btrfs_add(self):
        default_pool = btrfs.SSM_BTRFS_DEFAULT_POOL

        # Adding to non existent pool
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "mkfs.btrfs -L {0} /dev/sda".format(default_pool))
        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "mkfs.btrfs -L {0} /dev/sda /dev/sdc1".format(default_pool))
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "mkfs.btrfs -L my_pool /dev/sda")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "mkfs.btrfs -L my_pool /dev/sda")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "mkfs.btrfs -L my_pool /dev/sda /dev/sdc1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "mkfs.btrfs -L my_pool /dev/sda /dev/sdc1")

        # Adding to existing default pool
        self._addPool(default_pool, ['/dev/sdb', '/dev/sdd'])
        # Add device into default pool
        self._checkCmd("ssm add", ['/dev/sda'],
            "btrfs device add /dev/sda /tmp/mount")
        # Add more devices into default pool
        self._checkCmd("ssm add", ['/dev/sda /dev/sdc1'],
            "btrfs device add /dev/sda /dev/sdc1 /tmp/mount")

        # Adding to existing defined pool
        self._addPool('my_pool', ['/dev/sdc2', '/dev/sdc3'])
        self._addVol('vol001', 2982616, 1, 'my_pool', ['/dev/sdc2'],
                    '/mnt/test1')
        # Add device into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda'],
            "btrfs device add /dev/sda /mnt/test1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda'],
            "btrfs device add /dev/sda /mnt/test1")
        # Add more devices into defined pool
        self._checkCmd("ssm add", ['-p my_pool', '/dev/sda /dev/sdc1'],
            "btrfs device add /dev/sda /dev/sdc1 /mnt/test1")
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sda /dev/sdc1'],
            "btrfs device add /dev/sda /dev/sdc1 /mnt/test1")
        # Add verbose
        self._checkCmd("ssm -v add", ['--pool {0}'.format(default_pool),
            '/dev/sda /dev/sdc1'],
            "btrfs -v device add /dev/sda /dev/sdc1 /tmp/mount")

        # Add two devices into existing pool (one of the devices already is in
        # the pool
        self._checkCmd("ssm add", ['--pool my_pool', '/dev/sdc2 /dev/sda'],
            "btrfs device add /dev/sda /mnt/test1")
        self._checkCmd("ssm add", ['/dev/sda /dev/sdb'],
            "btrfs device add /dev/sda /tmp/mount")