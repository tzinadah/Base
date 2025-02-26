import os
from typing import Union

import rosparam
import rospkg
import rospy
import rosservice
import smach
import smach_ros
from geometry_msgs.msg import Point, Pose, PoseStamped, Quaternion
from lasr_skills import PlayMotion
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from std_msgs.msg import Header

PUBLIC_CONTAINER = False

try:
    from pal_startup_msgs.srv import (
        StartupStart,
        StartupStartRequest,
        StartupStop,
        StartupStopRequest,
    )
except ModuleNotFoundError:
    PUBLIC_CONTAINER = True


class GoToLocation(smach.StateMachine):
    def __init__(
        self,
        location: Union[Pose, None] = None,
        location_param: Union[str, None] = None,
        safe_navigation: bool = True,
    ):
        if location is not None or location_param is not None:
            super(GoToLocation, self).__init__(outcomes=["succeeded", "failed"])
        else:
            super(GoToLocation, self).__init__(
                outcomes=["succeeded", "failed"], input_keys=["location"]
            )

        if safe_navigation:
            r = rospkg.RosPack()
            els = rosparam.load_file(
                os.path.join(r.get_path("lasr_skills"), "config", "motions.yaml")
            )
            for param, ns in els:
                rosparam.upload_params(ns, param)

        IS_SIMULATION = (
            "/pal_startup_control/start" not in rosservice.get_service_list()
        )

        with self:
            if safe_navigation:
                smach.StateMachine.add(
                    "LOWER_BASE",
                    PlayMotion("pre_navigation"),
                    transitions={
                        "succeeded": (
                            "ENABLE_HEAD_MANAGER"
                            if not IS_SIMULATION
                            else "GO_TO_LOCATION"
                        ),
                        "aborted": "failed",
                        "preempted": "failed",
                    },
                )

                if not IS_SIMULATION:
                    if PUBLIC_CONTAINER:
                        rospy.logwarn(
                            "You are using a public container. The head manager will not be stopped during navigation."
                        )
                    else:
                        smach.StateMachine.add(
                            "ENABLE_HEAD_MANAGER",
                            smach_ros.ServiceState(
                                "/pal_startup_control/start",
                                StartupStart,
                                request=StartupStartRequest("head_manager", ""),
                            ),
                            transitions={
                                "succeeded": "GO_TO_LOCATION",
                                "preempted": "failed",
                                "aborted": "failed",
                            },
                        )

                if location is not None:
                    smach.StateMachine.add(
                        "GO_TO_LOCATION",
                        smach_ros.SimpleActionState(
                            "move_base",
                            MoveBaseAction,
                            goal=MoveBaseGoal(
                                target_pose=PoseStamped(
                                    pose=location, header=Header(frame_id="map")
                                )
                            ),
                        ),
                        transitions={
                            "succeeded": (
                                "DISABLE_HEAD_MANAGER"
                                if not IS_SIMULATION
                                else "RAISE_BASE"
                            ),
                            "aborted": "failed",
                            "preempted": "failed",
                        },
                    )
                elif location_param is not None:
                    smach.StateMachine.add(
                        "GO_TO_LOCATION",
                        smach_ros.SimpleActionState(
                            "move_base",
                            MoveBaseAction,
                            goal=MoveBaseGoal(
                                target_pose=PoseStamped(
                                    pose=Pose(
                                        position=Point(
                                            **rospy.get_param(
                                                f"{location_param}/position"
                                            )
                                        ),
                                        orientation=Quaternion(
                                            **rospy.get_param(
                                                f"{location_param}/orientation"
                                            )
                                        ),
                                    ),
                                    header=Header(frame_id="map"),
                                )
                            ),
                        ),
                        transitions={
                            "succeeded": (
                                "DISABLE_HEAD_MANAGER"
                                if not IS_SIMULATION
                                else "RAISE_BASE"
                            ),
                            "aborted": "failed",
                            "preempted": "failed",
                        },
                    )
                else:
                    smach.StateMachine.add(
                        "GO_TO_LOCATION",
                        smach_ros.SimpleActionState(
                            "move_base",
                            MoveBaseAction,
                            goal_cb=lambda ud, _: MoveBaseGoal(
                                target_pose=PoseStamped(
                                    pose=ud.location, header=Header(frame_id="map")
                                )
                            ),
                            input_keys=["location"],
                        ),
                        transitions={
                            "succeeded": (
                                "DISABLE_HEAD_MANAGER"
                                if not IS_SIMULATION
                                else "RAISE_BASE"
                            ),
                            "aborted": "succeeded",
                            "preempted": "failed",
                        },
                    )

                if not IS_SIMULATION:
                    if PUBLIC_CONTAINER:
                        rospy.logwarn(
                            "You are using a public container. The head manager will not be start following navigation."
                        )
                    else:
                        smach.StateMachine.add(
                            "DISABLE_HEAD_MANAGER",
                            smach_ros.ServiceState(
                                "/pal_startup_control/stop",
                                StartupStop,
                                request=StartupStopRequest("head_manager"),
                            ),
                            transitions={
                                "succeeded": "RAISE_BASE",
                                "aborted": "failed",
                                "preempted": "failed",
                            },
                        )

                smach.StateMachine.add(
                    "RAISE_BASE",
                    PlayMotion("post_navigation"),
                    transitions={
                        "succeeded": "succeeded",
                        "aborted": "failed",
                        "preempted": "failed",
                    },
                )
            else:
                smach.StateMachine.add(
                    "GO_TO_LOCATION",
                    smach_ros.SimpleActionState(
                        "move_base",
                        MoveBaseAction,
                        goal_cb=lambda ud, _: MoveBaseGoal(
                            target_pose=PoseStamped(
                                pose=ud.location, header=Header(frame_id="map")
                            )
                        ),
                        input_keys=["location"],
                    ),
                    transitions={
                        "succeeded": "succeeded",
                        "aborted": "failed",
                        "preempted": "failed",
                    },
                )
