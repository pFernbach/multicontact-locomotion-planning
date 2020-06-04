TIMEOPT_CONFIG_FILE = "cfg_softConstraints_talos.yaml"
from .common_talos import *
SCRIPT_PATH = "demos"
ENV_NAME = "multicontact/ground"

DURATION_SS = 1.8
DURATION_DS = 0.7

EFF_T_PREDEF = 0.3
EFF_T_DELAY_BEGIN = 0.
EFF_T_DELAY_END = 0.1
FEET_MAX_VEL = 1.
FEET_MAX_ANG_VEL = 1.5
p_max = 0.06
COM_SHIFT_Z = -0.03
COM_VIAPOINT_SHIFT_Z = -0.01
DURATION_CONNECT_GOAL = 0.

USE_PLANNING_ROOT_ORIENTATION = True
GUIDE_STEP_SIZE = 0.5
GUIDE_MAX_YAW = 100.  # maximal yaw rotation difference between two discretization step

IK_REFERENCE_CONFIG = np.array(
[       0.0,
        0.0,
        1.02127,
        0.0,
        0.0,
        0.0,
        1.,  # Free flyer
        0.0,
        0.0,
        -0.411354,
        0.859395,
        -0.448041,
        -0.001708,  # Left Leg
        0.0,
        0.0,
        -0.411354,
        0.859395,
        -0.448041,
        -0.001708,  # Right Leg
        0.0,
        0.006761,  # Chest
        0.40,
        0.24,
        -0.6,
        -1.45,
        0.0,
        -0.0,
        0.,
        -0.005,  # Left Arm
        -0.4,
        -0.24,
        0.6,
        -1.45,
        0.0,
        0.0,
        0.,
        -0.005,  # Right Arm
        0.,
        0.
    ])

#IK_REFERENCE_CONFIG = np.array(Robot.referenceConfig)
