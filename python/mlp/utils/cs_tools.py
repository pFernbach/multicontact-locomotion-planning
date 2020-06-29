import multicontact_api
from multicontact_api import ContactSequence, ContactPhase, ContactPatch
from curves import piecewise, polynomial, SE3Curve
from pinocchio import SE3, Quaternion
from mlp.utils.util import SE3FromConfig,  computeContactNormal, rootOrientationFromFeetPlacement
from mlp.utils.util import computeEffectorTranslationBetweenStates, computeEffectorRotationBetweenStates
from mlp.utils.util import effectorPlacementFromPhaseConfig, buildRectangularContactPoints
import numpy as np
import types
from hpp.corbaserver.rbprm.rbprmstate import State, StateHelper
from math import isnan, ceil
multicontact_api.switchToNumpyArray()

def createPhaseFromConfig(fb, q, limbsInContact, t_init = -1):
    phase = ContactPhase()
    phase.q_init = np.array(q)
    fb.setCurrentConfig(q)
    com = np.array(fb.getCenterOfMass())
    if t_init > 0:
        phase.timeInitial = 0.
    phase.c_init = com.copy()
    phase.c_final = com.copy()
    if  fb.client.robot.getDimensionExtraConfigSpace() >= 6 and len(q) == fb.getConfigSize():
        # add dc and ddc values from extraDOF
        phase.dc_init = np.array(q[-6:-3])
        phase.dc_final = np.array(q[-6:-3])
        phase.ddc_init = np.array(q[-3:])
        phase.ddc_final = np.array(q[-3:])
    for limb in limbsInContact:
        eeName = fb.dict_limb_joint[limb]
        q_j = fb.getJointPosition(eeName)
        placement = SE3FromConfig(q_j)
        patch = ContactPatch(placement)  # TODO set friction / other parameters here
        phase.addContact(eeName, patch)
    return phase

def addPhaseFromConfig(fb, cs, q, limbsInContact, t_init = -1):
    multicontact_api.switchToNumpyArray() # FIXME : why is it required to add it again here ?
    cs.append(createPhaseFromConfig(fb, q, limbsInContact, t_init))


def computeCenterOfSupportPolygonFromState(s):
    com = np.zeros(3)
    numContacts = float(len(s.getLimbsInContact()))
    for limbId in s.getLimbsInContact():
        com += np.array(s.getCenterOfContactForLimb(limbId)[0])
    com /= numContacts
    com[2] += s.fullBody.DEFAULT_COM_HEIGHT
    return com.tolist()

def computeCenterOfSupportPolygonFromPhase(phase, DEFAULT_HEIGHT):
    com = np.zeros(3)
    z_max = -100
    for patch in phase.contactPatches().values():
        com += patch.placement.translation
        z_max = max(z_max, patch.placement.translation[2])
    com /= phase.numContacts()
    com[2] = z_max + DEFAULT_HEIGHT
    return com


def projectCoMInSupportPolygon(s):
    desiredCOM = computeCenterOfSupportPolygonFromState(s)
    # print "try to project state to com position : ",desiredCOM
    success = False
    maxIt = 20
    #print "project state to com : ", desiredCOM
    q_save = s.q()[::]
    while not success and maxIt > 0:
        success = s.fullBody.projectStateToCOM(s.sId, desiredCOM, maxNumSample=0)
        maxIt -= 1
        desiredCOM[2] -= 0.005
    #print "success = ", success
    #print "result = ", s.q()
    if success and isnan(s.q()[0]):  # FIXME why does it happen ?
        success = False
        s.setQ(q_save)
    return success


