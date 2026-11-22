;; Initial and goal states as given in the project question.
;; LabStarted is added to the goal so that the session actually starts
;; (the expected plan in the question ends with StartLab).
(define (problem p01-question)
  (:domain lab-basic)
  (:init
    (ProjectorOff)
    (ComputersAvailable)
    (LabUnclean)
    (SoftwareNotInstalled)
    (InstructorAbsent))
  (:goal (and
    (ProjectorOn)
    (LabClean)
    (SoftwareReady)
    (InstructorPresent)
    (LabStarted))))
