#!/usr/bin/env python
"""Runs all of the mission components of Scan The Code."""
import txros
import genpy
from twisted.internet import defer
import sys
from sensor_msgs.msg import Image, CameraInfo
from scan_the_code_lib import ScanTheCodeAction, ScanTheCodePerception, Debug
from navigator_msgs.srv import ObjectDBQuery, ObjectDBQueryRequest
from navigator_tools import DBHelper, fprint
___author___ = "Tess Bianchi"


class ScanTheCodeMission:
    """Class that contains all the functionality for Scan The Code."""

    def __init__(self, navigator):
        """Initialize ScanTheCodeMission class."""
        self.nh = navigator.nh
        self.navigator = navigator
        self.action = ScanTheCodeAction()
        self.mission_complete = False
        self.colors = []
        self.scan_the_code = None

        self.stc_correct = False

    @txros.util.cancellableInlineCallbacks
    def init_(self, tl):
        """Initialize the txros elements of ScanTheCodeMission class."""
        my_tf = tl
        self.debug = Debug(self.nh, wait=False)
        self.perception = ScanTheCodePerception(my_tf, self.debug, self.nh)
        print "0"
        self.database = yield self.nh.get_service_client("/database/requests", ObjectDBQuery)
        print "1"
        self.image_sub = yield self.nh.subscribe("/stereo/right/image_rect_color", Image, self._image_cb)
        print "2"
        self.cam_info_sub = yield self.nh.subscribe("/stereo/right/camera_info", CameraInfo, self._info_cb)

        print "3"
        self.helper = yield DBHelper(self.nh).init_(self.navigator)

    def _image_cb(self, image):
        self.perception.add_image(image)

    def _info_cb(self, info):
        self.perception.update_info(info)

    @txros.util.cancellableInlineCallbacks
    def _get_scan_the_code(self):
        v = False
        if self.scan_the_code is None:
            ans = yield self.helper.get_object("scan_the_code", volume_only=v)
        else:
            try:
                ans = yield self.helper.get_object_by_id(self.scan_the_code.id)
            except Exception:
                print "PROBLEM"
                ans = yield self.helper.get_object("scan_the_code", volume_only=v)

        fprint("GOT SCAN THE CODE WITH ID {}".format(ans.id), msg_color="blue")
        defer.returnValue(ans)

    @txros.util.cancellableInlineCallbacks
    def find_colors(self, timeout=sys.maxint):
        """Find the colors of scan the code."""
        length = genpy.Duration(timeout)
        start = self.nh.get_time()
        while start - self.nh.get_time() < length:
            try:
                scan_the_code = yield self._get_scan_the_code()
            except Exception:
                print "Could not get scan the code..."
                yield self.nh.sleep(.1)
                continue

            # try:
            success, colors = yield self.perception.search(scan_the_code)
            if success:
                defer.returnValue(colors)
            # except Exception as e:
            #     print e
            #     yield self.nh.sleep(.1)
            #     continue

            yield self.nh.sleep(.3)
        defer.returnValue(None)

    @txros.util.cancellableInlineCallbacks
    def initial_position(self, timeout=sys.maxint):
        """Get the initial position of scan the code."""
        length = genpy.Duration(timeout)
        start = self.nh.get_time()
        while start - self.nh.get_time() < length:
            try:
                scan_the_code = yield self._get_scan_the_code()
            except Exception as exc:
                print exc
                print "Could not get scan the code..."
                yield self.nh.sleep(.1)
                continue

            defer.returnValue(self.action.initial_position(scan_the_code))

    @txros.util.cancellableInlineCallbacks
    def correct_pose(self, pose, timeout=sys.maxint):
        """Check to see if the boat pose needs to be corrected to get an optimal viewing angle."""
        length = genpy.Duration(timeout)
        start = self.nh.get_time()
        while start - self.nh.get_time() < length:
            try:
                scan_the_code = yield self._get_scan_the_code()
            except Exception as exc:
                print exc
                print "Could not get scan the code..."
                yield self.nh.sleep(.1)
                continue

            correct_pose = yield self.perception.correct_pose(scan_the_code)
            if correct_pose:
                self.stc_correct = True
                defer.returnValue(True)
                break

            yield self.nh.sleep(.1)