def generateConfigFromPhase(fb, phase, projectCOM=False):
    fb.usePosturalTaskContactCreation(False)
    effectorsInContact = phase.effectorsInContact()
    contacts = []  # contacts should contains the limb names, not the effector names
    list_effector = list(fb.dict_limb_joint.values())
    for eeName in effectorsInContact:
        contacts += [list(fb.dict_limb_joint.keys())[list_effector.index(eeName)]]
    #q = phase.q_init.tolist() # should be the correct config for the previous phase, if used only from high level helper methods
    q = fb.referenceConfig[::] + [0] * 6  # FIXME : more generic !
    root = computeCenterOfSupportPolygonFromPhase(phase, fb.DEFAULT_COM_HEIGHT).tolist()
    q[0:2] = root[0:2]
    q[2] += root[2] - fb.DEFAULT_COM_HEIGHT
    quat = Quaternion(phase.root_t.evaluateAsSE3(phase.timeInitial).rotation)
    q[3:7] = [quat.x, quat.y, quat.z, quat.w]
    # create state in fullBody :
    state = State(fb, q=q, limbsIncontact=contacts)
    # check if q is consistent with the contact placement in the phase :
    fb.setCurrentConfig(q)
    for limbId in contacts:
        eeName = fb.dict_limb_joint[limbId]
        placement_fb = SE3FromConfig(fb.getJointPosition(eeName))
        placement_phase = phase.contactPatch(eeName).placement
        if placement_fb != placement_phase:  # add a threshold instead of 0 ? how ?
            # need to project the new contact :
            placement = phase.contactPatch(eeName).placement
            p = placement.translation.tolist()
            n = computeContactNormal(placement).tolist()
            state, success = StateHelper.addNewContact(state, limbId, p, n, 1000)
            if not success:
                print("Cannot project the configuration to contact, for effector : ", eeName)
                return state.q()
            if projectCOM:
                success = projectCoMInSupportPolygon(state)
                if not success:
                    print("cannot project com to the middle of the support polygon.")
    phase.q_init = np.array(state.q())

    return state.q()


def setFinalState(cs, com=None, q=None):
    phase = cs.contactPhases[-1]
    if q is not None:
        phase.q_end = np.array(q)
    if com is None:
        com_x = 0.
        com_y = 0.
        for patch in phase.contactPatches().values():
            com_x += patch.placement.translation[0]
            com_y += patch.placement.translation[1]
        com_x /= phase.numContacts()
        com_y /= phase.numContacts()
        com_z = phase.c_init[2]
        com = np.array([com_x, com_y, com_z])
    elif isinstance(com, list):
        com = np.array(com)
    copyPhaseInitToFinal(phase)
    phase.c_final = com


# generate a walking motion from the last phase in the contact sequence.
# the contacts will be moved in the order of the 'gait' list. With the first one move only of half the stepLength
# TODO : make it generic ! it's currently limited to motion in the x direction
def walk(fb, cs, distance, stepLength, gait, offset_y = None, duration_ss = -1 , duration_ds = -1):
    fb.usePosturalTaskContactCreation(True)
    prev_phase = cs.contactPhases[-1]
    for limb in gait:
        eeName = fb.dict_limb_joint[limb]
        assert prev_phase.isEffectorInContact(eeName), "All limbs in gait should be in contact in the first phase"
    if offset_y is None:
        offset_y = [0] * len(gait)
    isFirst = True
    reached = False
    firstContactReachedGoal = False
    remainingDistance = distance
    while remainingDistance >= 1e-6:
        for k, limb in enumerate(gait):
            #print("move limb : ",limb)
            eeName = fb.dict_limb_joint[limb]
            if isFirst:
                length = stepLength / 2.
                isFirst = False
            else:
                length = stepLength
            if k == 0:
                if length > (remainingDistance + stepLength / 2.):
                    length = remainingDistance + stepLength / 2.
                    firstContactReachedGoal = True
            else:
                if length > remainingDistance:
                    length = remainingDistance
            transform = SE3.Identity()
            #print("length = ",length)
            transform.translation = np.array([length, offset_y[k], 0])
            cs.moveEffectorOf(eeName, transform, duration_ds, duration_ss)
        remainingDistance -= stepLength
        offset_y = [0] * len(gait)
    if not firstContactReachedGoal:
        transform = SE3.Identity()
        #print("last length = ", stepLength)
        transform.translation  = np.array([stepLength / 2., 0, 0])
        cs.moveEffectorOf(fb.dict_limb_joint[gait[0]], transform, duration_ds, duration_ss)
    q_end = fb.referenceConfig[::] + [0] * 6
    q_end[0] += distance
    fb.setCurrentConfig(q_end)
    com = fb.getCenterOfMass()
    setFinalState(cs, com, q=q_end)
    fb.usePosturalTaskContactCreation(False)


