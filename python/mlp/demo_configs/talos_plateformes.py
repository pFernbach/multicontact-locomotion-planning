TIMEOPT_CONFIG_FILE = "cfg_softConstraints_timeopt_talos.yaml"
from .common_talos import *
SCRIPT_PATH = "demos"
ENV_NAME = "multicontact/plateforme_surfaces"

kp_Eff = 500.  # proportional gain of the effectors motion task


DURATION_INIT = 3.  # Time to init the motion
DURATION_SS = 2.5
DURATION_DS = 0.8
DURATION_TS = 0.4
DURATION_CONNECT_GOAL = 0.

EFF_T_PREDEF = 0.2
p_max = 0.06
