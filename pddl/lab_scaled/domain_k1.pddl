;; LAB-SCALED domain with 1 workstation(s) (auto-generated)
(define (domain lab-scaled-k1)
  (:requirements :strips :action-costs)
  (:predicates (MainPowerOff) (MainPowerOn) (LabUnclean) (LabClean) (NetworkDown) (NetworkUp) (ProjectorOff) (ProjectorOn) (InstructorAbsent) (InstructorPresent) (SoftwareReady) (LabStarted) (PC1Off) (PC1On) (PC1SoftwareInstalled) (PC1Ready))
  (:functions (total-cost))
  (:action CleanLab
    :parameters ()
    :precondition (and (LabUnclean) (MainPowerOff))
    :effect (and (LabClean) (not (LabUnclean)) (increase (total-cost) 15)))
  (:action SwitchOnMainPower
    :parameters ()
    :precondition (and (MainPowerOff))
    :effect (and (MainPowerOn) (not (MainPowerOff)) (increase (total-cost) 1)))
  (:action ConnectNetwork
    :parameters ()
    :precondition (and (MainPowerOn) (NetworkDown))
    :effect (and (NetworkUp) (not (NetworkDown)) (increase (total-cost) 2)))
  (:action PrepareProjector
    :parameters ()
    :precondition (and (ProjectorOff) (MainPowerOn))
    :effect (and (ProjectorOn) (not (ProjectorOff)) (increase (total-cost) 2)))
  (:action SwitchOffProjector
    :parameters ()
    :precondition (and (ProjectorOn))
    :effect (and (ProjectorOff) (not (ProjectorOn)) (increase (total-cost) 1)))
  (:action BootPC1
    :parameters ()
    :precondition (and (PC1Off) (MainPowerOn))
    :effect (and (PC1On) (not (PC1Off)) (increase (total-cost) 1)))
  (:action InstallSoftwarePC1
    :parameters ()
    :precondition (and (PC1On) (NetworkUp))
    :effect (and (PC1SoftwareInstalled) (increase (total-cost) 5)))
  (:action ActivateLicensePC1
    :parameters ()
    :precondition (and (PC1SoftwareInstalled) (NetworkUp))
    :effect (and (PC1Ready) (increase (total-cost) 1)))
  (:action ShutDownPC1
    :parameters ()
    :precondition (and (PC1On))
    :effect (and (PC1Off) (not (PC1On)) (increase (total-cost) 1)))
  (:action VerifyAllWorkstations
    :parameters ()
    :precondition (and (PC1Ready))
    :effect (and (SoftwareReady) (increase (total-cost) 1)))
  (:action CallInstructor
    :parameters ()
    :precondition (and (InstructorAbsent) (LabClean) (SoftwareReady) (ProjectorOn))
    :effect (and (InstructorPresent) (not (InstructorAbsent)) (increase (total-cost) 3)))
  (:action StartLab
    :parameters ()
    :precondition (and (LabClean) (SoftwareReady) (ProjectorOn) (InstructorPresent))
    :effect (and (LabStarted) (increase (total-cost) 1)))
)