def computePhasesTimings(cs, cfg):
    current_t = cs.contactPhases[0].timeInitial
    if current_t < 0:
        current_t = 0.

    for pid,phase in enumerate(cs.contactPhases):
        duration = 0
        if phase.numContacts() == 1:
            duration = cfg.DURATION_SS
        if phase.numContacts() == 2:
            duration = cfg.DURATION_DS
        if phase.numContacts() == 3:
            duration = cfg.DURATION_TS
        if phase.numContacts() == 4:
            duration = cfg.DURATION_QS
        if phase.numContacts() > 4:
            raise Exception("Case not implemented")
        if pid == 0:
            duration = cfg.DURATION_INIT
        if pid == (cs.size() - 1):
            duration = cfg.DURATION_FINAL
        # Adjust duration if needed to respect bound on effector velocity
        duration_feet_trans = 0.
        duration_feet_rot = 0.
        if pid < cs.size() - 1:
            dist_feet = computeEffectorTranslationBetweenStates(cs, pid)
            if dist_feet > 0.:
                duration_feet_trans = (2. * cfg.EFF_T_DELAY + 2. * cfg.EFF_T_PREDEF) + dist_feet / cfg.FEET_MAX_VEL
            rot_feet = computeEffectorRotationBetweenStates(cs, pid)
            if rot_feet > 0.:
                duration_feet_rot = (2. * cfg.EFF_T_DELAY + 2. * cfg.EFF_T_PREDEF) + rot_feet / cfg.FEET_MAX_ANG_VEL
            duration_feet = max(duration_feet_trans, duration_feet_rot)
            # Make it a multiple of solver_dt :
            if duration_feet > 0.:
                duration_feet = ceil(duration_feet / cfg.SOLVER_DT) * cfg.SOLVER_DT
            if False:
                print("for phase : ", pid)
                print("dist_feet            : ", dist_feet)
                print("duration translation : ", duration_feet_trans)
                print("rot_feet             : ", rot_feet)
                print("duration rotation    : ", duration_feet_rot)
                print("duration complete    : ", duration_feet)
            duration = round(max(duration, duration_feet), 3) # round at the millisecond

        phase.timeInitial = current_t
        phase.timeFinal = round(current_t + duration, 3)
        current_t = phase.timeFinal
    return cs



def computePhasesCOMValues(cs,DEFAULT_HEIGHT, overwrite = False):
    """
    Generate c, dc and ddc initial and final values for the contactSequence if not provided or if overwrite = True
    With null dc and ddc and c position in the center of the support polygone for each phase
    :param cs: the contact sequence
    :param DEFAULT_HEIGHT: z value used for com_z position
    :param overwrite: if true, overwrite existing values
    :return:
    """
    for pid,phase in enumerate(cs.contactPhases):
        if overwrite or not phase.c_init.any():
            # this value is uninitialized
            phase.c_init = computeCenterOfSupportPolygonFromPhase(phase,DEFAULT_HEIGHT)
        if overwrite:
            phase.dc_init = np.zeros(3)
            phase.ddc_init = np.zeros(3)
        if pid > 0:
            cs.contactPhases[pid-1].c_final = phase.c_init
            cs.contactPhases[pid-1].dc_final = phase.dc_init
            cs.contactPhases[pid-1].ddc_final = phase.ddc_init
    if not cs.contactPhases[-1].c_final.any():
        # this value is uninitialized
        cs.contactPhases[-1].c_final = cs.contactPhases[-1].c_init
    if overwrite:
        cs.contactPhases[-1].dc_final = np.zeros(3)
        cs.contactPhases[-1].ddc_final = np.zeros(3)
    return cs

