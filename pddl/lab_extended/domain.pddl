;; =====================================================================
;; LAB-EXTENDED : a realistic engineering-lab preparation domain.
;;
;; Adds power, safety, network, licensing and lab manuals to the basic
;; domain, plus action costs (estimated minutes) via :action-costs.
;;
;; Interesting interactions that a planner must reason about:
;;   * Cleaning is only allowed with the MAIN POWER OFF (electrical safety),
;;     but almost everything else needs the power ON  -> ordering matters.
;;   * Switching the power off also shuts down projector, PCs and network.
;;   * Two ways to get software ready:
;;       network install + online licence  (more actions, cheaper: 24 min)
;;       USB install     + offline licence (fewer actions, dearer: 50 min)
;;     -> BFS (fewest actions) and UCS/A* (least cost) return different plans.
;;   * ConnectNetwork needs (NetworkSwitchWorking); drop it from :init to model
;;     a faulty switch (see p07).
;; =====================================================================
(define (domain lab-extended)
  (:requirements :strips :action-costs)

  (:predicates
    (SafetyNotChecked) (SafetyChecked)
    (MainPowerOff) (MainPowerOn)
    (LabUnclean) (LabClean)
    (ComputersAvailable) (ComputersOff) (ComputersOn)
    (NetworkSwitchWorking) (NetworkDown) (NetworkUp)
    (SoftwareNotInstalled) (SoftwareInstalled)
    (LicenseInactive) (SoftwareReady)
    (ProjectorOff) (ProjectorOn)
    (ManualsNotReady) (ManualsReady)
    (InstructorAbsent) (InstructorPresent)
    (LabStarted))

  (:functions (total-cost))

  (:action SafetyInspection
    :parameters ()
    :precondition (and (SafetyNotChecked))
    :effect (and (SafetyChecked) (not (SafetyNotChecked)) (increase (total-cost) 5)))

  (:action CleanLab
    :parameters ()
    :precondition (and (LabUnclean) (MainPowerOff))
    :effect (and (LabClean) (not (LabUnclean)) (increase (total-cost) 15)))

  (:action SwitchOnMainPower
    :parameters ()
    :precondition (and (MainPowerOff) (SafetyChecked))
    :effect (and (MainPowerOn) (not (MainPowerOff)) (increase (total-cost) 1)))

  (:action BootComputers
    :parameters ()
    :precondition (and (ComputersAvailable) (ComputersOff) (MainPowerOn))
    :effect (and (ComputersOn) (not (ComputersOff)) (increase (total-cost) 3)))

  (:action ConnectNetwork
    :parameters ()
    :precondition (and (MainPowerOn) (NetworkSwitchWorking) (NetworkDown))
    :effect (and (NetworkUp) (not (NetworkDown)) (increase (total-cost) 2)))

  (:action InstallSoftware
    :parameters ()
    :precondition (and (ComputersOn) (NetworkUp) (SoftwareNotInstalled))
    :effect (and (SoftwareInstalled) (not (SoftwareNotInstalled)) (increase (total-cost) 20)))

  (:action InstallSoftwareFromUSB
    :parameters ()
    :precondition (and (ComputersOn) (SoftwareNotInstalled))
    :effect (and (SoftwareInstalled) (not (SoftwareNotInstalled)) (increase (total-cost) 40)))

  (:action ActivateLicense
    :parameters ()
    :precondition (and (SoftwareInstalled) (NetworkUp) (LicenseInactive))
    :effect (and (SoftwareReady) (not (LicenseInactive)) (increase (total-cost) 2)))

  (:action ActivateLicenseOffline
    :parameters ()
    :precondition (and (SoftwareInstalled) (ComputersOn) (LicenseInactive))
    :effect (and (SoftwareReady) (not (LicenseInactive)) (increase (total-cost) 10)))

  (:action PrepareProjector
    :parameters ()
    :precondition (and (ProjectorOff) (MainPowerOn))
    :effect (and (ProjectorOn) (not (ProjectorOff)) (increase (total-cost) 2)))

  (:action PrintManuals
    :parameters ()
    :precondition (and (ManualsNotReady) (MainPowerOn))
    :effect (and (ManualsReady) (not (ManualsNotReady)) (increase (total-cost) 5)))

  (:action CallInstructor
    :parameters ()
    :precondition (and (InstructorAbsent) (LabClean) (SoftwareReady) (ProjectorOn))
    :effect (and (InstructorPresent) (not (InstructorAbsent)) (increase (total-cost) 3)))

  (:action StartLab
    :parameters ()
    :precondition (and (LabClean) (SoftwareReady) (ProjectorOn) (InstructorPresent) (ManualsReady))
    :effect (and (LabStarted) (increase (total-cost) 1)))

  ;; ---------------- actions that undo progress ----------------
  (:action SwitchOffMainPower
    :parameters ()
    :precondition (and (MainPowerOn))
    :effect (and (MainPowerOff) (not (MainPowerOn))
                 (ProjectorOff) (not (ProjectorOn))
                 (ComputersOff) (not (ComputersOn))
                 (NetworkDown)  (not (NetworkUp))
                 (increase (total-cost) 1)))

  (:action SwitchOffProjector
    :parameters ()
    :precondition (and (ProjectorOn))
    :effect (and (ProjectorOff) (not (ProjectorOn)) (increase (total-cost) 1)))

  (:action ShutDownComputers
    :parameters ()
    :precondition (and (ComputersOn))
    :effect (and (ComputersOff) (not (ComputersOn)) (increase (total-cost) 2)))
)
