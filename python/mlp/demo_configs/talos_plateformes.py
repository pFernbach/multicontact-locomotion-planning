TIMEOPT_CONFIG_FILE = "cfg_softConstraints_timeopt_talos.yaml"
from .common_talos import *
Robot.urdfSuffix += "_safeFeet"
SCRIPT_PATH = "demos"
ENV_NAME = "multicontact/plateforme_surfaces_noscale"

kp_Eff = 2000.  # proportional gain of the effectors motion task
DEMO_NAME = "talos_platformes"

#DURATION_INIT = 3.  # Time to init the motion
DURATION_SS = 2.
DURATION_DS = 1.
DURATION_TS = 0.4
DURATION_CONNECT_GOAL = 0.
COM_SHIFT_Z = -0.05
COM_VIAPOINT_SHIFT_Z = -0.05

EFF_T_PREDEF = 0.3
EFF_T_PREDEF_TAKEOFF = EFF_T_PREDEF  # duration during which the motion of the end effector is forced to be orthogonal to the contact surface, at the beginning and the end of the phase
EFF_T_PREDEF_LANDING = EFF_T_PREDEF
p_max = 0.16
p_max_takeoff = p_max  #setting used to compute the default height of the effector trajectory. end_effector/bezier_predef.py : computePosOffset()
p_max_landing = p_max  #setting used to compute the default height of the effector trajectory. end_effector/bezier_predef.py : computePosOffset()

"""
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
"""

IK_REFERENCE_CONFIG = np.array(Robot.referenceConfig_elbowsUp)