def computePhasesConfigurations(cs, fb):
    for pid, phase in enumerate(cs.contactPhases):
        if not phase.q_init.any():
            if pid > 0 and len(cs.contactPhases[pid-1].getContactsBroken(phase)) == 1 and \
                    len(cs.contactPhases[pid-1].getContactsCreated(phase)) == 0 and \
                    len(cs.contactPhases[pid-1].getContactsRepositioned(phase)) == 0:
                # there is only a contact break between previous and current phase, do not generate a new config but copy the previous one
                phase.q_init = cs.contactPhases[pid-1].q_init
            else:
                generateConfigFromPhase(fb, phase, projectCOM=True)
        if pid > 0:
            cs.contactPhases[pid-1].q_final = phase.q_init
    if not cs.contactPhases[-1].q_final.any():
        cs.contactPhases[-1].q_final =  cs.contactPhases[-1].q_init
    return cs

def initEmptyPhaseCentroidalTrajectory(phase):
    phase.c_t = piecewise()
    phase.dc_t = piecewise()
    phase.ddc_t = piecewise()
    phase.L_t = piecewise()
    phase.dL_t = piecewise()


def initEmptyPhaseWholeBodyTrajectory(phase):
    phase.q_t = piecewise()
    phase.dq_t = piecewise()
    phase.ddq_t = piecewise()
    phase.tau_t = piecewise()

def setCOMtrajectoryFromPoints(phase, c, dc, ddc, timeline, overwriteInit = True, overwriteFinal = True):
    """
    Define the CoM position, velocity and acceleration trajectories as a linear interpolation between each points
    Also set the initial / final values for c, dc and ddc to match the ones in the trajectory
    :param phase:
    :param c:
    :param dc:
    :param ddc:
    :param timeline:
    :param overwrite: Default True : overwrite init/final values even if they exist
    :return:
    """
    phase.c_t = piecewise.FromPointsList(c,timeline.T)
    phase.dc_t = piecewise.FromPointsList(dc,timeline.T)
    phase.ddc_t = piecewise.FromPointsList(ddc,timeline.T)
    if overwriteInit:
        phase.c_init = c[:,0]
    if overwriteInit:
        phase.dc_init = dc[:,0]
    if overwriteInit:
        phase.ddc_init = ddc[:,0]
    if overwriteFinal:
        phase.c_final = c[:,-1]
    if overwriteFinal:
        phase.dc_final= dc[:,-1]
    if overwriteFinal:
        phase.ddc_final = ddc[:,-1]


def setAMtrajectoryFromPoints(phase, L, dL, timeline, overwriteInit = True, overwriteFinal = True):
    """
    Define the AM  value and it's time derivative trajectories as a linear interpolation between each points
    Also set the initial / final values for L and dL to match the ones in the trajectory
    :param phase:
    :param L:
    :param dL:
    :param timeline:
    :param overwrite: Default True : overwrite init/final values even if they exist
    :return:
    """
    phase.L_t = piecewise.FromPointsList(L,timeline.T)
    phase.dL_t = piecewise.FromPointsList(dL,timeline.T)
    if overwriteInit:
        phase.L_init = L[:,0]
    if overwriteInit:
        phase.dL_init = dL[:,0]
    if overwriteFinal:
        phase.L_final = L[:,-1]
    if overwriteFinal:
        phase.dL_final= dL[:,-1]

