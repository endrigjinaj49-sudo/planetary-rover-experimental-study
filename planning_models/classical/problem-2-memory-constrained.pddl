(define (problem memory-rover-constrained)
  (:domain memory-rover)

  (:objects
    rover1 - rover
    base site1 site2 site3 site4 - location
    data1 data2 data3 data4 - data
  )

  (:init
    ;; Initial rover position
    (at rover1 base)

    ;; Base station
    (base base)

    ;; Map connections
    (connected base site1)
    (connected site1 base)

    (connected site1 site2)
    (connected site2 site1)

    (connected site2 site3)
    (connected site3 site2)

    (connected site3 site4)
    (connected site4 site3)

    ;; Data locations
    (data-at data1 site1)
    (data-at data2 site2)
    (data-at data3 site3)
    (data-at data4 site4)

    ;; Initial memory values
    (= (used-memory rover1) 0)
    (= (memory-capacity rover1) 10)

    ;; Each data item has size 6.
    ;; The rover cannot carry two data items at once because 6 + 6 > 10.
    (= (data-size data1) 4)
    (= (data-size data2) 4)
    (= (data-size data3) 10)
     (= (data-size data4) 6)
  )

  (:goal
    (and
      (offloaded data1)
      (offloaded data2)
      (offloaded data3)
      (offloaded data4)
    )
  )
)