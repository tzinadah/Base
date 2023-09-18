#!/usr/bin/env python3
import smach, os, rospy
from sensor_msgs.msg import Image
from tiago_controllers.helpers.pose_helpers import get_pose_from_param
import json
from interaction_module.srv import AudioAndTextInteraction, AudioAndTextInteractionRequest, \
    AudioAndTextInteractionResponse
from lift.defaults import TEST, PLOT_SHOW, PLOT_SAVE, DEBUG_PATH, DEBUG, RASA
from sensor_msgs.msg import PointCloud2
from lasr_object_detection_yolo.detect_objects_v8 import detect_objects, perform_detection, debug

class WaitForPeople(smach.State):
    def __init__(self, default):
        smach.State.__init__(self, outcomes=['success', 'failed'])
        self.default = default

        # self.controllers = controllers
        # self.voice = voice
        # self.yolo = yolo
        # self.speech = speech

    def listen(self):
        resp = self.default.speech()
        if not resp.success:
            self.default.voice.speak("Sorry, I didn't get that")
            return self.listen()
        resp = json.loads(resp.json_response)
        rospy.loginfo(resp)
        return resp


    def get_people_number(self):
        resp = self.listen()
        if resp["intent"]["name"] != "negotiate_lift":
            self.default.voice.speak("Sorry, I misheard you, could you say again how many people?")
            return self.get_people_number()
        people = resp["entities"].get("people",[])
        if not people: 
            self.default.voice.speak("Sorry, could you say again how many people?")
            return self.get_people_number()
        people_number = int(people[0]["value"])        
        self.default.voice.speak("I hear that there are {} people".format(people_number))
        return people_number

    def safe_seg_info(self, detections):

        pos_people = []
        for i, person in detections:
            print(person)
            pos_people.append([person[0], person[1]])

        num_people = len(detections)

        rospy.set_param("/lift/num_people", num_people)
        rospy.set_param("/lift/pos_persons", pos_people)

        if DEBUG > 3:
            print("num clusters in safe")
            print(rospy.get_param("/lift/num_people"))
            print(pos_people)
            print(type(pos_people))
            print("centers in safe")
            print(rospy.get_param("/lift/pos_persons"))


    def execute(self, userdata):
        # wait and ask
        self.default.voice.speak("How many people are thinking to go in the lift?")
        self.default.voice.speak("Please answer with a number.")

        count = 2
        if RASA:
            try:
                count = self.get_people_number()
            except Exception as e:
                print(e)
                count = 2
                self.default.voice.speak("I couldn't hear how many people, so I'm going to guess 2")
        else:
            req = AudioAndTextInteractionRequest()
            req.action = "ROOM_REQUEST"
            req.subaction = "ask_location"
            req.query_text = "SOUND:PLAYING:PLEASE"
            resp = self.default.speech(req)
            print("The response of asking the people is {}".format(resp.result))
            # count = resp.result

        self.default.voice.speak("I will now move to the center of the lift waiting area")
        state = self.default.controllers.base_controller.ensure_sync_to_pose(get_pose_from_param('/wait_centre/pose'))
        rospy.loginfo("State of the robot in wait for people is {}".format(state))
        rospy.sleep(0.5)

        # prev start   only yolo
        # send request - image, dataset, confidence, nms
        # image = rospy.wait_for_message('/xtion/rgb/image_raw', Image)
        # detections = self.default.yolo(image, "yolov8n-seg.pt", 0.3, 0.3)
        # prev end

        polygon = rospy.get_param('test_lift_points')
        pcl_msg = rospy.wait_for_message("/xtion/depth_registered/points", PointCloud2)
        detections, im = perform_detection(self.default, pcl_msg, polygon, ["person"], "yolov8n-seg.pt")
        debug(im, detections)
        people = detect_objects(["person"])


        # segment them as well and count them
        count_people = 0
        count_people = sum(1 for det in detections.detected_objects if det.name == "person")

        self.default.voice.speak("I can see beautiful people around. Only {} of them to be exact.".format(count_people))

        if count_people < count:
            return 'failed'
        else:
            return 'success'


        # check if they are static with the frames