def setJointsTrajectoryFromPoints(phase, q, dq, ddq, timeline, overwrite=True):
    """
    Define the joints position, velocity and acceleration trajectories as a linear interpolation between each points
    Also set the initial / final values for q, dq and ddq to match the ones in the trajectory
    :param phase:
    :param q:
    :param dq:
    :param ddq:
    :param timeline:
    :param overwrite: Default True : overwrite init/final values even if they exist
    :return:
    """
    phase.q_t = piecewise.FromPointsList(q, timeline.T)
    phase.dq_t = piecewise.FromPointsList(dq, timeline.T)
    phase.ddq_t = piecewise.FromPointsList(ddq, timeline.T)
    if overwrite or not phase.q_init.any():
        phase.q_init = q[:,0]
    if overwrite or not phase.dq_init.any():
        phase.dq_init = dq[:,0]
    if overwrite or not phase.ddq_init.any():
        phase.ddq_init = ddq[:,0]
    if overwrite or not phase.q_final.any():
        phase.q_final = q[:,-1]
    if overwrite or not phase.dq_final.any():
        phase.dq_final = dq[:,-1]
    if overwrite or not phase.ddq_final.any():
        phase.ddq_final = ddq[:,-1]


def connectPhaseTrajToFinalState(phase, duration = None):
    """
    Append to the trajectory of c, dc and ddc a quintic spline connecting phase.c_final, dc_final and ddc_final
    and L and dL with a trajectory at 0
    :param phase:
    :param duration:
    """
    if phase.c_t is None or phase.dc_t is None or phase.ddc_t is None:
        # initialise empty trajectories
        phase.c_t = piecewise()
        phase.dc_t = piecewise()
        phase.ddc_t = piecewise()
        # get the initial state from the phase :
        c_init = phase.c_init
        dc_init = phase.dc_init
        ddc_init = phase.ddc_init
        t_init = phase.timeInitial
    else:
        # get the initial state from the last points of the trajectories :
        t_init = phase.c_t.max()
        c_init = phase.c_t(t_init)
        dc_init = phase.dc_t(t_init)
        ddc_init = phase.ddc_t(t_init)
    if phase.L_t is None or phase.dL_t is None :
        # initialise empty trajectories
        phase.L_t = piecewise()
        phase.dL_t = piecewise()
        # get the initial state from the phase :
        L_init = phase.L_init
        dL_init = phase.dL_init
    else :
        L_init = phase.c_t(t_init)
        dL_init = phase.dL_t(t_init)
    if not phase.c_final.any():
        raise RuntimeError("connectPhaseTrajToFinalState can only be called with a phase with an initialized c_final")
    if duration is not None:
        t_final = t_init + duration
    else:
        t_final = phase.timeFinal
    com_t = polynomial(c_init, dc_init, ddc_init, phase.c_final, phase.dc_final, phase.ddc_final, t_init, t_final)
    L_t = polynomial(L_init, dL_init, phase.L_final, phase.dL_final, t_init, t_final)
    phase.c_t.append(com_t)
    phase.dc_t.append(com_t.compute_derivate(1))
    phase.ddc_t.append(com_t.compute_derivate(2))
    phase.L_t.append(L_t)
    phase.dL_t.append(L_t.compute_derivate(1))
    phase.timeFinal = t_final


