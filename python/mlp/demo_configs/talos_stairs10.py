TIMEOPT_CONFIG_FILE = "cfg_softConstraints_talos.yaml"
from .common_talos import *
#Robot.urdfSuffix = "_reduced_safeFeet"
SCRIPT_PATH = "demos"
ENV_NAME = "multicontact/bauzil_stairs"

DURATION_INIT = 1.5  # Time to init the motion
DURATION_FINAL = 1  # Time to stop the robot
DURATION_FINAL_SS = 1.
DURATION_SS = 3.
DURATION_DS = 0.8
DURATION_TS = 0.4

EFF_T_PREDEF_TAKEOFF = 0.6 # duration during which the motion of the end effector is forced to be orthogonal to the contact surface, at the beginning and the end of the phase
EFF_T_PREDEF_LANDING = 0.3
p_max_takeoff = 0.25  #setting used to compute the default height of the effector trajectory. end_effector/bezier_predef.py : computePosOffset()
p_max_landing = 0.15  #setting used to compute the default height of the effector trajectory. end_effector/bezier_predef.py : computePosOffset()


GUIDE_STEP_SIZE = 0.8
MAX_SURFACE_AREA = 2.

COM_SHIFT_Z = -0.025
TIME_SHIFT_COM = 2.


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

gain_vector = np.array(  # gain vector for postural task
    [
        10.,
        5.,
        5.,
        1.,
        1.,
        10.,  # lleg  #low gain on axis along y and knee
        10.,
        5.,
        5.,
        1.,
        1.,
        10.,  #rleg
        5000.,
        5000.,  #chest
        500.,
        1000.,
        100.,
        100.,
        100.,
        100.,
        1000.,
        500.,  #larm
        500.,
        1000.,
        100.,
        100.,
        100.,
        100.,
        1000.,
        50.,  #rarm
        100.,
        100.
    ]  #head
)