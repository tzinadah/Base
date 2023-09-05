#!/usr/bin/env python3
import smach, os, rospy
from sensor_msgs.msg import Image
from tiago_controllers.helpers.pose_helpers import get_pose_from_param

class WaitForPeople(smach.State):
    def __init__(self, controllers, voice, yolo):
        smach.State.__init__(self, outcomes=['success', 'failed'])

        self.controllers = controllers
        self.voice = voice
        self.yolo = yolo

    def execute(self, userdata):
        # wait and ask
        self.voice.speak("How many people are thinking to go in the lift?")

        # get the answer
        count = 2

        result = self.controllers.base_controller.sync_to_pose(get_pose_from_param('/wait_centre/pose'))
        rospy.sleep(1)

        # send request - image, dataset, confidence, nms
        image = rospy.wait_for_message('/xtion/rgb/image_raw', Image)
        detections = self.yolo(image, "yolov8n.pt", 0.3, 0.3)

        # segment them as well and count them
        count_people = 0
        count_people = sum(1 for det in detections.detected_objects if det.name == "person")

        self.voice.speak("I see {} people".format(count_people))

        if count_people < count:
            return 'failed'
        else:
            return 'success'


        # check if they are static with the frames