def connectPhaseTrajToInitialState(phase, duration):
    """
    Insert at the beginning of the trajectory of c, dc and ddc a quintic spline connecting phase.c_init, dc_init and ddc__init
    and L and dL with a trajectory at 0
    :param phase:
    :param duration:
    """
    if duration <= 0.:
        return
    if phase.c_t is None or phase.dc_t is None or phase.ddc_t is None:
        raise RuntimeError("connectPhaseTrajToFinalState can only be called with a phase with an initialized COM trajectory")
    if phase.L_t is None or phase.dL_t is None :
        raise RuntimeError("connectPhaseTrajToFinalState can only be called with a phase with an initialized AM trajectory")
    if not phase.c_init.any():
        raise RuntimeError("connectPhaseTrajToFinalState can only be called with a phase with an initialized c_final")
    t_final = phase.c_t.min()
    t_init = t_final - duration
    c_final = phase.c_t(t_final)
    dc_final = phase.dc_t(t_final)
    ddc_final = phase.ddc_t(t_final)
    L_final = phase.L_t(t_final)
    dL_final = phase.dL_t(t_final)
    com_t = polynomial( phase.c_init, phase.dc_init, phase.ddc_init,c_final, dc_final, ddc_final, t_init, t_final)
    L_t = polynomial(phase.L_init, phase.dL_init, L_final, dL_final, t_init, t_final)

    # insert this trajectories at the beginning of the phase :
    piecewise_c= piecewise(com_t)
    piecewise_c.append(phase.c_t)
    phase.c_t = piecewise_c
    piecewise_dc= piecewise(com_t.compute_derivate(1))
    piecewise_dc.append(phase.dc_t)
    phase.dc_t = piecewise_dc
    piecewise_ddc= piecewise(com_t.compute_derivate(2))
    piecewise_ddc.append(phase.ddc_t)
    phase.ddc_t = piecewise_ddc
    piecewise_L= piecewise(L_t)
    piecewise_L.append(phase.L_t)
    phase.L_t = piecewise_L
    piecewise_dL= piecewise(L_t.compute_derivate(1))
    piecewise_dL.append(phase.dL_t)
    phase.dL_t = piecewise_dL
    # set the new initial time
    phase.timeInitial = t_init

def computeRootTrajFromConfigurations(cs):
    assert cs.haveConfigurationsValues(), "computeRootTrajFromConfigurations require haveConfigurationsValues"
    for phase in cs.contactPhases:
        p_init = SE3FromConfig(phase.q_init)
        p_final = SE3FromConfig(phase.q_final)
        phase.root_t = SE3Curve(p_init, p_final, phase.timeInitial, phase.timeFinal)


def computeRootTrajFromContacts(Robot, cs):
    #Quaternion(rootOrientationFromFeetPlacement(phase, None)[0].rotation)
    for pid in range(cs.size()):
        phase = cs.contactPhases[pid]
        if pid > 0:
            previous_phase = cs.contactPhases[pid-1]
        else:
            previous_phase = None
        if pid < (cs.size()-1):
            next_phase = cs.contactPhases[pid+1]
        else:
            next_phase = None

        p_init, p_final = rootOrientationFromFeetPlacement(Robot, previous_phase, phase, next_phase)
        phase.root_t = SE3Curve(p_init, p_final, phase.timeInitial, phase.timeFinal)


def copyPhaseInitToFinal(phase):
    phase.c_final = phase.c_init
    phase.dc_final = phase.dc_init
    phase.ddc_final = phase.ddc_init
    phase.L_final = phase.L_init
    phase.dL_final = phase.dL_init
    phase.q_final = phase.q_init

def setFinalFromInitialValues(previous_phase, next_phase):
    """
    Set c_final, dc_final, ddc_final, L_final, dL_final of previous_phase
    to the values of the 'init' in next_phase
    :param previous_phase:
    :param next_phase:
    :return:
    """
    previous_phase.c_final = next_phase.c_init
    previous_phase.dc_final = next_phase.dc_init
    previous_phase.ddc_final = next_phase.ddc_init
    previous_phase.L_final = next_phase.L_init
    previous_phase.dL_final = next_phase.dL_init
    previous_phase.q_final = next_phase.q_init



def setPreviousFinalValues(phase_prev, phase, cfg):
    """
    Set the final values and last points of the trajectory of phase_prev to the initial values of phase
    :param phase_prev:
    :param phase:
    :param cfg:
    :return:
    """
    if phase_prev is None:
        return
    setFinalFromInitialValues(phase_prev,phase)
    t = phase_prev.timeFinal
    phase_prev.q_t.append(phase_prev.q_final, t)
    if cfg.IK_store_joints_derivatives:
        phase_prev.dq_t.append(phase.dq_t(t), t)
        phase_prev.ddq_t.append(phase.ddq_t(t), t)
    if cfg.IK_store_joints_torque:
        phase_prev.tau_t.append(phase.tau_t(t), t)
    if cfg.IK_store_centroidal:
        phase_prev.c_t.append(phase_prev.c_final, t)
        phase_prev.dc_t.append(phase_prev.dc_final, t)
        phase_prev.ddc_t.append(phase_prev.ddc_final, t)
        phase_prev.L_t.append(phase_prev.L_final, t)
        phase_prev.dL_t.append(phase_prev.dL_final, t)
    if cfg.IK_store_zmp:
        phase_prev.zmp_t.append(phase.zmp_t(t), t)
        phase_prev.wrench_t.append(phase.wrench_t(t), t)
    if cfg.IK_store_contact_forces:
        for eeName in phase_prev.effectorsInContact():
            if phase.isEffectorInContact(eeName):
                contact_forces = phase.contactForce(eeName)(t)
                contact_normal_force = phase.contactNormalForce(eeName)(t)
            else:
                contact_normal_force = np.zeros(1)
                if cfg.Robot.cType == "_3_DOF":
                    contact_forces = np.zeros(3)
                else:
                    contact_forces = np.zeros(12)
            phase_prev.contactForce(eeName).append(contact_forces, t)
            phase_prev.contactNormalForce(eeName).append(contact_normal_force.reshape(1), t)



def setInitialFromFinalValues(previous_phase, next_phase):
    """
    Set c_final, dc_init, ddc_init, L_init, dL_init of next_phase
    to the values of the 'final' in previous_phase
    :param previous_phase:
    :param next_phase:
    :return:
    """
    next_phase.c_init = previous_phase.c_final
    next_phase.dc_init = previous_phase.dc_final
    next_phase.ddc_init = previous_phase.ddc_final
    next_phase.L_init = previous_phase.L_final
    next_phase.dL_init = previous_phase.dL_final
    next_phase.q_init = previous_phase.q_final

def resetCOMtrajectories(cs):
    for phase in cs.contactPhases:
        phase.c_t = None
        phase.dc_t = None
        phase.ddc_t = None

def deleteAllTrajectories(cs):
    for phase in cs.contactPhases:
        deletePhaseWBtrajectories(phase)
        phase.c_t = None
        phase.dc_t = None
        phase.ddc_t = None
        phase.L_t = None
        phase.dL_t = None
        phase.root_t = None

def deletePhaseWBtrajectories(phase):
    phase.q_t = None
    phase.dq_t = None
    phase.ddq_t = None
    phase.tau_t = None

def updateContactPlacement(cs, pid_begin, eeName, placement, update_rotation):
    """
    Starting from cs.contactPhases[pid_begin] and going until eeName is in contact,
    the placement of eeName is modified with the given placement.
    Note that the wholebody configurations are not updated !
    :param cs: The ContactSequence to modify
    :param pid_begin: the Id of the first phase to modify
    :param eeName: the effector name
    :param placement: the new placement for eeName
    :param update_rotation: if True, update the placement, if False update only the translation
    """
    for pid in range(pid_begin, cs.size()):
        phase = cs.contactPhases[pid]
        if phase.isEffectorInContact(eeName):
            if update_rotation:
                phase.contactPatch(eeName).placement = placement
            else:
                new_placement = phase.contactPatch(eeName).placement
                new_placement.translation = placement.translation
                phase.contactPatch(eeName).placement = new_placement
        else:
            return

def setAllUninitializedFrictionCoef(cs, mu):
    """
    For all the contact patch of all the phases, if the friction is <= 0, set it to the given value
    :param cs:
    :param mu:
    :return:
    """
    for phase in cs.contactPhases:
        for eeName in phase.effectorsInContact():
            if phase.contactPatch(eeName).friction <= 0 :
                phase.contactPatch(eeName).friction = mu

def setAllUninitializedContactModel(cs, Robot):
    """
    For all the contact patch of all the phases, if the contact type is UNDEFINED, set it from the Robot config
    :param cs: The contact sequence to modify
    :param Robot: The Robot class, require the fields cType, dict_size and dict_offset
    :return:
    """
    for phase in cs.contactPhases:
        for eeName in phase.effectorsInContact():
            if phase.contactPatch(eeName).contact_model.contact_type == ContactType.CONTACT_UNDEFINED:
                if Robot.cType == "_3_DOF":
                    phase.contactPatch(eeName).contact_model.contact_type = ContactType.CONTACT_POINT
                elif Robot.cType == "_6_DOF":
                    phase.contactPatch(eeName).contact_model.contact_type = ContactType.CONTACT_PLANAR
                    phase.contactPatch(eeName).contact_model.contact_points_positions =\
                        buildRectangularContactPoints(Robot.dict_size[eeName], Robot.dict_offset[eeName])
                else:
                    raise RuntimeError("Unknown contact type : ", Robot.cType)

def generateZeroAMreference(cs):
    """
    For all phases in the sequence, set an L_t and dL_t trajectory constant at 0 with the right duration
    :param cs:
    :return:
    """
    for phase in cs.contactPhases:
        phase.L_t = polynomial(np.zeros(3), np.zeros(3), phase.timeInitial, phase.timeFinal)
        phase.dL_t = polynomial(np.zeros(3), np.zeros(3), phase.timeInitial, phase.timeFinal)

def copyEffectorTrajectories(cs_eff, cs):
    """
    Copy all the effector trajectories contained in cs_eff in a copy of cs
    :param cs_eff:
    :param cs:
    :return: A new ContactSequence, which is a copy of cs with the addition of the trajectories from cs_eff
    Return None if the phases do not have the same duration in cs_eff and cs
    """
    if cs_eff.size() != cs.size():
        return None
    cs_res = ContactSequence(cs)
    for pid, phase_eff in enumerate(cs_eff.contactPhases):
        if len(phase_eff.effectorsWithTrajectory()) > 0:
            phase = cs_res.contactPhases[pid]
            if phase.timeInitial != phase_eff.timeInitial or phase.timeFinal != phase_eff.timeFinal:
                print("Unable to copy effector trajectories, the phase duration have changed")
                return None
            for eeName, traj in phase_eff.effectorTrajectories().items():
                phase.addEffectorTrajectory(eeName, traj)
    return cs_res



def generate_effector_trajectories_for_sequence(cfg, cs, generate_end_effector_traj, fullBody = None):
    """
    Generate an effector trajectory for each effectors which are going to be in contact in the next phase
    :param cfg: an instance of the configuration class
    :param cs: the contact sequence
    :param generate_end_effector_traj: a pointer to the method used to generate an end effector trajectory for one phase
    :param fullBody: an instance of rbprm FullBody
    :return: a new contact sequence, containing the same data as the one given as input
    plus the effector trajectories for each swing phases
    """
    cs_res = ContactSequence(cs)
    effectors = cs_res.getAllEffectorsInContact()
    previous_phase = None
    for pid in range(cs_res.size()-1): # -1 as last phase never have effector trajectories
        phase = cs_res.contactPhases[pid]
        next_phase = cs_res.contactPhases[pid+1]
        if pid > 0 :
            previous_phase = cs_res.contactPhases[pid-1]

        for eeName in effectors:
            if not phase.isEffectorInContact(eeName) and next_phase.isEffectorInContact(eeName):
                # eeName will be in compute in the next phase, a trajectory should be added in the current phase
                placement_end = next_phase.contactPatch(eeName).placement
                time_interval = [phase.timeInitial, phase.timeFinal]
                if previous_phase is not None and previous_phase.isEffectorInContact(eeName):
                    placement_init = previous_phase.contactPatch(eeName).placement
                else:
                    placement_init = effectorPlacementFromPhaseConfig(phase,eeName,fullBody)
                # build the trajectory :
                traj = generate_end_effector_traj(cfg, time_interval,placement_init,placement_end)
                phase.addEffectorTrajectory(eeName,traj)
    return cs_res


